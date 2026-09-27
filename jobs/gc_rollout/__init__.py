"""Nautobot Jobs for reviewed, durable Golden Config rollouts."""
import json
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from nautobot.apps.jobs import Job, StringVar, TextVar
from nautobot.extras.models import Job as JobModel, JobResult

from . import state
from .backend import deploy, permission_check, refresh_evidence
from .manifest import build, digest, validate_current
from .state import RolloutCanceled, check_cancel

name = "Golden Config Rollout"


class PrepareGCRollout(Job):
    spec_json = TextVar(description="Reviewed rollout specification; see jobs/gc_rollout/README.md")

    class Meta:
        name = "Prepare GC Rollout"
        description = "Snapshot configuration plans, source, canaries and verification policy for explicit approval. No device writes."
        has_sensitive_variables = False

    def run(self, spec_json):
        if len(spec_json) > 100_000:
            raise ValueError("Rollout specification is too large")
        manifest = build(self.user, json.loads(spec_json))
        approval_digest = digest(manifest)
        self.logger.info("Prepared %s plans in %s waves. Approval digest: %s",
                         len(manifest["plans"]), len(manifest["waves"]), approval_digest)
        return {
            "schema": state.SCHEMA, "run_id": str(self.job_result.pk), "manifest": manifest,
            "approval_digest": approval_digest, "created_at": state.now(), "updated_at": state.now(),
            "expires_at": (timezone.now() + timedelta(hours=1)).isoformat(),
            "stage": "prepared", "execution_job": None, "approval": None, "cancel_requested": False,
            "claimed_plans": [], "completed_waves": [], "devices": {}, "events": [], "evidence": [],
        }


class ExecuteGCRollout(Job):
    run_id = StringVar(description="Completed Prepare GC Rollout JobResult UUID")
    approval_digest = StringVar(description="Exact SHA256 returned by preparation and approved by the operator")
    approval_reference = StringVar(description="Reference to the explicit operator approval for this digest")

    class Meta:
        name = "Execute GC Rollout"
        description = "Execute exactly the reviewed configuration rollout, stop on failed gates, and persist progress."
        has_sensitive_variables = False
        is_singleton = True
        soft_time_limit = 21600
        time_limit = 21660

    def run(self, run_id, approval_digest, approval_reference):
        if not approval_reference.strip():
            raise ValueError("Explicit operator approval reference required")
        ledger = state.read(run_id)
        manifest = ledger["manifest"]
        permission_check(self, manifest)
        validate_current(manifest, [p["device"] for p in manifest["plans"]])
        # Serialize claims across runs in addition to Nautobot's singleton cache lock.
        with transaction.atomic():
            JobModel.objects.select_for_update().get(pk=self.job_result.job_model_id)
            others = JobResult.objects.filter(result__schema=state.SCHEMA).exclude(pk=run_id)
            for other in others.iterator():
                value = other.result
                if value.get("execution_job") and value.get("stage") not in {"completed", "failed", "canceled", "reconciled"}:
                    raise ValueError(f"Another rollout is active or needs reconciliation: {other.pk}")
            with state.locked(run_id) as ledger:
                if ledger["execution_job"] or ledger["stage"] != "prepared" or ledger["cancel_requested"]:
                    raise ValueError("Run already claimed or canceled; automatic replay is forbidden")
                if timezone.now().isoformat() > ledger["expires_at"]:
                    raise ValueError("Approval envelope expired; prepare a new run")
                if approval_digest != ledger["approval_digest"] or digest(manifest) != approval_digest:
                    raise ValueError("Approval digest does not match the exact manifest")
                ledger["execution_job"] = str(self.job_result.pk)
                ledger["stage"] = "preflight"
                ledger["approval"] = {"user_id": str(self.user.pk), "username": self.user.username,
                                      "reference": approval_reference, "digest": approval_digest, "at": state.now()}
                state.event(ledger, "approved", ledger["approval"])
        try:
            for index, names in enumerate(manifest["waves"]):
                check_cancel(run_id)
                self.logger.info("Wave %s/%s: %s", index + 1, len(manifest["waves"]), ", ".join(names))
                deploy(self, run_id, manifest, names)
                with state.locked(run_id) as ledger:
                    ledger["stage"] = "verifying"
                    state.event(ledger, "verifying", {"wave": index + 1, "devices": names})
                refresh_evidence(self, run_id, manifest, names)
                with state.locked(run_id) as ledger:
                    ledger["completed_waves"].append(index + 1)
                    state.event(ledger, "wave_completed", {"wave": index + 1, "devices": names})
            check_cancel(run_id)
            with state.locked(run_id) as ledger:
                ledger["stage"] = "completed"
                state.event(ledger, "completed", "All approved waves completed deployment, fresh backup and selected compliance gates")
            self.logger.info("Rollout %s completed", run_id)
            return {"run_id": run_id, "stage": "completed"}
        except Exception as exc:
            with state.locked(run_id) as ledger:
                uncertain = ledger["stage"] == "deploying"
                ledger["stage"] = "needs_reconciliation" if uncertain else "canceled" if isinstance(exc, RolloutCanceled) else "failed"
                ledger["error_type"] = type(exc).__name__
                state.event(ledger, ledger["stage"], "Expansion stopped; inspect execution logs and device evidence. No automatic rollback.")
            self.logger.error("Rollout %s stopped: %s", run_id, str(exc))
            raise


class CancelGCRollout(Job):
    run_id = StringVar(description="Prepare GC Rollout JobResult UUID")
    reason = StringVar(description="Reason for stopping expansion")

    class Meta:
        name = "Cancel GC Rollout"
        description = "Request cooperative cancellation; run on a control queue with an available worker."
        has_sensitive_variables = False

    def run(self, run_id, reason):
        owner = JobResult.objects.get(pk=run_id).user_id
        executor = state.read(run_id).get("approval") or {}
        if not self.user.is_superuser and str(self.user.pk) not in {str(owner), executor.get("user_id")}:
            raise PermissionError("Only the preparer, executor or an administrator may cancel this rollout")
        if not reason.strip():
            raise ValueError("A cancellation reason is required")
        with state.locked(run_id) as ledger:
            if ledger["stage"] in state.TERMINAL:
                return {"run_id": run_id, "stage": ledger["stage"], "cancel_requested": ledger["cancel_requested"]}
            ledger["cancel_requested"] = True
            if ledger["stage"] == "prepared":
                ledger["stage"] = "canceled"
            state.event(ledger, "cancel_requested", {"user": self.user.username, "reason": reason})
        return {"run_id": run_id, "cancel_requested": True,
                "message": "In-flight deployment may finish; cancellation stops subsequent stages/waves."}


class ReconcileGCRollout(Job):
    run_id = StringVar(description="Interrupted rollout's preparation JobResult UUID")
    evidence_reference = StringVar(description="Operator reconciliation evidence for every claimed device/plan")

    class Meta:
        name = "Reconcile GC Rollout"
        description = "Administrator acknowledges an ended/interrupted run after manual device reconciliation. Never replays it."
        has_sensitive_variables = False

    def run(self, run_id, evidence_reference):
        if not self.user.is_superuser:
            raise PermissionError("Reconciliation requires a Nautobot administrator")
        if not evidence_reference.strip():
            raise ValueError("Document device/plan reconciliation before releasing the rollout lock")
        with state.locked(run_id) as ledger:
            execution_id = ledger["execution_job"]
            if not execution_id or ledger["stage"] in {"prepared", "completed", "reconciled"}:
                raise ValueError("This run does not require reconciliation")
            execution = JobResult.objects.get(pk=execution_id)
            if execution.status in {"PENDING", "STARTED", "RETRY", "RECEIVED"}:
                raise ValueError("Execution is still active; establish worker termination before reconciliation")
            ledger["stage"] = "reconciled"
            state.event(ledger, "reconciled", {"user": self.user.username, "evidence": evidence_reference,
                                              "message": "Claims preserved; any further deployment needs fresh plans/approval"})
        return {"run_id": run_id, "stage": "reconciled"}
