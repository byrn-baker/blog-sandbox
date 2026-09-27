# Golden Config rollout coordinator

These four Nautobot Jobs add durable canary/wave sequencing around Golden
Config's existing operations. They target Nautobot 3.2.1 / Golden Config 3.0.7.
The MCP adapter submits Jobs and reports progress; Nautobot owns execution.

## Reused operations

For each approved batch the coordinator calls:

1. `DeployConfigPlans.run(..., fail_job_on_task_failure=True)`.
2. `BackupJob.run(...)`.
3. `ComplianceJob.run(...)`.

Golden Config owns plan consolidation, platform dispatch, credentials, device
connections, concurrency, postprocessing, saves, backups, compliance computation,
Git persistence and device deployment statuses. The coordinator requires every
selected plan to reach Completed and checks that fresh backup/compliance evidence
exists and every selected compliance rule passes before starting the next wave.
The built-in operations share the coordinator's execution request/JobResult;
they are called inline, without waiting for nested Celery Jobs.

There is no custom SSH engine, command parser, NTP timer, repeated preflight
backup or extra connection pool. Any literal ConfigPlan commands are supported
on platforms supported by the configured Golden Config dispatcher. Multiple
plans on one device are passed together to Golden Config.

## Added orchestration

- **Prepare GC Rollout** binds reviewed plan contents, source, intended config,
  compliance rules, canaries/waves and runtime versions to an approval digest.
- **Execute GC Rollout** executes that approved sequence and stops expansion on
  failure. Each wave gets one deployment, one backup and one compliance pass.
- **Cancel GC Rollout** requests cooperative cancellation between operations.
- **Reconcile GC Rollout** lets an administrator close an interrupted run after
  confirming worker termination and reconciling devices. Claims remain intact.

The preparation JobResult is the stable run ID and durable ledger. Its Nautobot
status remains SUCCESS; `result.stage` describes the rollout. Execution has a
separate JobResult containing Golden Config's logs. Events record phase durations,
wave completion and evidence references. No automatic deployment retry or rollback
is performed. A claimed plan must not be replayed after a worker interruption.

## Preparation input

Complete the modeled-source/CI/Batfish workflow, source synchronization, intended
config generation, backups and plan review first. Submit this JSON as `spec_json`:

```json
{
  "plan_ids": ["PLAN-UUID-1", "PLAN-UUID-2"],
  "source_repository": "GITREPOSITORY-UUID",
  "source_commit": "FULL-40-CHARACTER-SYNCHRONIZED-COMMIT",
  "ci_evidence": "Passing CI/Batfish evidence for this revision",
  "rollback_reference": "Reviewed rollback procedure and baseline evidence",
  "change_control_id": "lab-change-YYYYMMDD",
  "canaries": ["CE1", "DCA-Leaf01"],
  "parallel_canaries": true,
  "wave_size": 6,
  "feature_ids": ["CHANGED-COMPLIANCE-FEATURE-UUID"]
}
```

Supply 1–64 distinct unused plans. Select exactly one canary per affected platform
network driver. Parallel canaries form one batch; otherwise each canary forms a
separate batch. Subsequent waves contain at most `wave_size` distinct devices
(1–16). Golden Config's Nornir runner determines actual connection concurrency;
the observed lab setting was four workers. This coordinator does not change it.

All plans must have the given change-control ID. Selected compliance features
must cover every feature attached to the plans and have rules for each platform.
For manual plans, the operator must ensure the rules cover the actual commands;
CLI feature coverage is not inferred. Configuration compliance does not establish
protocol convergence, startup persistence or application health. Changes requiring
such gates need additional reviewed checks; none are implied by Completed status.

Review the returned manifest and approve its exact digest. Execute with:

```json
{
  "run_id": "PREPARATION-JOBRESULT-UUID",
  "approval_digest": "EXACT-RETURNED-SHA256",
  "approval_reference": "Operator approval of this digest and wave policy"
}
```

Approval expires one hour after preparation if execution has not claimed it.
Changes to plans, intended config, source or rules require fresh preparation.
CI, rollback and approval references are operator assertions, not independently
verified attestations. Literal commands are required; unresolved Jinja and custom
postprocessing require a separately reviewed integration. Golden Config's builtin
render_secrets is supported only when it preserves the reviewed command text.

The internal manifest profile is `gc-coordinator-v2`. Earlier NTP manifests must
be prepared and approved again. NTP-specific spec keys are no longer accepted.
Old ledgers remain readable and can still be canceled/reconciled.

## Installation and operation

Sync the repository in Nautobot; `jobs/__init__.py` registers all four Jobs.
Enable them and grant run permissions to rollout operators. The executor also
needs change access to every plan and view access to every device. Configure
Execute on an execution queue and Cancel on a control queue with an available
worker. Preparation and reconciliation can share the control queue. Source
execution limits are six hours soft and six hours plus 60 seconds hard; confirm
database overrides have not replaced them.

Use the existing Golden Config inventory, credential provider, platform mappings,
repository settings and worker network access. NetClaw does not need device
credentials to invoke these Jobs. Existing backups and compliance must work.

Keep source and intended inputs fixed during a rollout. For a shared source/output
repository, only the selected devices' exact mapped `.cfg`/`.conf` backup artifacts
may change. The normal Golden Config Git operations persist those artifacts.
Avoid competing ordinary deployment Jobs; they do not honor this coordinator's
rollout lock. Freshness of pre-change device state remains part of plan preparation;
there is no additional live drift check immediately before each wave.

Keep preparation and execution JobResults for the audit retention period and do
not purge active ledgers. Cancellation cannot undo an in-flight push. After an
interrupted worker, establish termination, inspect every claimed device/plan,
record reconciliation evidence, and use Reconcile GC Rollout as an administrator.
Generate fresh plans and obtain new approval for any further deployment.

## NetClaw integration

`integrations/gc_rollout_mcp/server.py` exposes prepare, start, status and cancel.
Those are transport functions suitable for inclusion in the existing Golden
Config MCP; workflow state and wave decisions stay in Nautobot. The standalone
entrypoint is a registration option, not a second deployment implementation.

The expected improvement is fewer agent/tool round trips and no redundant device
verification loop. Phase timings and execution-log links expose where time goes.
No end-to-end speedup has yet been measured for this revision.

## Validation status

Existing isolated tests were adjusted for the coordinator and obsolete NTP/SSH
tests removed. They were not run for this refactor. The previous 69-test result
and preparation-only worker trial apply to the earlier NTP implementation.
This revision still requires worker integration validation before a live rollout.
`tools/validate_gc_rollout_import.py` supports import/registration validation;
it does not execute Jobs or touch devices.
