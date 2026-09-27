# Golden Config rollout Jobs

This first version automates **NTP-only** IOS/IOS-XE and EOS rollouts. Deployment is
Golden Config's own `config_deployment()` play; SSH connections opened by the
verification code issue fixed `show` commands only. It targets Nautobot **3.2.1**
and Golden Config **3.0.7** and refuses other versions until reviewed.

## Components

- **Prepare GC Rollout** snapshots existing plans, intended NTP, backup NTP,
  devices/platforms, source HEAD, compliance rules, wave policy and versions.
  It returns a manifest, SHA256 approval digest and a stable run ID.
- **Execute GC Rollout** requires that exact digest and an explicit approval
  reference. It checks live NTP against the reviewed backup, deploys platform
  canaries, verifies them, then proceeds through bounded waves.
- **Cancel GC Rollout** sets a cooperative cancellation flag. It cannot undo an
  in-flight push. It must run on a control queue with an available worker.
- **Reconcile GC Rollout** lets an administrator close an interrupted run after
  establishing worker termination and recording device/plan reconciliation.
  It preserves every claim; it never retries the old run.
- `integrations/gc_rollout_mcp/server.py` exposes prepare, start, status and cancel.
  It contains no device connection or deployment orchestration logic.

## Durable state and recovery

The completed preparation JobResult's `result` is the ledger. Its top-level
Nautobot status stays `SUCCESS` (preparation succeeded); **read `result.stage` for
rollout status**. Execution has its own JobResult and log stream. All ledger
updates use database row locks. Celery never runs the preparation task again.
Do not use Nautobot's rerun/scheduling facilities to replay either Job.

Before each deployment, the runner atomically records the claim and assigns
`ConfigPlan.deploy_result` to the execution JobResult. A crash after this point
is deliberately ambiguous: some or all commands might have reached devices.
There is no automatic retry, continuation, claim clearing or rollback. A
second execution of the same run is rejected. Another active or unreconciled
runner blocks new runners. This protection applies to these Jobs; administrative
use of Golden Config's ordinary deployment Job can bypass it. Do not run competing
deployments or edit selected plans/source/configuration during a rollout.

After worker loss:

1. Read the preparation ledger, execution logs and each claimed Config Plan.
2. Establish that the old worker/task can no longer issue commands. A stale
   `STARTED` JobResult alone is not proof of termination.
3. Read running/startup config and protocol state for **every claimed device**.
4. Record the findings and run Reconcile GC Rollout as an administrator.
5. Generate fresh backups/plans and obtain a new approval for remaining work.

Keep preparation and execution JobResults for the complete audit retention
period (at least longer than the maximum rollout duration). Do not purge an
active ledger. This implementation uses existing database models and requires
no migration. At larger scale, a dedicated app/model is preferable for retention,
indexed rollout queries and richer access control.

## Deployment prerequisites

Implementation is local source until the repository is committed/pushed and the
Nautobot Git repository is synchronized. No deployment has been performed by
adding these files.

1. Review the changes and validate them in the target Nautobot environment.
2. Publish the reviewed repository revision through the normal Git workflow;
   synchronize `blog-sandbox` in Nautobot. The root `jobs/__init__.py` registers
   all four Jobs. Enable them and grant run permissions only to rollout operators.
3. The execution identity needs view access to all selected devices, source Git
   repository and plans; it also needs change access to all selected plans.
   Job run permissions authorize the runner's backup/compliance operations.
4. Put Execute GC Rollout on an execution queue and Cancel GC Rollout on a
   separate control queue with a listening worker. Preparation and reconciliation
   can share the control queue. Do not rely on a single occupied worker to
   process cancellation. Configure Job queues in Nautobot and the worker
   subscriptions to match your deployment.
5. Check the execution Job's singleton and time limits have not been overridden
   in the database. Source defaults are 6 hours soft / 6 hours + 60 seconds hard.
   A timeout stops expansion and may require reconciliation.
6. Use the same Nautobot Nornir credentials/inventory settings as Golden Config.
   Netmiko verification runs **on the Nautobot worker**, not the NetClaw host.
   It needs network reachability and the installed Nornir Netmiko connection
   plugin. It does not read NetClaw's pyATS testbed or `.env`.
   Driver selection comes from each Device Platform's `network_driver_mappings`;
   the supported-platform check selects the NTP verification profile only.
   Usernames/passwords/enable secrets come from Golden Config's configured
   Nornir credential provider (`get_device_creds(device=...)`). The runner
   does not define per-vendor credentials. Confirm the provider resolves the
   existing Nautobot credential data; storing credentials in Nautobot alone
   does not configure a provider to read them.
7. Golden Config backups, intended configs and compliance must already work.
   Postprocessing may be disabled or use only Golden Config's built-in
   `render_secrets` callable. Plans must contain literal NTP commands without
   Jinja markup; preparation renders them and requires identical command text.
   The effective callable sequence is bound into approval. Custom processors
   require a separately reviewed adapter.
   Select actual compliance feature UUIDs with rules on both affected platforms.
8. Preserve intended config inputs during execution. A shared source/output repo
   is supported: preparation records the exact mapped backup file paths for the
   selected devices. Only those `.cfg`/`.conf` artifacts may change. Commits that
   alter source, intended config or other files invalidate approval. The worker
   checkout is checked as well as the database HEAD, including uncommitted files.

The runner invokes normal Golden Config Backup and Compliance Jobs inline;
these include their normal Git sync/commit/push behavior. Those Git credentials
and repository mappings must work on the worker.

## Prepare specification

First complete modeled-source changes, CI/Batfish, source synchronization,
intended generation, fresh backups/compliance and Config Plan review. CI evidence
and rollback references below are operator assertions, not independently checked
CI attestations. The runner does not bypass that review or manufacture approval.

Pass the following JSON shape as `spec_json` to Prepare GC Rollout, replacing the
example UUIDs/commit with actual values. Device names below illustrate the policy;
select exactly one canary per affected platform. Each device must have one unused,
NTP-only plan with the supplied change-control ID.

```json
{
  "plan_ids": ["PLAN-UUID-1", "PLAN-UUID-2"],
  "source_repository": "BLOG-SANDBOX-GITREPOSITORY-UUID",
  "source_commit": "FULL-40-CHARACTER-SYNCHRONIZED-COMMIT",
  "ci_evidence": "Reference to passing CI/Batfish evidence for this commit",
  "rollback_reference": "Reference to the reviewed rollback procedure and baseline evidence",
  "change_control_id": "ntp-change-YYYYMMDD",
  "canaries": ["CE1", "DCA-Leaf01"],
  "parallel_canaries": true,
  "wave_size": 6,
  "ntp_server": "192.168.3.242",
  "timeout_seconds": 1200,
  "poll_seconds": 20,
  "feature_ids": ["NTP-COMPLIANCE-FEATURE-UUID"]
}
```

`parallel_canaries: true` means the two platform canaries are deployed together
and observed concurrently. This choice is part of the digest the operator
approves. `false` runs platform canaries sequentially. All canaries must pass
before fleet waves start. Wave size bounds the number of devices handed to
Golden Config; its configured Nornir runner determines actual push concurrency.
Verification opens at most eight simultaneous SSH sessions.

Read the complete returned manifest before asking for approval. It includes the
exact plan commands and wave membership. Approval expires after one hour if
execution has not claimed it. Once approved, submit Execute GC Rollout with:

```json
{
  "run_id": "PREPARATION-JOBRESULT-UUID",
  "approval_digest": "EXACT-RETURNED-SHA256",
  "approval_reference": "Reference to the operator's explicit approval of this digest"
}
```

The Jobs cannot establish whether a supplied approval reference represents a
human decision; enforce that in operator practice and the caller's tool policy.

## Gates and progress

Stages per device: `deployed` → `applied` → `saved` → `peer_responding` →
`synchronized`, or `verification_failed`. `deployed` alone is not proof of saved
or working configuration. Running and startup NTP lines must exactly equal the
reviewed intended NTP lines. The requested peer must have nonzero reach and be
selected, and the clock must report synchronization. Timeout stops expansion.

Each wave then gets fresh backups and compliance. Every selected rule must have
a passing result for every wave device. Unrelated compliance features are not
used as this rollout's gate. This profile does **not** validate BGP, forwarding,
application health or routing stability; retain independent checks if required
by the change. Add a reviewed verification profile before using the runner for
other changes. NTP acquisition can still take many minutes; concurrent canaries
remove duplicated waiting without declaring unsynchronized clocks successful.

The execution Job logs stage transitions; the preparation ledger includes the
latest NTP output, timestamps, wave completion, approval and evidence IDs. The
MCP status tool returns compact progress by default and the full approval
manifest only when `include_manifest=true`. Callers should report stage changes
to the user rather than waiting silently. Suggested polling interval: 15–30 s.

Cancellation returns a request acknowledgement, not proof the worker stopped.
Poll the ledger until terminal. Avoid Nautobot's force-cancel endpoint during a
configuration push; if forced termination is necessary, reconcile afterward.

## Validation

Run the isolated logic suite with `python -m pytest tests/test_gc_rollout.py -q`.
Django/Nornir services are mocked in these unit tests; the Git cases create real
local repositories. They cover approval, plan/input changes, wave ordering, NTP
parsing, cancellation, interrupted pushes, duplicate runs and backup-only commits.

Use the worker's Python for the real import/registration check:

```sh
python /path/to/blog-sandbox/tools/validate_gc_rollout_import.py
```

The script uses the worker's Nautobot configuration by default; `--config PATH`
selects a different configuration. Registration is in-process only. No Job is
executed, queued or permanently registered by this script.

Validation completed with 69 isolated tests, then imports and a synchronous
preparation-only Job on the actual Nautobot 3.2.1 / Golden Config 3.0.7 worker.
The live trial used temporary copies of completed CE1/DCA-Leaf01 NTP plans; it
produced JobResult `a4606ffc-2a76-4391-83ce-9e1c03268822` successfully. The test
ledger was canceled, temporary plan copies removed, and validation Job disabled.
No device connections or deployments were performed by this trial.

The live credential provider is `CredentialsNautobotSecrets`; inventory resolution
confirmed driver mappings and populated username/password/enable-secret values
for both platforms without printing credentials. The live worker runs Nornir
plugin 3.1.2, nornir-nautobot 4.4.0 and Django 5.2.16.

Production Job installation, asynchronous queue behavior, MCP integration and an
explicitly approved canary deployment remain separate activation gates. Tests do
not grant deployment approval.
