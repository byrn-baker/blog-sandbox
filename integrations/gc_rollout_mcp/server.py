"""Thin stdio MCP adapter; all orchestration and durable state live in Nautobot.

Credentials are supplied by the launching process, never accepted in tool inputs.
Job UUIDs must be explicitly configured after the Jobs are registered/enabled.
"""
import json
import os
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("golden-config-rollout")


def uuid(value):
    return str(UUID(value))


def request(path, data=None):
    base = os.environ["NAUTOBOT_URL"].rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("NAUTOBOT_URL must be an HTTP(S) service URL without embedded credentials")
    context = ssl.create_default_context(cafile=os.getenv("NAUTOBOT_CA_BUNDLE") or None)
    req = Request(base + "/api/" + path, data=json.dumps(data).encode() if data is not None else None,
                  headers={"Authorization": "Token " + os.environ["NAUTOBOT_TOKEN"],
                           "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urlopen(req, timeout=30, context=context) as response:
            return json.load(response)
    except HTTPError as exc:
        # Error bodies can contain sensitive job/config data; keep tool errors concise.
        raise RuntimeError(f"Nautobot returned HTTP {exc.code}; inspect its API/job logs") from None
    except URLError:
        raise RuntimeError("Nautobot connection failed; check endpoint and CA configuration") from None


def submit(key, data):
    job_id = uuid(os.environ[key])
    result = request(f"extras/jobs/{job_id}/run/", {"data": data})
    job = result["job_result"]
    return {"job_result_id": job["id"], "status": job["status"],
            "message": "Queued; poll gc_rollout_status. Submission is not deployment success."}


@mcp.tool()
def gc_rollout_prepare(spec: dict) -> dict:
    """Snapshot a reviewed NTP rollout without deploying. Returns the preparation JobResult/run ID."""
    result = submit("GC_ROLLOUT_PREPARE_JOB_ID", {"spec_json": json.dumps(spec)})
    result["run_id"] = result["job_result_id"]
    return result


@mcp.tool()
def gc_rollout_start(run_id: str, approval_digest: str, approval_reference: str) -> dict:
    """Deploy only after explicit operator approval of the returned manifest/digest and canary policy.

    Returns immediately after enqueueing. Never retry automatically after a timeout;
    read the preparation ledger/execution JobResults to establish whether it started.
    """
    if not approval_reference.strip():
        raise ValueError("Explicit operator approval reference required")
    return submit("GC_ROLLOUT_EXECUTE_JOB_ID", {"run_id": uuid(run_id), "approval_digest": approval_digest,
                                               "approval_reference": approval_reference})


@mcp.tool()
def gc_rollout_status(run_id: str, include_manifest: bool = False) -> dict:
    """Read durable stages and per-device progress. Read full manifest for approval; poll summaries thereafter."""
    job = request(f"extras/job-results/{uuid(run_id)}/")
    ledger = job.get("result")
    if not isinstance(ledger, dict) or ledger.get("schema") != "gc-rollout/v1":
        return {"job_result_id": job["id"], "job_status": job["status"], "result": ledger}
    result = {k: ledger.get(k) for k in ("run_id", "stage", "approval_digest", "expires_at", "updated_at",
              "execution_job", "cancel_requested", "completed_waves", "error_type")}
    result["devices"] = {name: {k: value.get(k) for k in ("stage", "applied", "saved", "peer_responding",
                          "synchronized", "observed_at", "error_type")} for name, value in ledger["devices"].items()}
    result["recent_events"] = ledger["events"][-8:]
    result["evidence"] = ledger["evidence"]
    if include_manifest:
        result["manifest"] = ledger["manifest"]
    if ledger.get("execution_job"):
        execution = request(f"extras/job-results/{uuid(ledger['execution_job'])}/")
        result["execution_status"] = execution["status"]
        status = execution["status"]
        if isinstance(status, dict):
            status = status.get("value")
        if status not in {"PENDING", "STARTED", "RETRY", "RECEIVED"} and ledger["stage"] not in {"completed", "failed", "canceled", "reconciled"}:
            result["stage"] = "needs_reconciliation"
            result["message"] = "Worker ended before a terminal ledger update. Do not replay; inspect devices and plans."
    return result


@mcp.tool()
def gc_rollout_cancel(run_id: str, reason: str) -> dict:
    """Queue cooperative cancellation on the configured control worker. Does not forcibly kill a push or roll it back."""
    return submit("GC_ROLLOUT_CANCEL_JOB_ID", {"run_id": uuid(run_id), "reason": reason})


if __name__ == "__main__":
    mcp.run(transport="stdio")
