# Tasks: Unified OTel Telemetry Pipeline (v3)

**Date**: 2026-09-09 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)
All implementation tasks remain unchecked. IDs are retained for continuity,
but v1/v2 descriptions and execution order are superseded. Execute by phase,
not numerical ID: T009 is deliberately deferred to P2. Wave numbers and
Application filenames are defined once in plan.md.

## Phase 0 — Baseline and design gates

- [ ] T001 Reconcile baseline evidence and record constitution compliance.
  Baseline read-back/polls recorded in [the audit](evidence/2026-09-09-baseline/README.md);
  SNMP deployment is not established. [The pyATS baseline and TCP trace](evidence/2026-09-09-pyats-baseline/README.md)
  records 25 completed device checks, outstanding collection failures and transport gaps.
  [The evening hop trace](evidence/2026-09-09-hop-latency/README.md) localizes
  oversized VXLAN loss at the DC-A spine. The [approved GRO canary](evidence/2026-09-09-gro-canary/README.md)
  removed oversized packets on the treated path; GRO was restored, and persistent
  repair and residual latency remain open. [Source integration](evidence/2026-09-10-gro-integration/README.md)
  passed local and Batfish checks; persistent device deployment is not yet performed. Track
  K3s cloud-controller-manager flags and managed runtime updates, verify
  effective settings and a documented stability window before extra load.
  Record Principle VI interpretation or required amendment without claiming
  PASS prematurely. Verify: evidence links and explicit open/closed gates.
  Maps: FR-001, FR-008, FR-014; constitution II/VI.
- [ ] T002 Document deployment prerequisites in both repositories: cluster,
  mirror, credentials, existing root/child apps and working-tree baseline.
  Verify: clean checkout instructions distinguish prerequisites from new
  workloads; preserve unrelated inventory edits. Maps: FR-002, SC-007.
- [ ] T003 Pin/mirror charts, images, plugins and generator dependencies;
  validate the chosen Collector binary's components, flow field coverage,
  resource settings and rendered configuration. Verify: rendered charts and
  pinned-binary validation output; no guessed receiver types. Maps: FR-001,
  FR-002, FR-012; constitution V.
- [ ] T004 Implement/document child Application health gating and dependency
  order in bootstrap values and apps/README.md. Verify: stalled Longhorn or
  other prerequisite blocks dependent initial deployment; test update
  behavior separately. Maps: FR-018, SC-007.

## Phase 1 — Stores, VIP and generated Collector configuration

SuzieQ is not a dependency of this phase or US1/US2.

- [ ] T005 Add values/victorialogs-values.yaml and update shared VM values
  for 14d logs/547d metrics. State chart fields explicitly; measure capacity
  before fleet rollout rather than assuming the existing 20Gi PVC fits.
  Verify: rendered retention/storage and initial capacity budget.
  Maps: FR-003, FR-004, FR-013.
- [ ] T006 Add MetalLB and VictoriaLogs Applications per plan.md; resolve
  K3s ServiceLB ownership through managed infrastructure configuration.
  Verify: healthy controllers, explicit placement, correct CRDs/StorageClass
  and no competing Service ownership. Maps: FR-002, FR-017, FR-018.
- [ ] T007 Build values/otel-collector-values.yaml: generated 60s SNMP
  metrics → VM, NetFlow/sFlow/syslog logs → VL, internal health → VM.
  Include explicit requests, queue capacity/persistence, retries and error
  visibility. Verify: pinned-binary config validation and required fields
  from fixtures; no unsupported raw-SNMP-to-logs path. Maps: FR-001,
  FR-003, FR-014, FR-016.
- [ ] T008 Add telemetry-config and Collector Applications per plan.md;
  source generated non-secret config through Git and ready Secret refs.
  Reserve VIP in Nautobot, pin Service/pool to it, configure distinct UDP
  ports. Verify: rendered references and dependency order. Maps: FR-002,
  FR-005, FR-017, FR-018.
- [ ] T010 Implement config_generator and queries/network_fleet.gql from
  Nautobot roles/platforms/primary management IP/context/credential refs.
  Generate sorted SNMP receivers and pipeline membership; canary selection
  filters query results. Verify: fixture render and deterministic rerun.
  Maps: FR-001, FR-005.
- [ ] T011 Test generator removal/re-role/context exclusion and failed/empty
  query handling. Validate before publishing all outputs atomically; retain
  previous outputs on failure. Verify: meaningful fixture/failure tests
  with unchanged prior artifacts and no hardcoded fleet. Maps: FR-005.
- [ ] T012 Expose ingestion/decode errors, drops, queue usage, retry
  exhaustion, restart counts, per-device freshness and storage growth.
  Verify: tagged test input and a failure produce operator-visible signals;
  do not confuse retry errors with terminal drops. Maps: FR-014.
- [ ] T013 Document/implement secure SNMP secret resolution from existing
  context authority, no independently maintained community; add redacted
  templates and Argo Secret ownership rules. Verify: resolved values stay
  out of generated Git artifacts and logs. Maps: FR-005, FR-008.
- [ ] T014 Commit new desired state and let the existing root app reconcile.
  Provision fixed-UID VM/VL Grafana datasources and initial interface,
  raw-flow, syslog and collection-health panels. Verify: services/PVCs,
  chart placement and panel queries. No direct child kubectl apply.
  Maps: FR-002, FR-004, FR-014, SC-001.
- [ ] T015 Validate synthetic metric/log delivery using the pinned test
  configuration or isolated internal test path, then remove test-only
  receivers. Verify records in correct stores and no unintended external
  ingestion endpoint. Maps: FR-001, FR-003, FR-016.
- [ ] T021 Prove the VIP path before device enablement: tagged traffic from
  each subnet to each receiver port, observed at the Collector. Implement a
  PostSync hook/health gate surfacing failure and verify a negative case.
  If Kiro 12.5 cannot be met, stop dependent rollout and revise topology
  constraints; do not add untracked routing/NAT. Maps: FR-017, FR-018.

## Phase 2 — US1: useful canary collection, then fleet

Dependencies: phase 1 gates passed, particularly T021.

- [ ] T016 Add IOS-XE Flexible NetFlow template/includes, with supported
  interface/VRF/export version settings. Verify: lint/render/Batfish plus
  planned canary CLI review. Maps: FR-001, FR-008, FR-015.
- [ ] T017 Add EOS sFlow template/includes and validate actual image/VRF
  syntax. Verify: lint/render/Batfish and planned canary CLI review.
  Maps: FR-001, FR-008, FR-015.
- [ ] T018 Add role-appropriate flow/syslog contexts and platform logging
  templates as needed, using the reserved VIP as one source of truth.
  Reuse existing logging machinery where present. Verify: all applicable
  roles render correct destination/ports and scope. Maps: FR-001, FR-017.
- [ ] T019 Update all seven role mock contexts and assertions for introduced
  variables. Verify: make ci and make ci-full, no unintended device config
  changes. Maps: FR-015.
- [ ] T020 Extend the actual compliance loader
  jobs/gc_compliance_setup/__init__.py for NetFlow/sFlow and reuse logging
  rules; no duplicate stale YAML feature tree. Verify: intended config is
  matched including relevant ACL/export parents. Maps: FR-008, FR-015.
- [ ] T022 Generate fresh intended/backup/compliance data and Config Plans;
  obtain per-run approval, enable Fail Job on Task Failure, deploy exactly
  one queried device per platform. Verify actual export, SNMP, required
  fields and Grafana panels with V1. Confirm rollback/failure handling and
  no automatic retry; do not assume a job failure reverts partial CLI.
  Maps: FR-008, FR-009, SC-001.
- [ ] T023 Obtain explicit operator confirmation of both canaries before
  expansion, then deploy approved fleet Plans. Verify per-device read-back,
  poll/export receipt and failure reporting. Maps: FR-009, SC-001.
- [ ] T024 Record at least 30 minutes of source/Collector/backend accounting,
  units, duplicates, decoder/template misses, poll gaps and panels for the
  full fleet. Verify V1; do not equate datagrams to records or claim universal
  losslessness. Maps: FR-001, FR-014, SC-001.

## Phase 3 — US2: count accounting and measured reduction

- [ ] T025 Prototype then implement count conversion with documented
  timestamps, window boundaries, lateness, duplicate identity/policy and
  replay/reconciliation strategy. Verify raw/count equality for closed
  retained windows. Treat independent exporter success as insufficient.
  Maps: FR-006, FR-007, SC-003, SC-004.
- [ ] T026 Bound metric grouping/cardinality and specify overflow counts.
  Keep raw IDs, unbounded 5-tuples and absolute window times out of metric
  labels. Verify low-cap overflow preserves accounting. Maps: FR-006, FR-013.
- [ ] T027 Test Collector restart, duplicate input, late input and each
  backend outage separately. Verify recovery within documented bounds,
  raw records unaffected by metric failure, and window/group error status;
  persistent exporter queues are not connector-state persistence.
  Maps: FR-006, FR-014, SC-003.
- [ ] T028 Implement fidelity/storage report and drill-down contract.
  Verify identical source windows/grouping/schema/duplicate semantics,
  expiry handling, raw/derived bytes and total footprint. Never use
  extrapolated rate queries as exact count proof. Maps: FR-007, FR-013.
- [ ] T029 Run 24-hour measurement, record actual representation ratio
  against 10x target and size shared 14d/547d stores with replicas/overhead.
  Verify V2/V3; unresolved mismatch or capacity remains open, not PASS.
  Maps: FR-004, FR-013, SC-002–SC-004.

## Phase 4 — US3: SuzieQ state (P2)

- [ ] T009 Add SuzieQ Application/values per plan.md using a pinned chart
  or mirrored local chart. Poller/REST may share a PVC in one pod; bridge
  is part of the declared workload. Define state retention/cleanup and
  capacity before fleet polling. Verify render, mount access and supported
  API/schema. Maps: FR-002, FR-010.
- [ ] T030 Extend generator for SuzieQ sources/devices/auths/namespaces from
  the same Nautobot query. Verify fixture output and references to existing
  credential authority, without resolved secrets. Maps: FR-005, FR-010.
- [ ] T031 Implement secure existing-credential resolution, Secret rotation
  and inventory mounts with declared ownership. Verify authentication and
  rotation without logging values; failed query/sync preserves prior state.
  Maps: FR-005, FR-010.
- [ ] T032 Verify BGP/LLDP/route/interface state for all 28 devices over two
  cycles; document cadence, age and per-device errors. Verify V4, no silent
  success for unsupported tables. Maps: FR-010, SC-005.
- [ ] T033 Verify device removal/re-role, authentication failure isolation,
  and retention cleanup preserves expected history. Maps: FR-005, FR-010.

## Phase 5 — US4: SuzieQ Grafana visibility (P2)

- [ ] T034 Pin/provision Infinity and datasource authentication via Secret,
  with fixed UID and device/namespace filters. Verify table queries without
  exposing API keys. Maps: FR-011.
- [ ] T035 Implement OTLP bridge using verified SuzieQ fields: Established/
  not-Established BGP and per-device advertised/received routes. If facts
  are unavailable, resolve required collection or revise the requirement;
  do not rename generic RIB counts. Verify device/API/VM agreement.
  Maps: FR-010, FR-011.
- [ ] T036 Provision four state tables and trend panels plus freshness.
  Verify Grafana matches same-cycle SuzieQ state. Maps: FR-011, SC-006.
- [ ] T037 Use an approved controlled state change or observed event to
  cross-check tables/trends by the next poll/bridge cycle; do not introduce
  an unapproved device write path. Verify V5. Maps: FR-008, FR-011, SC-006.

## Phase 6 — US5: optional enrichment (P3)

- [ ] T038 Add default-off MaxMind-local enrichment and bounded ipinfo.io
  fallback for misses/missing/stale DB; private addresses bypass lookups.
  Ensure all branches rejoin storage/counting. Verify pinned component
  capability before committing configuration. Maps: FR-012.
- [ ] T039 Add secure license/API-key references, pinned dataset revision,
  refresh/staleness policy and fallback timeout/cache/rate limits.
  Verify absent Secrets cannot prevent baseline Collector startup.
  Maps: FR-012, FR-014.
- [ ] T040 Verify disabled, resolved, fallback-success, timeout and unresolved
  paths all store/count records with no indefinite delay. Verify V6 and
  repeat V2 accounting. Maps: FR-006, FR-012, SC-003.

## Phase 7 — Documentation and final acceptance

- [ ] T041 Finish interface/flow/syslog/health dashboards, units, unknown
  intervals and expired raw links. Initial panels already exist at T014.
  Verify useful traffic questions without conflating counts/volume.
  Maps: FR-007, FR-013, FR-014.
- [ ] T042 Document tested query surfaces for follow-on alerts/LLM, without
  implementing new sources or workflows. Maps: FR-016.
- [ ] T043 Update demo-lab/series notes to deployed reality: Part 7 foundation,
  next telemetry slice, later SuzieQ. Verify device count/evidence wording.
  Maps: SC-007.
- [ ] T044 Replace all prospective query/component/schema choices in
  quickstart/data-model/contracts/research with validated versions and
  evidence links. Verify no historical design example is treated as proven.
  Maps: FR-001–FR-018.
- [ ] T045 Run make ci/full validation for changed code and V0–V7 as
  applicable; record SC-001–SC-007 evidence. Optional enrichment disabled
  is explicit N/A for enabled-path tests, not claimed completed.
  Maps: FR-015, SC-001–SC-007.
- [ ] T046 Reproduce from documented prerequisites and verify no-change
  generation/Argo sync, including stalled-dependency/failed-reachability
  checks. Maps: FR-002, FR-018, SC-007.
- [ ] T047 Record CPU/RAM, queue/state/PVC growth, replicas and retention
  capacity for all components. Verify budget at observed ingest rate.
  Maps: FR-004, FR-013; constitution V.

## Execution discipline

P1 is phases 0–3; P2 is phases 4–5; P3 is optional phase 6. Final acceptance
includes only enabled scope with explicit evidence. No live task is complete
on rendered YAML alone. Required device approval is per deployment run and
is not granted by approval of these documentation changes.
