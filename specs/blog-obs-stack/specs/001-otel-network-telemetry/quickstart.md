# Validation Guide: Unified OTel Telemetry Pipeline (v3)

**Spec**: [spec.md](spec.md) | **Tasks**: [tasks.md](tasks.md)
This is an acceptance procedure, not a claim of execution or a runnable
installation script. Replace prospective queries/component names with
verified pinned-version commands and output references at T044.

## Prerequisites and sequence

Record cluster/mirror/bootstrap prerequisites, secret provisioning, baseline
stability and SNMP access evidence. Implement P1 first per plan.md; SuzieQ
is unnecessary for V0–V3. Commit workload desired state and reconcile via
the existing root app. Device Plans require separate per-run approval.

## V0 — VIP and dependency gate (FR-017/018)

1. Confirm reserved VIP, assigned Service IP, receiver ports, MetalLB pool/
   advertisement and absence of competing ServiceLB ownership.
2. From a host on each subnet, send distinct tagged test traffic to all
   three ports and observe receipt at Collector listeners. A successful
   generic UDP send command, ping or allocated IP is not receipt evidence.
3. Exercise a controlled negative path and verify failed hook/health status
   blocks rollout. Test a stalled prerequisite's effect on initial app sync.
4. Restore the declared path and verify success before any device export.

## V1 — Useful collection and bounded delivery (SC-001)

1. Read back existing SNMP access. Generate a canary selection from Nautobot.
   Deploy fresh approved Plans to one device per platform.
2. Verify SNMP interface status/in-out octets/errors/uptime in VM at 60s
   polls; decoded NetFlow/sFlow and syslog in VL, with identity and required
   fields. Confirm useful interface/raw-flow/syslog Grafana panels.
3. Record source export counters with their units, Collector accepted/decoded
   counts, backend counts, restart/template/decode errors and clock basis.
   Distinguish datagrams from records and sFlow samples from packets.
4. Use tagged/known input where source counters cannot support exact parity.
   Record limitations rather than asserting exported == stored universally.
5. After explicit canary confirmation, approved fleet rollout repeats this
   across 28 devices for at least 30 minutes. Missing polls/records remain
   visible gaps, not zero traffic.

## V2 — Closed-window accounting and failures (SC-003/004)

1. Fix input unit, window [start,end), grouping/schema, duplicate policy and
   settling interval inside 14d raw retention.
2. Compare stored raw record counts with derived counts using that same
   definition. Rate/increase extrapolation is not exact count evidence.
3. Test duplicate/late input and overflow; then Collector restart and each
   backend outage independently. Record queue/retry limits, connector-state
   behavior, replay and reconciliation outcomes for affected windows.
4. Require equality after successful reconciliation; mark incomplete or
   mismatched windows with errors. Verify raw records survive metric failure.
5. Repeat for enabled enrichment paths. Verify raw links inside retention
   and explicit expired detail outside it; older metrics remain accessible.

## V3 — Storage and traffic interpretation (SC-002)

Measure the same 24-hour workload: raw bytes, derived bytes, cardinality,
duplicates/gaps, replicas, queues and total footprint. Report actual ratio
against the 10x representation target and projected capacity for 14d logs/
547d metrics. An unmet target remains open.

Validate SNMP utilization/error panels against device counters. Flow counts
are record rates, not bandwidth; any sampled estimate must disclose its
sampling/units and be checked separately.

## V4 — SuzieQ state (SC-005)

After P1, deploy SuzieQ with generated inventory, securely resolved existing
credentials and explicit state retention/cleanup. Verify four state tables
across 28 devices for two cycles. Test device exclusion, authentication
failure isolation, rotation and cleanup. Check presence/authentication
without dumping secrets or container environments.

## V5 — SuzieQ Grafana (SC-006)

Verify four Infinity tables with device/namespace filters and VM trends.
Cross-check Established/not-Established and advertised/received route facts
against actual same-cycle source data; generic route row counts are not
equivalent. Use an approved state change or observed event and verify
visibility after the next poll/bridge cycle with freshness/error context.

## V6 — Optional enrichment (FR-012)

Verify disabled baseline, pinned local MaxMind resolution, missing/stale DB,
bounded ipinfo.io fallback, timeout, unresolved public IP and private IP.
Every branch stores/counts its records. Missing credentials/data must not
prevent baseline Collector startup. Disabled enrichment records enabled-path
tests as N/A, never as executed passes.

## V7 — Reproducibility (SC-007)

From documented prerequisites, reproduce the declared workloads and
generated config; verify a no-change regeneration/sync has no diff.
Include chart/CRD compatibility, health-gated dependencies, Secret ownership,
retention/PVC placement and resource footprint. Root-app alone does not
provision the prerequisite cluster/mirror/secrets or approve device Plans.

## Evidence record

For each V0–V7 / SC-001–SC-007 entry, record date/time/window, commits,
chart/image versions, fleet scope, exact query/command, redacted output,
observed values, expected values, and pass/fail/N/A with limitations.
No pipeline validation has been performed by this documentation revision.
