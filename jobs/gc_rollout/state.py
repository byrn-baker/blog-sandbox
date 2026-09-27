"""Durable ledger in a completed PrepareGCRollout JobResult.

Only this module mutates the ledger. Never write into a running Celery task's
result: Celery owns that field until preparation has finished successfully.
"""
import copy
from contextlib import contextmanager

from django.db import transaction
from django.utils import timezone
from nautobot.extras.models import JobResult

SCHEMA = "gc-rollout/v1"
TERMINAL = {"completed", "failed", "canceled", "needs_reconciliation", "reconciled"}


def now():
    return timezone.now().isoformat()


def validate(row):
    data = row.result
    if row.status != "SUCCESS" or not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError("Run ID must identify a successfully completed Prepare GC Rollout result")
    if not row.job_model or not row.job_model.job_class_name == "PrepareGCRollout":
        raise ValueError("Result does not belong to PrepareGCRollout")
    return data


def read(run_id):
    return copy.deepcopy(validate(JobResult.objects.select_related("job_model").get(pk=run_id)))


@contextmanager
def locked(run_id):
    with transaction.atomic():
        row = JobResult.objects.select_for_update().get(pk=run_id)
        data = validate(row)
        yield data
        data["updated_at"] = now()
        row.result = data
        row.save(update_fields=["result"])


def event(data, stage, detail, device=None):
    data["events"].append({"at": now(), "stage": stage, "device": device, "detail": detail})
    # Samples are summarized separately; retain all transition events.


def canceled(run_id):
    return read(run_id)["cancel_requested"]


def progress(run_id, device, sample):
    with locked(run_id) as data:
        old = data["devices"].get(device, {})
        data["devices"][device] = {**old, **sample, "observed_at": now()}
        if old.get("stage") != sample.get("stage"):
            event(data, sample["stage"], "Verification stage changed", device)


class RolloutCanceled(RuntimeError):
    """Cooperative stop; already deployed changes are not reverted."""


def check_cancel(run_id):
    if canceled(run_id):
        raise RolloutCanceled("Cancellation requested; no further rollout stages will start")
