# Implementation Plan: Unified OTel Telemetry Pipeline (v3)

**Date**: 2026-09-09 | **Spec**: [spec.md](spec.md)
**Status**: Draft; design gates and deployment evidence remain pending.

## Architecture

`blog-sandbox` owns contexts, Jinja, compliance, Nautobot generation and
secure credential integration. `blog-sandbox-argo-cd` owns Applications,
values, generated non-secret resources and dashboards. Where no suitable
chart exists, package a versioned local chart and mirror it.

1. Generated SNMP receivers poll at 60s → OTLP metrics → VM.
2. Devices send NetFlow/sFlow/syslog to reserved MetalLB Telemetry_VIP →
   Collector → OTLP logs → VL.
3. Every flow path feeds count conversion → OTLP metrics → VM.
   Independent raw/count delivery requires proven reconciliation.
4. Later, generated SuzieQ inventory + existing SSH secrets → Parquet
   state history → REST/Infinity; state bridge → OTLP → VM.

SNMP is not serialized to VL. SNMP supplies utilization/error/status panels;
flow-record counts measure accounting/record rates. Logs retain 14d, metrics
547d. SuzieQ is a scoped storage exception with explicit cleanup policy.

## Delivery sequence

| Stage | Deliverable / gate | Tasks |
|-------|--------------------|-------|
| 0 | Baseline evidence, Principle VI review, tracked K3s/runtime and Argo health gaps. | T001–T004 |
| 1 | Pinned component validation, MetalLB path and ServiceLB ownership. | T003, T005–T008, T021 |
| 2 | Generated canary receivers, stores/collector and useful Grafana panels; no SuzieQ prerequisite. | T010–T015 |
| 3 | Approved IOS-XE/EOS canaries; prove SNMP/flows/syslog before fleet. | T016–T024 |
| 4 | Reconciliation, restart/outage evidence, bounded cardinality and storage report. | T025–T029 |
| 5 | SuzieQ, inventory/credentials, state and Grafana bridge. | T009, T030–T037 |
| 6 | Optional enrichment and final reproducibility/evidence. | T038–T047 |

Before device enablement, prove tagged UDP receipt at actual VIP/ports from
both subnets. A cluster-pod probe or assigned Service address is insufficient.
Surface failure through a sync hook or health-gated resource. Do not silently
add routing/NAT outside Kiro 12.5's boundary; report an infeasible path and
revise the constraint before implementing an alternative.

## Proposed Applications and dependency order

These filenames are prospective. Existing Longhorn wave 1 and VM wave 2
remain the foundation.

| Application | Wave | Dependencies |
|-------------|------|--------------|
| 04-metallb.yaml | 3 | Cluster networking and documented ServiceLB ownership |
| 05-victorialogs.yaml | 3 | Healthy Longhorn |
| 06-telemetry-config.yaml | 4 | MetalLB CRDs; owns pool/advertisement and generated non-secret config |
| 07-otel-collector.yaml | 5 | VM/VL, telemetry config, ready Secrets and VIP prerequisites |
| 08-suzieq.yaml | 6 | Longhorn, generated inventory and credential Secrets; deployed in P2 |

Use mirror-chart + Git values for every Application. Add the documented
Application health customization and prove stalled dependencies block
consumers. On later updates, test dependency behavior rather than assuming
waves serialize autonomous child syncs. Connectivity validation can be a
Collector PostSync hook once its Service/listeners exist; never place a
hook before resources it needs.

## Generation and secrets

Publish sorted, deterministic non-secret output from Nautobot GraphQL into
Git. Canary selection filters query results, not a hand-maintained fleet
inventory. Validate all output before atomic publication; failed/empty
queries preserve existing output.

Generate credential references, never values. Design secure resolution from
CISCO_SSH/ARISTA_SSH into workload Secrets, rotation and failed-sync behavior,
plus Argo ownership. A secrets-group name alone is not authentication.
Validate credential presence without logging values or dumping environments.

## Feasibility gates

- Validate the pinned Collector distribution supports SNMP, both flow
  protocols, syslog, count and chosen enrichment. Receiver instance names
  need not equal protocols; validate actual component configuration.
- Define decoded record units/fields and compare to real canary exports.
  Do not assert every wire field is retained.
- Define timestamps/windows, duplicate identity, lateness, restart handling,
  reconciliation and bounded queues. Prototype backend failure before US2.
  Raw data survives metric-path failure; incomplete windows stay visible.
- Keep raw IDs, unbounded 5-tuples and window start timestamps out of metric
  labels. Document overflow aggregation.
- Verify SuzieQ advertised/received-route facts in actual API/device output.
  RIB row count is not a substitute. Verify retention/cleanup.
- Measure capacity for shared 547d VM and 14d VL, Longhorn replicas, queues
  and SuzieQ. Existing 20Gi VM storage is not presumed sufficient.

## Constitution review — conditional, not passed

| Principle | Assessment |
|-----------|------------|
| I — Source of truth | Aligned design; generation/failure evidence pending. |
| II — Verification | Existing code tests passed; new pipeline evidence absent. |
| III — Zero drift | GitOps ownership proposed; health and Secret ownership pending. |
| IV — Read-only telemetry | Existing credentials; device changes via fresh approved Plans. |
| V — Pinning/reproducibility | Versions, mirror, budgets and bootstrap remain tasks. |
| VI — Deliberate reduction | Review complete-ingestion/retention wording against UDP limits and 14d/547d policy. |

The constitution remains v1.1.0, unamended by this revision. T001 records
whether Principle VI requires amendment; if so, follow its governance before
dependent implementation. An unresolved gate is not a completed PASS.

## Complexity and deletion paths

| Addition | Purpose | Removal consequence |
|----------|---------|---------------------|
| MetalLB | Device receiver VIP | Needs an approved replacement path |
| VictoriaLogs | Flow/syslog detail | Removes drill-down/accounting baseline |
| Collector + generator | Collection from Nautobot data | Replacement must preserve signal/generation contracts |
| Reconciliation/report tooling | Detect delivery failures and measure reduction | US2 cannot claim accounting without equivalent evidence |
| SuzieQ + REST + bridge | State history/tables/trends | Entire P2 can be deferred without blocking P1 |
| Enrichment | Optional geographic/ASN context | Removal must leave baseline collection/counting intact |

[Tasks](tasks.md) and [validation](quickstart.md) define evidence. The older
Kiro design is background only; revalidate its examples before use.
