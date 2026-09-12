# Contracts: Unified OTel Telemetry Pipeline (v3)

**Spec**: [spec.md](../spec.md) | **Deployment order**: [plan.md](../plan.md)
These are prospective contracts. Exact service names, metric names, OIDs,
receiver instances and API fields are pinned and verified during tasks.

## C1 — Ingestion and storage

| Source | Endpoint / path | Output |
|--------|-----------------|--------|
| SNMP | Collector → generated device management IP:161, every 60s | OTLP metrics → VM |
| IOS-XE NetFlow v9/IPFIX | Telemetry_VIP UDP 2055 | Decoded logs → VL; record counts → VM |
| EOS sFlow | Telemetry_VIP UDP 6343 | Decoded logs → VL; record counts → VM |
| Syslog, both platforms | Telemetry_VIP UDP 5514 | Logs → VL |
| Internal collector health / SuzieQ bridge | Restricted internal OTLP or internal collection pipeline | Metrics → VM |

Ports are proposed and must match device/Service/receiver renders. No public
general-purpose OTLP ingestion is introduced. VM/VL native OTLP URLs must
be validated for the pinned backend and exporter: avoid accidental duplicate
signal suffixes when setting base versus signal-specific endpoints.

MetalLB owns the reserved/pinned VIP after ServiceLB ownership is resolved.
Prove traffic receipt from both subnets at each UDP port, including a
negative test that fails the rollout gate. Service allocation is insufficient.

## C2 — Query and dashboard contract

Fixed provisioned datasource UIDs identify VM, VL and later SuzieQ-Infinity.
VM provides SNMP utilization/error/status and flow-record-rate panels.
VL provides filtered raw flow/syslog views. Infinity queries authenticated
SuzieQ REST tables; its OTLP bridge supplies verified state trends.

Exact working queries belong in deployment evidence, not guessed wildcard
metric names. Queries must state units, temporality, grouping and timestamp
basis. Raw-detail links share window/group filters and expire after 14d.
Metrics retain 547d. Missing delivery/state is unknown, never a false zero.

## C3 — Count and failure contract

For each closed retained window/group, derived count equals matching raw
record count after settling under identical schema and duplicate policies.
This is record accounting, not packet/byte-volume fidelity.

Collector restart, raw-backend outage and metric-backend outage are separate
tests. Record queue bounds/persistence, retries, terminal drops, late arrivals
and connector state loss. Reconciliation must identify affected windows,
preserve already-stored raw data on metric failure and handle replay without
silent overcounting. Independent exporter fan-out alone does not meet this
contract. Enrichment fallback and overflow paths participate in accounting.

## C4 — Device deployment

Reuse existing SNMP artifacts after verifying access. Add IOS-XE NetFlow,
EOS sFlow and both-platform syslog to existing Golden Config ownership.
Extend actual compliance loader rules, including relevant parent sections.
Fresh intended/backup/compliance → fresh Config Plans → per-run approval →
Fail Job on Task Failure → one device per platform → explicit confirmation →
fleet. Verify prior-state/rollback behavior on a failed device; a failed job
alone does not prove partial CLI changes reverted.

## C5 — Generator and credentials

Input is Nautobot GraphQL for fleet identity, role/platform, management IP,
SNMP context and credential references. Output is deterministic non-secret
receiver/pipeline configuration, then SuzieQ inventory. Canary scope is a
filter over the same source. Failed/empty query must not delete the fleet.

Publish validated outputs atomically to Git. Resolve secret values via a
separate managed, secure path and define rotation/Argo ownership. A
CISCO_SSH/ARISTA_SSH name is a reference, not a credential value.

## C6 — Ownership and reproducibility

Application names/waves are in plan.md. Every workload uses a pinned
mirror-chart plus Git values; generated supporting resources have an owning
Git-managed chart/Application. Bootstrap, cluster provisioning, mirror and
secret setup are documented prerequisites. Do not claim root-app alone
rebuilds the cluster or approves device deployment.

VM/VL are metrics/log stores. SuzieQ Parquet is the explicit state-history
exception; document retention, cleanup, storage size and growth monitoring.
No Prometheus remote-write/Loki/ServiceMonitor/PodMonitor dependency.

## C7 — Measurement and follow-on consumers

Compare the same 24-hour workload's raw and derived representation sizes,
including series cardinality and duplicate/gap policy. Report total footprint
and capacity for actual retention/replicas. Tenfold is a measured target.

Follow-on alerts/LLM may consume verified query surfaces but are not
implemented here. Internal health/bridge signals do not authorize arbitrary
new external telemetry sources.
