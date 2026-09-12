# Design Decisions and Research Gates (v3)

**Date**: 2026-09-09 | **Spec**: [spec.md](spec.md)
Supersedes v1/v2 research conclusions. Decisions are separated from
implementation evidence; no pinned-image validation is claimed here.

## Decisions retained

- Two repositories: device configuration/generation in blog-sandbox;
  Kubernetes Applications/values in blog-sandbox-argo-cd.
- Separate VictoriaLogs Application; existing VM/Grafana stack remains.
- Syslog and MetalLB are required, with one reserved/pinned telemetry VIP.
- SNMP receiver metrics go to VM; decoded flow/syslog logs go to VL.
- Shared retention is 14d logs and 547d metrics, not flow-only settings.
- SuzieQ has a scoped native state-store exception and is P2, not a P1
  foundation dependency.
- Optional enrichment uses local MaxMind then bounded ipinfo.io fallback;
  all records still take storage/count paths.
- There is no evidence of an existing deployed snmp_exporter in the reviewed
  manifests. The OTel receiver is the planned SNMP collection path.

## Source-backed boundaries

- [OTel SNMP receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/snmpreceiver)
  produces metrics. It does not establish a raw-SNMP log-storage path.
- [OTel count connector](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/connector/countconnector)
  converts record counts; it does not by itself establish transactional
  delivery to two backends or exact traffic-volume fidelity.
- [OTel NetFlow receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/netflowreceiver)
  is a candidate component. Verify actual protocol configuration and decoded
  fields in the chosen distribution; do not invent a separate component
  solely because a protocol has a different name.
- [Argo Application health](https://argo-cd.readthedocs.io/en/stable/operator-manual/health/#argocd-app)
  requires explicit restoration for app-of-apps wave orchestration.
- [K3s process flags](https://docs.k3s.io/cli/server)
  distinguish cloud-controller-manager arguments from controller-manager
  and scheduler arguments; the blog's logged controller needs separate review.

These links describe upstream behavior, not proof that the lab's pinned
versions support a proposed YAML field. Pin references during T003/T044.

## Research still required

| Gate | Evidence needed | Task |
|------|-----------------|------|
| Principle VI interpretation | Record alignment/amendment need for UDP boundaries and unequal retention | T001 |
| VIP path / ServiceLB | Existing interfaces/routes, permitted advertisement design and receipt from both subnets | T006/T021 |
| Collector compatibility | Pinned distribution validates all components, pipeline merges, OTLP URLs and fields | T003/T007 |
| Count equality under failure | Window/duplicate/late-arrival contract, connector state, independent backend outage/replay | T025/T027 |
| Cardinality/capacity | Bounded grouping/overflow plus 24h measurement and retention sizing | T026/T029 |
| SuzieQ | Actual route facts, Secret resolution/rotation, table API and retention cleanup | T009/T031/T035 |
| Enrichment | Local/fallback capability, bounded latency and all-path accounting | T038–T040 |

Do not carry forward the older design's fallback-count bypass, unsupported
config snippets, generic send-failure counters as terminal-drop proof,
unverified Service reachability, or secret-dumping validation commands.
