# Feature Specification: Unified OTel Telemetry Pipeline (v3)

**Feature Branch**: `001-otel-network-telemetry`
**Created**: 2026-09-07 | **Reconciled**: 2026-09-09
**Status**: Draft — architecture aligned; feasibility gates remain open
**Authority**: [Kiro requirements](../../../../../.kiro/specs/network-telemetry-pipeline/requirements.md)

## Overview and scope

Build on Argo CD, Longhorn, VictoriaMetrics and Grafana. Nautobot generates
per-device configuration; Golden Config delivers device CLI;
`blog-sandbox-argo-cd` delivers Kubernetes workloads. OTel polls SNMP and
receives IOS-XE NetFlow, EOS sFlow and syslog. VictoriaMetrics stores metrics;
VictoriaLogs stores decoded flow records and syslog. SuzieQ adds SSH-polled
state and Grafana visibility after the P1 collection and accounting slices.

Network_Fleet is 28 devices: 13 IOS-XE (Border-Router 1, CE-Router 3,
P-Router 4, PE-Router 3, Route-Reflector 2) and 15 EOS (Leaf 9, Spine 6).
Nautobot's 38 total devices include 10 Server-role Ubuntu VMs excluded here.
Protocol assignments describe this lab's images, not universal vendor
capability claims.

Syslog and a MetalLB-advertised Telemetry_VIP are required. The VIP serves
separate NetFlow, sFlow and syslog UDP ports and must be reachable from
management `192.168.3.0/24` and server `192.168.100.0/24`. The actual path
remains to be proven; advertisement cannot be assumed to create routing.

Alert rules, LLM/NetClaw investigation and additional external sources are
follow-on work. Optional enrichment uses local MaxMind first, with bounded
ipinfo.io fallback. SuzieQ is P2 and does not block P1 collection.

## Existing state and evidence boundary

- SNMP context/templates/compliance and Longhorn/VM Applications exist.
  Reuse them; no duplicate SNMP feature or exporter is needed.
- The [2026-09-09 live audit](evidence/2026-09-09-baseline/README.md) found
  no SNMP configuration on 26 readable devices; two SSH read-backs timed out.
  All 28 SNMP polls timed out. Fleet collection is not established.
- Collector, VictoriaLogs, MetalLB, SuzieQ, generated inventories and network
  dashboards are planned work, not established deployments.
- K3s timer changes omit the cloud-controller-manager in the failure log and
  only applied at installation in the original baseline. The cloud-controller
  runtime mitigation was [rolled out on 2026-09-09](evidence/2026-09-09-stabilization/README.md).
  Readiness passed; fabric/storage and the stability window remain open.
- New workloads target DC-B/DC-C. Check rendered tolerations/placement;
  the DC-A taint alone is insufficient evidence for every chart component.

## Data and delivery contract

SNMP samples are metrics in VM without deliberate pre-storage aggregation.
Decoded flow records and syslog are logs in VL. This does not claim packet
capture fidelity or preservation of every vendor wire field: required fields
must be checked against the pinned receiver and canary exports.

Logs retain **14 days**; all feature metrics retain **547 days**
(approximately 1.5 years), using shared store settings. SuzieQ's Parquet
store is an explicit exception, solely for polled network state. Document
its retention/cleanup and capacity before its fleet rollout.

Measure device export, Collector acceptance and each backend separately.
UDP delivery is not guaranteed. Bounded retries, visible loss and explicit
unknown intervals are required. Document persistent queue capacity,
connector state, duplicates, timestamps, late arrivals and reconciliation.

Derived flow counts must match raw records for the same closed window and
grouping **within raw retention**, after a defined settling interval and
under the same duplicate policy. Raw lookup expires after 14 days, while
metrics remain queryable. Independent exporter fan-out does not establish
atomic raw/metric storage; failure/recovery behavior is an implementation gate.

Count equality measures record accounting, not bandwidth fidelity. Initial
panels use SNMP for utilization, errors and operational status. Flow panels
show record rates and retained raw conversations with available byte/packet
and sampling fields. Any sampled traffic estimate identifies units,
weighting and limitations.

## User stories and acceptance scenarios

### US1 — Network collection and useful dashboards (P1)

- **Given** generated configuration for one IOS-XE and one EOS canary,
  **when** approved device export is enabled, **then** SNMP metrics appear
  in VM and NetFlow/sFlow/syslog appear in VL with device identity.
- **Given** probes from both subnets, **when** tagged traffic is sent to
  each VIP receiver port, **then** receipt is verified; failure blocks rollout.
- **Given** successful canaries and explicit operator confirmation,
  **when** the remaining fleet is deployed via approved Config Plans,
  **then** applicable devices contribute data and failures are visible.
- **Given** a poll or backend failure, **when** Grafana refreshes, **then**
  unknown intervals are distinguishable from zero traffic.

### US2 — Accountable flow reduction (P1)

- **Given** closed windows inside raw retention, **when** raw and derived
  counts use identical grouping/duplicate policy, **then** counts agree
  and mismatches identify the window/group.
- **Given** restart or either backend outage, **when** recovery completes,
  **then** reconciliation accounts for duplicates/gaps; incomplete windows
  are not presented as verified zero.
- **Given** older metrics, **when** raw drill-down is requested, **then**
  expired detail is labeled while retained metrics remain available.
- **Given** a measured 24-hour workload, **when** storage is compared,
  **then** the report includes representation ratio, total footprint,
  cardinality and fidelity limitations. Tenfold reduction is a target.

### US3 — SuzieQ state history (P2)

- **Given** Nautobot-generated inventory and securely resolved existing
  CISCO_SSH/ARISTA_SSH credentials, **when** two poll cycles complete,
  **then** BGP/LLDP/route/interface tables cover the fleet.
- **Given** inventory/credential changes, **when** generation/sync runs,
  **then** new values take effect without hand-edited device lists.
- **Given** one authentication failure, **when** polling continues,
  **then** other devices proceed and prior state retains age/error context.

### US4 — SuzieQ in Grafana (P2)

- **Given** SuzieQ state, **when** Grafana opens, **then** four Infinity
  tables support device/namespace filtering.
- **Given** a verified state change, **when** the next poll/bridge cycle
  completes, **then** BGP Established/not-Established trends reflect it.
- **Given** advertised/received route metrics, **when** checked, **then**
  they match those specific device facts. Generic RIB row counts must not
  be substituted; platform/API support is a design gate.

### US5 — Optional enrichment (P3)

- **Given** enrichment enabled, **when** MaxMind resolves an address,
  **then** versioned geographic/ASN context accompanies the record.
- **Given** a missing/stale database or miss, **when** bounded ipinfo.io
  fallback also fails, **then** store/count the record without attributes.
  Private-use addresses are not enriched.
- **Given** resolved, fallback, unresolved or disabled paths, **when**
  accounting runs, **then** every path contributes under the same
  duplicate policy, without bypassing counting.

## Functional requirements

| ID | Requirement | Kiro mapping |
|----|-------------|--------------|
| FR-001 | Collect 60-second SNMP metrics and NetFlow/sFlow/syslog with identity and measured delivery. | 4, 5, 10, 13 |
| FR-002 | Use chart-plus-Git-values Applications and Git-managed supporting resources; no direct child deployment. | 1 |
| FR-003 | VM/VL native OTLP only for metrics/logs; SuzieQ state and delivery queues are explicit exceptions. No Prometheus remote-write, Loki, ServiceMonitor or PodMonitor dependency. | 2 |
| FR-004 | Shared VL retention 14d, VM retention 547d; size from measurements. | 6.4 |
| FR-005 | Generate device lists from Nautobot; failed/empty queries preserve previous output and fail. Never commit resolved secrets. | 3, 4 |
| FR-006 | Count connector plus verified window/group reconciliation and failure semantics. | 6, 13 |
| FR-007 | Raw drill-down within retained 14-day windows only; metrics outlive raw detail. | 6.2, 13.5 |
| FR-008 | Fresh Golden Config Plans, per-run approval, Fail Job on Task Failure and verified failure/rollback behavior. | 5 |
| FR-009 | One canary per platform, verification, explicit confirmation, then fleet. | 5.8 |
| FR-010 | SuzieQ uses existing credentials, generated inventory, documented cadence and bounded state storage. | 8, 2.3 |
| FR-011 | Infinity tables and OTLP bridge; verify advertised/received route semantics. | 9 |
| FR-012 | Optional licensed/pinned MaxMind-first enrichment, bounded ipinfo.io fallback and complete counting paths. | 7 |
| FR-013 | Measure representation ratio and total footprint; separate record accounting from traffic fidelity. | 13 |
| FR-014 | Expose ingestion, decode/drop/errors, lag, queues, poll age, growth and reconciliation status. | 2.6, 13 |
| FR-015 | Existing lint/render/Batfish validation with applicable role mocks. | 11 |
| FR-016 | External sources: SNMP, NetFlow, sFlow, syslog. Internal health/bridge OTLP is not general application ingestion. | 10 |
| FR-017 | MetalLB, reserved/pinned VIP, ServiceLB ownership and receipt gate from both subnets. | 12 |
| FR-018 | Child Application health/readiness plus waves; prove stalled dependency blocks consumers. | 1.4, 12.6 |

## Success criteria

- **SC-001**: Canary then 28-device coverage, useful panels, and a documented
  30-minute source/acceptance/storage accounting run. State units, gaps,
  duplicates and source-counter limits; datagrams are not flow records.
- **SC-002**: A 24-hour storage report, targeting derived representation at
  least 10x smaller than raw, with actual ratio and total footprint.
  An unmet target stays unmet and prompts measured tuning/review.
- **SC-003**: Closed-window equality plus outage/restart recovery evidence,
  including overflow and enrichment paths, within retained raw data.
- **SC-004**: Raw query links inside retention and explicit expiry beyond it,
  with schema/grouping version recorded.
- **SC-005**: SuzieQ's four state tables over two cycles across the fleet;
  unsupported facts remain gaps, not successes.
- **SC-006**: Four Infinity tables and verified BGP/route trends.
- **SC-007**: Documented prerequisites/bootstrap reproduce workloads;
  no-change generation/sync produces no drift. Cluster provisioning,
  mirror, secrets and device approvals are explicit prerequisites.

## Open design gates

See [plan.md](plan.md) and [quickstart.md](quickstart.md): VIP topology and
ServiceLB ownership, pinned components, count/replay semantics, credential
resolution, SuzieQ route facts/retention, and storage capacity need proof.
Constitution Principle VI's complete-ingestion and retained-detail wording
needs explicit review against bounded UDP delivery and unequal retention;
do not record an unconditional PASS.
