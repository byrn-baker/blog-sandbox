# Specification Review Checklist (v3)

**Updated**: 2026-09-09 | **Feature**: [spec.md](../spec.md)

## Documentation consistency

- [x] 28-device network scope distinguished from 38 total devices.
- [x] Required syslog/MetalLB and 14d/547d retention propagated.
- [x] SuzieQ state-store exception explicit.
- [x] SNMP metrics destination consistent across documents.
- [x] Record accounting distinguished from traffic fidelity.
- [x] Raw drill-down bounded to raw retention; expired detail explicit.
- [x] P1 canaries/collection precede SuzieQ; approval remains per device run.
- [x] Requirements mapped to tasks and validation scenarios.
- [x] Historical design identified as background, not deployable instruction.

## Implementation readiness and evidence

- [ ] Principle VI compliance interpretation/amendment requirement resolved.
- [ ] Baseline SNMP deployment and control-plane stability verified.
- [ ] VIP path and ServiceLB ownership proven from both subnets.
- [ ] Pinned Collector/chart capabilities and fields validated.
- [ ] Raw/count restart/outage/reconciliation semantics demonstrated.
- [ ] SuzieQ route facts, credential integration and retention validated.
- [ ] Storage budgets measured for required retention.
- [ ] Canary then fleet evidence recorded.
- [ ] SC-001–SC-007 evidence complete for enabled scope.

The first section checks document agreement only. It does not mean the
pipeline exists, all requirements are satisfied, or implementation gates pass.
