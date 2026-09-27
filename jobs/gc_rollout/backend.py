"""Golden Config integration. Device writes occur only through its deploy play."""
from django.utils import timezone
from nautobot.dcim.models import Device
from nautobot.extras.models import Status
from nautobot_golden_config.jobs import BackupJob, ComplianceJob
from nautobot_golden_config.models import ConfigPlan, ConfigCompliance, GoldenConfig
from nautobot_golden_config.nornir_plays.config_deployment import config_deployment
from nautobot_golden_config.utilities.helper import update_dynamic_groups_cache

from . import state
from .manifest import validate_current
from .verify import check_cancel


def permission_check(job, manifest):
    """Executing a custom Job must not bypass object-level change permissions."""
    ids = [p["id"] for p in manifest["plans"]]
    devices = [p["device_id"] for p in manifest["plans"]]
    if ConfigPlan.objects.restrict(job.user, "change").filter(pk__in=ids).count() != len(ids):
        raise PermissionError("Executor needs change permission on all selected Config Plans")
    if Device.objects.restrict(job.user, "view").filter(pk__in=devices).count() != len(devices):
        raise PermissionError("Executor needs view permission on all selected devices")


def deploy(job, run_id, manifest, names):
    """Reserve every plan before touching devices; a crash makes it non-retryable."""
    check_cancel(run_id)
    validate_current(manifest, names)
    ids = [p["id"] for p in manifest["plans"] if p["device"] in names]
    with state.locked(run_id) as ledger:
        if ledger["cancel_requested"]:
            check_cancel(run_id)
        # Lock only for claim, not across Nornir threads (which update these rows).
        plans = list(ConfigPlan.objects.select_for_update().filter(pk__in=ids))
        if len(plans) != len(ids) or any(p.deploy_result_id for p in plans):
            raise ValueError("A plan has been claimed by another deployment")
        validate_current(manifest, names)
        approved = Status.objects.get(name="Approved")
        ConfigPlan.objects.filter(pk__in=ids).update(deploy_result=job.job_result, status=approved)
        ledger["claimed_plans"].extend(ids)
        ledger["stage"] = "deploying"
        state.event(ledger, "deploying", {"devices": names, "plan_ids": ids})
    job.logger.info("Deploying approved wave: %s", ", ".join(names))
    # Uses the current JobResult/request/user; never queues a nested Celery task.
    job.data = {"config_plan": ConfigPlan.objects.filter(pk__in=ids),
                "fail_job_on_task_failure": True, "debug": False}
    update_dynamic_groups_cache()
    config_deployment(job)
    if ConfigPlan.objects.filter(pk__in=ids).exclude(status__name="Completed").exists():
        raise RuntimeError("Golden Config did not mark every plan Completed")
    for name in names:
        state.progress(run_id, name, {"stage": "deployed", "deployment_job_result": str(job.job_result.pk)})


def invoke(job, cls, devices):
    """Use the normal GC backup/compliance paths, including Git persistence."""
    child = cls()
    child.request = job.request
    child.run(device=devices, fail_job_on_task_failure=True, debug=False,
              commit_message="Golden Config rollout evidence")


def refresh_evidence(job, run_id, manifest, names):
    check_cancel(run_id)
    device_ids = [p["device_id"] for p in manifest["plans"] if p["device"] in names]
    devices = Device.objects.filter(pk__in=device_ids)
    started = timezone.now()
    with state.locked(run_id) as ledger:
        ledger["stage"] = "backup_and_compliance"
        state.event(ledger, "backup_and_compliance", {"devices": names})
    invoke(job, BackupJob, devices)
    check_cancel(run_id)
    invoke(job, ComplianceJob, devices)
    evidence = []
    for device in devices:
        gc = GoldenConfig.objects.get(device=device)
        if (not gc.backup_last_success_date or gc.backup_last_success_date < started or
                not gc.compliance_last_success_date or gc.compliance_last_success_date < started):
            raise RuntimeError(f"{device.name}: fresh backup/compliance evidence is missing")
        expected_rules = {r["id"] for r in manifest["rules"] if r["platform_id"] == str(device.platform_id)}
        rows = list(ConfigCompliance.objects.filter(device=device, rule_id__in=expected_rules))
        if {str(r.rule_id) for r in rows} != expected_rules or any(not r.compliance for r in rows):
            raise RuntimeError(f"{device.name}: approved compliance features did not pass")
        evidence.append({"device": device.name, "backup_at": gc.backup_last_success_date.isoformat(),
                         "compliance_at": gc.compliance_last_success_date.isoformat(),
                         "compliance_result_ids": [str(r.pk) for r in rows]})
    validate_current(manifest, [])
    with state.locked(run_id) as ledger:
        ledger["evidence"].extend(evidence)
        state.event(ledger, "wave_verified", {"devices": names})
