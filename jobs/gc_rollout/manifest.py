"""Build an immutable approval envelope from existing Golden Config plans."""
import hashlib
import json
import re
from importlib.metadata import version

from nautobot.extras.models import GitRepository
from nautobot_golden_config.models import ConfigPlan, GoldenConfig, ComplianceRule
from nautobot_golden_config.utilities.constant import ENABLE_POSTPROCESSING, PLUGIN_CFG

from .source import relative_backup_path, validate_source


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def plan_snapshot(plan):
    device = plan.device
    if not device.platform or not device.platform.network_driver:
        raise ValueError(f"Device requires a configured platform network driver: {device.name}")
    return {
        "id": str(plan.pk), "device_id": str(device.pk), "device": device.name,
        "platform": device.platform.network_driver, "platform_id": str(device.platform_id),
        "management_ip": str(device.primary_ip4 or device.primary_ip6 or ""),
        "config_set": plan.config_set, "plan_type": plan.plan_type,
        "plan_result": str(plan.plan_result_id), "change_control_id": plan.change_control_id,
        "features": sorted(str(x) for x in plan.feature.values_list("pk", flat=True)),
    }


def rules_snapshot(platform_ids, feature_ids):
    return list(ComplianceRule.objects.filter(platform_id__in=platform_ids, feature_id__in=feature_ids)
                .order_by("pk").values("id", "platform_id", "feature_id", "match_config", "config_type", "config_ordered", "custom_compliance"))


def json_safe(value):
    return json.loads(json.dumps(value, default=str))


def backup_paths(repo, plans):
    from nautobot.apps.utils import render_jinja2
    from nautobot.dcim.models import Device
    from nautobot_golden_config.utilities.helper import get_device_to_settings_map

    mapping = get_device_to_settings_map(Device.objects.filter(pk__in=[p.device_id for p in plans]))
    paths = []
    for plan in {p.device_id: p for p in plans}.values():
        settings = mapping[plan.device_id]
        if settings.backup_repository_id == repo.pk:
            rendered = render_jinja2(template_code=settings.backup_path_template, context={"obj": plan.device})
            paths.append(relative_backup_path(rendered))
    if len(paths) != len(set(paths)):
        raise ValueError("Two devices map to the same backup output path")
    return sorted(paths)


def source_snapshot(repo, plans):
    result = {"id": str(repo.pk), "name": repo.name, "commit": repo.current_head,
              "backup_paths": backup_paths(repo, plans)}
    validate_source(repo, result)
    return result


def postprocessing_snapshot():
    """Allow Golden Config's built-in renderer for literal, fully reviewed plans."""
    if not ENABLE_POSTPROCESSING:
        return {"enabled": False, "callables": []}
    builtin = "nautobot_golden_config.utilities.config_postprocessing.render_secrets"
    available = [builtin] + list(PLUGIN_CFG.get("postprocessing_callables", []))
    subscribed = list(PLUGIN_CFG.get("postprocessing_subscribed") or available)
    if any(name != builtin for name in subscribed):
        raise ValueError("Rollout requires a reviewed adapter for custom postprocessing callables")
    return {"enabled": True, "callables": subscribed}


def verify_postprocessing(plan, user, policy):
    # A template could resolve secrets or change later even with identical plan text.
    if any(marker in plan.config_set for marker in ("{{", "{%", "{#")):
        raise ValueError("Rollout requires literal plan commands, not unresolved templates")
    if not policy["enabled"]:
        return
    from django.http import HttpRequest
    from nautobot_golden_config.utilities.config_postprocessing import get_config_postprocessing

    request = HttpRequest()
    request.user = user
    rendered = get_config_postprocessing(ConfigPlan.objects.filter(pk=plan.pk), request)
    if rendered.strip() != plan.config_set.strip():
        raise ValueError("Postprocessing changed the reviewed commands; prepare a literal plan first")


def build(user, spec):
    required = {"plan_ids", "source_repository", "source_commit", "ci_evidence", "rollback_reference",
                "change_control_id", "canaries", "parallel_canaries", "wave_size", "feature_ids"}
    if not isinstance(spec, dict):
        raise ValueError("Specification must be a JSON object")
    if version("nautobot") != "3.2.1" or version("nautobot-golden-config") != "3.0.7":
        raise ValueError("This integration targets Nautobot 3.2.1 / Golden Config 3.0.7; review APIs before upgrading")
    if set(spec) != required:
        raise ValueError(f"Spec keys must be exactly: {sorted(required)}")
    ids = spec["plan_ids"]
    if not isinstance(ids, list) or not 1 <= len(ids) <= 64 or len(set(ids)) != len(ids):
        raise ValueError("Provide 1..64 distinct plan IDs")
    for field, low, high in (("wave_size", 1, 16),):
        if type(spec[field]) is not int or not low <= spec[field] <= high:
            raise ValueError(f"{field} must be an integer in {low}..{high}")
    if type(spec["parallel_canaries"]) is not bool:
        raise ValueError("parallel_canaries must be an explicit boolean policy")
    for key in ("ci_evidence", "rollback_reference", "change_control_id"):
        if not isinstance(spec[key], str) or not spec[key].strip() or len(spec[key]) > 2048:
            raise ValueError(f"{key} must be a nonempty reference")
    postprocessing = postprocessing_snapshot()
    repo = GitRepository.objects.restrict(user, "view").get(pk=spec["source_repository"])
    if not re.fullmatch(r"[0-9a-f]{40}", spec["source_commit"]) or repo.current_head != spec["source_commit"]:
        raise ValueError("Source commit must match the synchronized Nautobot GitRepository HEAD")
    plans = list(ConfigPlan.objects.restrict(user, "view").filter(pk__in=ids).select_related("device__platform", "status"))
    if len(plans) != len(ids):
        raise ValueError("Missing or inaccessible Config Plans")
    if not isinstance(spec["feature_ids"], list) or not spec["feature_ids"] or len(set(spec["feature_ids"])) != len(spec["feature_ids"]):
        raise ValueError("Explicit distinct compliance feature IDs are required")
    entries = []
    for plan in plans:
        if plan.deploy_result_id or not plan.status or plan.status.name not in {"Not Approved", "Approved"}:
            raise ValueError(f"Plan {plan.pk} is already used or not reviewable")
        if plan.change_control_id != spec["change_control_id"]:
            raise ValueError("Every plan must match the reviewed change_control_id")
        verify_postprocessing(plan, user, postprocessing)
        entry = plan_snapshot(plan)
        commands = [x.strip() for x in plan.config_set.splitlines() if x.strip() and x.strip() != "!"]
        if not commands:
            raise ValueError("Config Plans must contain commands")
        if not set(entry["features"]) <= set(spec["feature_ids"]):
            raise ValueError("Selected compliance features must cover every plan feature")
        baseline = GoldenConfig.objects.get(device_id=plan.device_id)
        if not baseline.backup_last_success_date or not baseline.intended_last_success_date:
            raise ValueError(f"{plan.device.name}: intended config and successful backup are required")
        if not baseline.backup_config or not baseline.intended_config:
            raise ValueError(f"{plan.device.name}: nonempty backup and intended config are required")
        entry.update({"intended_digest": digest(baseline.intended_config),
                      "baseline_backup_at": baseline.backup_last_success_date.isoformat()})
        entries.append(entry)
    entries.sort(key=lambda p: (p["platform"], p["device"]))
    names = {p["device"] for p in entries}
    canaries = spec["canaries"]
    if not isinstance(canaries, list) or len(set(canaries)) != len(canaries) or not set(canaries) <= names:
        raise ValueError("canaries must be distinct device names in the selected plans")
    platforms = {p["platform"] for p in entries}
    if len(canaries) != len(platforms) or {p["platform"] for p in entries if p["device"] in canaries} != platforms:
        raise ValueError("Select exactly one canary per affected platform")
    waves = [canaries] if spec["parallel_canaries"] else [[name] for name in canaries]
    remaining = list(dict.fromkeys(p["device"] for p in entries if p["device"] not in canaries))
    waves += [remaining[i:i + spec["wave_size"]] for i in range(0, len(remaining), spec["wave_size"])]
    rules = json_safe(rules_snapshot({p["platform_id"] for p in entries}, spec["feature_ids"]))
    for platform in {p["platform_id"] for p in entries}:
        if {r["feature_id"] for r in rules if r["platform_id"] == platform} != set(spec["feature_ids"]):
            raise ValueError("Each platform needs a compliance rule for every selected feature")
    return {"profile": "gc-coordinator-v2", "spec": spec, "plans": entries, "waves": waves, "rules": rules, "postprocessing": postprocessing,
            "source": source_snapshot(repo, plans), "versions": {name: version(name) for name in
            ("nautobot", "nautobot-golden-config", "nautobot-plugin-nornir", "nornir-nautobot")}}


def validate_current(manifest, pending):
    """Revalidate authoritative inputs before each wave; status is checked separately."""
    if manifest.get("profile") != "gc-coordinator-v2":
        raise ValueError("Prepare a new rollout with the current coordinator before executing")
    if postprocessing_snapshot() != manifest["postprocessing"]:
        raise ValueError("Postprocessing changed since approval")
    validate_source(GitRepository.objects.get(pk=manifest["source"]["id"]), manifest["source"])
    if any(version(k) != v for k, v in manifest["versions"].items()):
        raise ValueError("Runtime package versions changed since preparation")
    current_rules = json_safe(rules_snapshot({p["platform_id"] for p in manifest["plans"]}, manifest["spec"]["feature_ids"]))
    if current_rules != manifest["rules"]:
        raise ValueError("Compliance rules changed since approval")
    for expected in manifest["plans"]:
        gc = GoldenConfig.objects.get(device_id=expected["device_id"])
        if digest(gc.intended_config) != expected["intended_digest"]:
            raise ValueError(f"Intended config changed: {expected['device']}")
        if expected["device"] not in pending:
            continue
        plan = ConfigPlan.objects.select_related("device__platform", "status").get(pk=expected["id"])
        actual = plan_snapshot(plan)
        if any(expected[k] != value for k, value in actual.items()) or plan.deploy_result_id:
            raise ValueError(f"Plan changed or already used: {expected['device']}")
        if not plan.status or plan.status.name not in {"Not Approved", "Approved"}:
            raise ValueError(f"Plan no longer eligible: {expected['device']}")
