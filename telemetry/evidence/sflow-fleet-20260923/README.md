# EOS fleet sFlow rollout, September 23, 2026

The approved rollout configured sFlow on all 15 EOS devices and verified
decoded records from every exporter in VictoriaLogs. DCA-Leaf01 retained its
existing canary configuration; fresh one-device Config Plans deployed the same
five sFlow commands to the remaining 14 devices.

## Source and validation

Commit `2f35d86` added the platform-scoped EOS sFlow context. It points at
`192.168.3.241:6343` through `MGMT-VRF`, sources datagrams from `Management1`,
uses a 1:16,384 packet sampling rate and keeps the 20-second counter polling
interval. The template keeps syslog limited to the earlier DCA-Leaf01 canary.

`make ci`, `make ci-full`, and the focused telemetry tests passed before the
source was synchronized to Nautobot. The pinned Collector endpoint was Ready
and exposed UDP 6343 before deployment.

## Deployment

Fresh intended configurations, backups, compliance results and Config Plans
were generated after source synchronization. DCA-Leaf02 was the platform
canary. Its first verification attempt used privileged `show running-config`
commands without entering enable mode; `show sflow` still proved the exporter
was running. The verification helper was corrected to enter enable mode, after
which running and startup configuration both passed.

The remaining devices were deployed serially, one plan per job, with Fail Job
on Task Failure enabled. This avoids the overlapping-save behavior observed in
the IOS-XE NetFlow rollout. All 14 deployment jobs completed successfully.

## Acceptance

The final read-only audit covered 15 devices. Every device reported:

- sFlow enabled and running
- destination `192.168.3.241:6343` in `MGMT-VRF`
- `Management1` as the IPv4 source interface
- matching `sflow run` state in running and startup configuration
- no CLI errors in the final verification

Fresh post-deployment backups and compliance completed successfully. The
`flow_export` rule was compliant on 15 of 15 EOS devices with no missing or
extra matched configuration.

The VictoriaLogs query below returned all 15 management addresses as
`flow.sampler_address` values in one 30-minute window. The acceptance snapshot
contains 136 decoded records across those exporters.

```text
_time:30m AND flow.type:sflow_5
| stats by (flow.sampler_address) count() as records
```

This proves sampled packet records reached the observability stack from every
EOS device. It does not prove exact packet or byte accounting. Counter samples
remain unsupported by the pinned OTel receiver, so SNMP remains the source for
interface counters. Sampling is probabilistic; low-traffic exporters can take
several minutes to appear.

`acceptance.json` is the compact compliance and backend record. `verify-fleet.json`
contains the sanitized live command output. Plan, approval and job-result files
retain the change trail without credentials or session logs.
