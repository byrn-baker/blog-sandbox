# IOS-XE fleet NetFlow rollout

The operator approved moving forward with NetFlow on September 22, 2026, while deferring the vEOS forwarding investigation until after the Part 8 post. This rollout therefore covered all 13 IOS-XE routers. EOS sFlow remained limited to DCA-Leaf01.

## Source and validation

Commit `014d1ca` added a platform-scoped NetFlow context, retained CE1's separate syslog canary context, and attached the monitor only to enabled IOS-XE data interfaces. It did not add NetFlow to GigabitEthernet1, expand syslog, or expand EOS sFlow.

`make ci` passed 88 template and structure tests. The focused telemetry tests passed 5 tests. `make ci-full` passed all 149 template, intended-config and Batfish checks. Fresh intent, backup and compliance jobs ran before plan creation. Each manual Config Plan contained only the three PART8 flow objects and applicable interface attachments.

## Deployment

CE2 was the new rollout canary. Its deployment job succeeded with Fail Job on Task Failure enabled. Read-back found the expected configuration in running and startup state, four attached interfaces, established BGP, and successful export. VictoriaLogs stored 2,135 decoded NetFlow v9 records from CE2 during the first 15-minute check.

The first three-device expansion job failed. Golden Config's Netmiko dispatcher starts an inventory-wide save task from each per-device merge task. Selecting CE3, RR1 and RR2 together caused overlapping save operations. The exact failures were an invalid `exit` during save and a 300-second `read_channel_timing` expiry. Read-back showed:

- RR1 was fully configured and saved.
- RR2 was fully configured in running state but not startup state.
- CE3 had the flow objects but only two of four required interface attachments and was not saved.

No automatic rollback was assumed. Fresh intent, backups and compliance preceded two new recovery plans. CE3 received only the missing GigabitEthernet4 and GigabitEthernet5 attachments. RR2 received an idempotent flow-monitor context command to trigger a save. Both one-device recovery jobs succeeded and passed running/startup read-back.

Every remaining plan was then deployed in a separate one-device job. All jobs used Fail Job on Task Failure. This avoids the overlapping-save behavior without changing the deployed device intent.

## Final result

| Check | Result |
| --- | --- |
| IOS-XE routers configured | 13 of 13 |
| Running and startup flow objects | 13 of 13 |
| Routers with expected active-interface attachments | 13 of 13 |
| Routers reporting successful exporter packets | 13 of 13 |
| Routers with an Idle, Active or Connect BGP neighbor | 0 |
| Fresh flow-export compliance | 13 of 13 |
| Final missing-feature Config Plans | 0 |
| VictoriaLogs NetFlow v9 sampler addresses | 13 of 13 (`192.168.3.50` through `.62`) |
| Kubernetes nodes Ready | 9 of 9 |
| Argo CD Applications Healthy and Synced | 12 of 12 |
| Longhorn volumes healthy | 4 of 4 |
| Collector warning/error log lines during the 45-minute final window | 0 |

Backend record counts prove receipt and decoding from every IOS-XE exporter during the measured window. They do not prove lossless UDP delivery or record-level reconciliation. The previously measured workload packet loss through vEOS remains an open, separately documented issue.

## Evidence

- `final-audit.json` contains sanitized per-device read-back summaries, compliance, zero-plan confirmation, backend counts and cluster health.
- `reviewed-deltas.json` contains the original 12 undeployed-device plan contents.
- `verify-wave-border1-spe3.json` contains the final direct CLI read-back from all 13 routers.
- `recovery-reviewed-deltas.json` records the exact CE3 and RR2 recovery commands.
- `job-*.json`, `deploy-*.json` and `approval-*.json` identify the gated Nautobot jobs and plans.
- Failed multi-device deployment job: `652edc7e-8edd-4d50-86fe-a54e68a7a45a`.
- Final intent job: `145ff75a-a1ab-436a-b94f-40b887a63781`.
- Final backup job: `eb7be7a9-576a-40bf-b151-202d48333e16`.
- Final compliance job: `93ccbc4c-05d3-4ded-8c21-b0357324b155`.
- Final no-op plan job: `ec1c82e6-5114-4dcb-8fd8-b3b02e43a2ae`.

Secrets, complete environments, kubeconfig content and device session logs are not included.
