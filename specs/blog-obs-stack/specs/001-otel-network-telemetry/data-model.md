# Data Model: Unified OTel Telemetry Pipeline (v3)

**Spec**: [spec.md](spec.md) | **Status**: contract, pending implementation evidence

## Signals and stores

| Entity | Required identity/fields | Store / retention |
|--------|--------------------------|-------------------|
| SNMP metric | Device/site, interface identity, OID mapping, value/type/unit, poll time; uptime/status/in-out octets/errors | VM / 547d |
| Decoded NetFlow record | Exporter identity, protocol/template context where exposed, addresses/ports/protocol, available octets/packets and start/end times | VL / 14d |
| Decoded sFlow record | Exporter identity, sample type, available sampled header/counter fields and sampling metadata | VL / 14d |
| Syslog record | Source device, receive/event times, severity/facility when parseable, original message | VL / 14d |
| Derived count | Device/site, bounded grouping, signal/schema version, point timestamp, temporality and unit = records | VM / 547d |
| SuzieQ state | Device/namespace, table schema, collection time, state and freshness/error context | Native Parquet / policy set and tested at T009 |
| SuzieQ derived metric | Device/namespace, specific state fact, unit, observation time/freshness | VM / 547d |

A decoded record is not a packet capture. Required field support is verified
against the pinned receiver/image; missing required fields block acceptance.
SNMP is stored as native metrics, not fabricated raw VL logs.

## Record accounting

- Distinguish exporter datagrams, flow records, sFlow samples, Collector log
  records and stored rows. Sampling is not lossless packet observation.
- Preserve device event time where available and add receive time. Select
  one timestamp basis for comparison windows; define clock skew/late arrival.
- Define duplicate identity from actual protocol fields and exporter
  boot/session context where available. A payload hash alone may merge
  legitimate identical records. Keep identity in logs/reconciliation state,
  never as an unbounded metric label.
- Account for unattributed records as unknown with visible errors; do not
  silently discard them. Unknown identity is not fleet-coverage success.
- Use half-open windows [start, end), a documented settling interval and
  schema/grouping version. Equality uses identical filters/duplicate policy
  in both stores; no exact-equality assertion from an extrapolated rate.
- Unbounded conversation tuples and absolute window-start labels are
  excluded from baseline metrics. Raw logs support detailed conversations.
  Bounded aggregation/overflow must retain accounting totals.

## State and retention

Window status: open → settling → reconciled or mismatch/incomplete →
raw-expired. Backend/connector failures cannot silently finalize a window.
Replay must define how duplicates and prior output are handled; exporter
queues alone do not preserve connector state.

Raw records expire after 14d. Counts and SNMP/SuzieQ metrics retain 547d.
Raw links are valid only for retained windows. The report includes raw and
derived storage together, replicas, queues and SuzieQ overhead.

## Generated fleet and secrets

Nautobot defines 28 network devices, per-device SNMP applicability, primary
management IP, site, platform and credential authority. Query failure or an
unexpected empty fleet preserves previous output and fails the run.
Generated artifacts contain secret references; secure runtime resolution
and rotation are separate, verified operations.

## Enrichment and state facts

Optional enrichment appends versioned attributes without replacing original
fields. Resolved, fallback and unresolved records all reach storage/counting.
Private addresses remain unenriched. Dataset revision/staleness and fallback
limits are explicit.

SuzieQ advertised/received-route counts require those actual facts from
supported collection. RIB rows cannot stand in for them. An unavailable fact
stays unsupported until its collection/requirement is resolved.
