# Part 8 canary, September 20–21, 2026

The two-device canary established real NetFlow v9, sFlow packet samples and
syslog delivery to VictoriaLogs. Scope was CE1 (C8000V, IOS-XE 17.15.1a) and
DCA-Leaf01 (vEOS-lab 4.34.6M). No other device received telemetry configuration.
The operator authorized this canary and selected the current server subnet,
10.100.0.0/24, plus management, 192.168.3.0/24. Home-network reachability was
excluded. The requirements glossary and Requirement 12 reflect that choice.

## What was tested

The Git-reserved VIP is 192.168.3.241. MetalLB announces it on the management
interface of dcb-k3s-w1. Its Local traffic policy forwards to the Collector on
that node. UDP ports 2055, 6343 and 514 feed NetFlow, sFlow and syslog receivers.
The Service translates syslog port 514 to unprivileged container port 5514.

Protocol-valid synthetic messages from 192.168.3.21 and a server socket bound
to 10.100.0.10 reached storage on all three paths. The Argo PostSync hook checks
six fresh, distinguishable stored records and fails if they do not appear.
The deployment helper requires that successful hook before approving a plan.
The synthetic NetFlow packet is v5; subsequent CE1 records separately establish
actual v9 export and decoding. No routing or NAT configuration was added.
The lab-source NetFlow probe arrived with a CNI-translated sender address;
this test proves delivery from the bound server socket, not source-IP
preservation on every Kubernetes path.

Golden Config generated fresh intent, backups, compliance and telemetry-only
Config Plans. Both deployment jobs used Fail Job on Task Failure. Startup
read-backs confirmed saved export and logging configuration. CE1 has ingress
monitors on GigabitEthernet2 through GigabitEthernet5. EOS uses its normal
global ingress sampling at 1:16384, with a 20-second counter polling interval.

The Collector is pinned to 0.154.0. VictoriaLogs is v1.52.0, deployed through
the mirrored victoria-logs-single chart 0.13.9 and the Argo root Application.
It has a 10 GiB Longhorn volume and 14-day configured retention. Capacity for
14 days of fleet traffic was not measured. The original SNMP Collector and
metrics stores remain separate.

## Failures that changed the implementation

The first CE1 job rejected `match ip protocol`. The correct command on this
image is `match ipv4 protocol`. Its read-back showed only an unused partial
record, with no exporter, interface attachment or startup change. A reviewed
replacement plan removed that exact partial record, then applied the corrected
source after fresh generation and validation. The failed plan was not retried.
This also demonstrates that a failed merge can leave partial running config.

Batfish does not model the tested EOS sFlow commands. They were accepted in
an EOS configuration session that was aborted before any commit, then verified
by the actual canary. Narrow exceptions were added to both mock and generated
configuration validation. Batfish passed the original invalid IOS protocol
command, so its pass alone was insufficient device evidence.

Cisco's syslog format did not parse as RFC 3164. Messages were initially
retained through `on_error: send`, but without useful parsed metadata. The
receiver now uses `protocol: none`, preserving the original message while
decoding PRI severity/facility and adding UDP sender attributes. Both devices
emitted explicit PART8-CANARY markers, which were queried with their source IP
and informational severity. Device timestamps remain in the original text;
the stored timestamp is receiver time for this configuration.

The Collector restart during that correction lost its NetFlow template cache.
It logged template misses until CE1 refreshed its template, then resumed v9
decoding. This is a measured collection gap. Exporter queues are bounded in
memory (1000 requests, 300-second retry limit), not durable or lossless.

IOS-XE hides default v9 export, 15-second inactive timeout and informational
logging from normal running configuration. EOS omits its default sFlow UDP
port and informational logging. The final templates match those observed
forms so compliance does not report defaults as missing commands.

The final fresh compliance run passed flow export and logging on both devices.
Config Plan generation job `4928d851-1d5e-44e0-bac4-cd8f6544db9f` then reported
no missing configuration for either feature on either device and created no
plans. No additional push was needed. Final `make ci-full` passed its 88
template/structure checks and 149 Batfish/generated-configuration checks.

## Traffic interpretation and limits

Stored EOS samples contain original 10.100.0.x endpoints, including Kubernetes
API and etcd traffic, and separate outer UDP/4789 records between 10.3.x.x
VTEPs. CE1's NetFlow also sees outer VXLAN traffic. These are actual samples,
not proof that every application or packet is visible.

The selected Collector's decoded projection does not expose VNI or ingress
interface fields in these stored examples. It cannot yet support the proposed
per-VNI attribution or establish which leaf port produced a particular sample.
The receiver also ignores sFlow counter samples; retain SNMP for interface
utilization. Flow-record counts are not packet counts or exact traffic volume.
The underlying packet capture and custom-field preservation work remain open.

A bounded 250-packet/s workload sent 45,000 UDP datagrams of 128-byte payloads
between 10.100.0.10:47776 and 10.100.0.20:47777. The receiver counted 44,403,
leaving 597 missing (1.33%). The cause was not isolated. This measures the
test workload's delivery, not telemetry-export loss. A matching sFlow record
for that specific workload was not established; the real sFlow evidence comes
from other traffic during the observation period.

This is a feasibility canary, not completion of fleet acceptance. No fleet
rollout, 30-minute fleet accounting, external notification delivery, deliberate
BFD/BGP flap, VNI decoding, enrichment, count reconciliation or 24-hour storage
comparison was performed. No sustained-loss or failover guarantee is implied.

## Evidence and repeatability

- `summary.json` records the query cutoff, stored record counts, examples,
  application/node/volume state, compliance and per-device deployment logs.
- `final-live-devices.json` contains the saved configuration and export-state
  read-backs. `first-ce1-failure.json` and `after-failed-ce1-devices.json` record
  the rejected command and partial state.
- `receiver-gate.json`, `receiver-gate-records.json` and the gate resource
  capture record the prerequisite path tests. The hook passed again after the
  syslog receiver update.
- Job and approval files identify the actual runs. `reviewed-deltas.json`
  contains the second attempt's exact commands, including partial-record cleanup.

The source tools are in `telemetry/canary_*.py`. The controller uses existing
Nautobot credentials in memory; files contain no credential values. The
deployment helper intentionally refuses a plan that already has a deployment
result. Do not rerun it as a generic reconciliation tool.

To query stored detail locally:

```sh
kubectl port-forward -n observability svc/victorialogs 19428:9428
curl http://127.0.0.1:19428/select/logsql/query \
  --data-urlencode 'query=_time:1h AND flow.type:sflow_5 | limit 10'
```

For another approved device run, review current state and prepare new Plans.
To disable this canary, remove the two device contexts' telemetry section,
regenerate intent/backups/compliance, and review removal Plans for the named
PART8 flow objects, their four attachments, and the telemetry logging/sFlow
configuration. Stop device export before removing the receiver Application.
Preserve the VictoriaLogs PVC if its evidence is still needed.

Sources used for component behavior:
[pinned NetFlow receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.154.0/receiver/netflowreceiver/README.md),
[pinned syslog receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.154.0/receiver/syslogreceiver/README.md),
[VictoriaLogs OTLP ingestion](https://docs.victoriametrics.com/victorialogs/data-ingestion/opentelemetry/).
