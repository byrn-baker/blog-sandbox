# NetClaw adapter for the Golden Config rollout Jobs

The adapter is a standalone stdio MCP server. It is ready to register after the
Nautobot Jobs have been synchronized, enabled, assigned queues and validated.
It is not automatically installed into OpenClaw or substituted for other MCPs.

Create a dedicated environment from this directory's `requirements.txt`; launch
`server.py` with that environment's Python interpreter. Use environment variables:

```dotenv
NAUTOBOT_URL=http://your-nautobot-host:8080
NAUTOBOT_TOKEN=your-scoped-token
GC_ROLLOUT_PREPARE_JOB_ID=uuid-of-Prepare-GC-Rollout-job
GC_ROLLOUT_EXECUTE_JOB_ID=uuid-of-Execute-GC-Rollout-job
GC_ROLLOUT_CANCEL_JOB_ID=uuid-of-Cancel-GC-Rollout-job
# For HTTPS with a private CA, optional:
NAUTOBOT_CA_BUNDLE=/absolute/path/to/ca-bundle.pem
```

Use **Job UUIDs**, not JobResult UUIDs, in these variables. Obtain them from the
Nautobot Jobs UI or `/api/extras/jobs/` after registration. The adapter does not
auto-discover by display name or silently select a different job. It verifies
TLS by default and has no skip-verification option. It inherits only what its
launcher supplies; it does not load `.env` itself.

Example MCP registration structure (adapt to your launcher):

```json
{
  "command": "/absolute/path/to/rollout-mcp-venv/bin/python",
  "args": ["/absolute/path/to/blog-sandbox/integrations/gc_rollout_mcp/server.py"],
  "env": {
    "NAUTOBOT_URL": "http://your-nautobot-host:8080",
    "NAUTOBOT_TOKEN": "SUPPLY-USING-YOUR-SECRET-LOADER",
    "GC_ROLLOUT_PREPARE_JOB_ID": "PREPARE-JOB-UUID",
    "GC_ROLLOUT_EXECUTE_JOB_ID": "EXECUTE-JOB-UUID",
    "GC_ROLLOUT_CANCEL_JOB_ID": "CANCEL-JOB-UUID"
  }
}
```

Do not commit a real token. In NetClaw, use the existing managed launcher pattern
to supply only these variables from the private credential store.

## Agent instructions to load for a rollout

1. Complete the established modeled-source/CI/Batfish/review workflow. Supply
   existing ConfigPlan IDs and compliance features covering the change. The
   coordinator accepts arbitrary literal configuration plans; no NTP-specific
   parameters or profile selection are needed.
2. Call `gc_rollout_prepare(spec)` once. Poll `gc_rollout_status(run_id, true)`
   until preparation succeeds. Present its exact commands, canaries/waves,
   deployment and compliance gates, CI and rollback references, and digest for approval.
3. Only after explicit operator approval, call
   `gc_rollout_start(run_id, approval_digest, approval_reference)` once.
4. Poll `gc_rollout_status(run_id)` every 15–30 seconds. Report transitions and
   time spent in the selected verification gates. Do not invent a new script or open a
   second orchestration loop. Do not equate queued/running with success.
5. Call `gc_rollout_cancel(run_id, reason)` for a cooperative stop, then observe
   its cancellation JobResult and the run ledger. The cancel Job needs its own
   available control worker. An acknowledged request may still be queued.
6. For any `needs_reconciliation` state, stop. An administrator must reconcile
   device state; never clear claims or automatically regenerate/redeploy plans.
7. If a start request times out, inspect state and recent execution JobResults
   before doing anything else. HTTP calls are not automatically retried.

The preparation JobResult is the stable run ID. A start/cancel operation also
returns its own JobResult ID, which `gc_rollout_status` can inspect for queue/job
completion. Pending starts may not yet appear in the preparation ledger; keep
both IDs. The full evidence remains in the preparation JobResult and execution
logs, even if NetClaw restarts.

See `jobs/gc_rollout/README.md` for installation, exact schema, scope and recovery.

Status includes wave counts, phase timing events and an execution-log URL. Report
transitions without launching a duplicate SSH, save or NTP polling loop. The
coordinator reuses Golden Config's built-in Jobs for each approved batch.
