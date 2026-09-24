# Syslog fleet rollout, September 24, 2026

All 28 network devices now send syslog to the existing telemetry VIP,
192.168.3.241, through MGMT-VRF. IOS-XE uses GigabitEthernet1 as its source;
EOS uses Management1. No routing, interface forwarding or flow-export settings
were changed during this rollout.

The operator authorized syslog and SuzieQ expansion to the remaining fleet.
Platform contexts and source templates were updated in `b0d23f8`; matching
mock contexts, `make ci` and `make ci-full` passed before deployment. The latter
included 149 Batfish/intended-configuration checks. Golden Config generated
fresh intent, backups, compliance and 26 minimal Config Plans. CE1 and
DCA-Leaf01 already had the required configuration.

CE2 and DCA-Leaf02 were verified first. The remaining plans were deployed in
waves, one device per job, with Fail Job on Task Failure enabled. Each push
was followed by running and startup configuration checks. All 26 deployment
jobs succeeded. The final independent read-back covered all 28 devices.

## Acceptance

Fresh intended configuration, backup and compliance jobs completed after the
rollout. `acceptance.json` records 28 compliant platform logging rules, with
no missing or extra matched configuration, and received records from all
28 management addresses in a two-hour window. The backend query was:

```text
_time:2h AND NOT flow.type:*
| stats by (net.peer.ip) count() as records
```

This verifies sender coverage and delivery to VictoriaLogs. It does not prove
lossless UDP delivery or exact event accounting. The existing raw-log retention
remains 14 days. No synthetic link flap or forwarding change was used to
generate these messages.

`verify-fleet.json` contains sanitized running/startup logging configuration
and status output. Plan, approval and job files retain the deployment trail.
The matching SuzieQ rollout and Grafana checks are recorded in
`blog-sandbox-argo-cd/suzieq/evidence/fleet-20260924/` and
`blog-sandbox-argo-cd/observability/evidence/part8-fleet-20260924/`.

The vEOS forwarding investigation remains separate. Successful management-plane
telemetry does not establish that the affected data-plane path is repaired.
