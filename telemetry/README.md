# SNMP collection

The generator queries Nautobot for roles, platforms, primary management IPv4,
location and resolved SNMP context. It selects eligible Cisco IOS-XE and Arista
EOS network devices, excluding servers. It polls every 60 seconds through the
device's management VRF using the existing read-only community and ACL.
Initial poll phases are spread across the minute, with the receiver's standard
five-second request timeout. The first unspread fleet cycle had one RR1 uptime
request time out at three seconds; subsequent polls recovered. Errors remain
visible instead of being treated as valid zero samples.

This is the SNMP portion of the telemetry plan. It does not enable flow export,
syslog, MetalLB or SuzieQ. Polling initiates outbound traffic from the Collector;
it needs no inbound telemetry VIP. Those other source types retain their own
reachability and device deployment gates.

## Generate and deploy

Use Python 3 with `pip install -r telemetry/requirements.txt`. Supply
`NAUTOBOT_URL` and `NAUTOBOT_TOKEN` through the existing credential mechanism,
without printing them or entering them in shell history. The Kubernetes context
must point at the lab. The observability namespace and existing VictoriaMetrics
operator are prerequisites.

```bash
python3 telemetry/generate_snmp.py \
  --output ../blog-sandbox-argo-cd/values/otel-snmp-values.yaml \
  --sync-secret
pytest telemetry/test_generate_snmp.py -q
```

For a canary add `--canary CE1 DCA-Leaf01`; selection filters the query, not a
separate inventory. Inspect the non-secret diff, render with the pinned chart,
validate the rendered Collector configuration using its pinned binary, then
commit and push the values to the Argo repository. Its existing root Application
discovers `snmp-metrics` at wave 4 and `otel-snmp` at wave 5. No direct child apply
is needed. A failed or empty source query leaves previous artifacts untouched.

The bootstrap health rule was installed and tested on September 12: an
unsynchronizable first child held the next wave; repairing the first child
allowed the later child to appear. This gates initial deployment. Existing
children can reconcile independently afterward.

## Credentials and rotation

`--sync-secret` resolves communities from the same Nautobot contexts as Golden
Config. It writes only `network-snmp-credentials` in `observability` using
server-side apply over stdin. It never emits credential values into generated
Git files, logs or last-applied annotations. Argo owns the reference, not this
externally managed Secret. The Collector has no Kubernetes API token and cannot
read arbitrary Secrets. This helper does not change device credentials.

The helper preserves an unchanged Secret. A changed credential set receives a
random revision marker, copied into generated pod annotations so the reviewed
Git update causes the Collector to reread its environment. The marker is not a
hash of the community. Rotation must be coordinated with the separate approved
Golden Config device rollout; synchronization alone does not rotate devices.
Failed Secret synchronization preserves generated values. Publication failure
after Secret synchronization requires finishing the reviewed Git update; do not
assume those two systems form one transaction.

## Metrics and storage

One receiver per device collects `sysUpTime` and IF-MIB interface names, 64-bit
in/out octets, errors, discards, operational/admin state and high-speed values.
Metrics carry device, platform, site, management IP, job and instance. Interface
samples also carry interface name and index. SNMP uptime is in hundredths of a
second, wrapping after about 497 days. IF-MIB errors/discards are 32-bit counters;
rate queries account for resets but cannot reconstruct multiple wraps between
polls. Interface speed in a virtual lab is not measured forwarding capacity.
The `interface` label uses `ifDescr`, while `if_name` retains the short name and
`if_type` identifies the layer. IOS MPLS-layer rows can share `ifName` with the
physical interface but have different indices and descriptions. The September
12 direct GET check returned `NoSuchInstance` for errors on SP1's MPLS-layer row
and a real zero Counter32 on the physical row. Both rows' traffic is retained;
do not sum them as separate physical links. Missing error counters remain absent
and have a dedicated dashboard table.

Samples go over native OTLP HTTP to the existing VictoriaMetrics instance for
current queries/alerts, and to `snmp-metrics` for 547-day history. These are two
destinations for one poll, not two device pollers. The existing cluster store
retains its prior policy. Both exporters have independent bounded queues and
retry state. They do not provide atomic delivery between stores.

The separate 20 GiB Longhorn volume avoids extending roughly 12,000 cluster
samples/second to 547 days on the existing 20 GiB volume. It uses three replicas,
so its full allocation requires 60 GiB across storage nodes. The SNMP history
budget must be checked against actual series, ingest, compression and growth;
547 days configured is not 547 days of measured retention. No downsampling is
introduced. To remove the second store, first choose an adequately sized
replacement retention policy and update the exporter/datasource; preserve its
PVC until historical data is no longer needed.

Collector requests are 100m CPU/192 MiB, with a 512 MiB memory limit. The history
store requests 100m CPU/256 MiB with a 768 MiB limit. Ordinary workloads remain
off the tainted control-plane nodes. One Collector replica and Recreate updates
avoid double polling. A restart creates a polling gap. Export queues hold up to
1,000 requests per destination in memory, retry for at most 300 seconds, and are
lost on process restart. This bounded implementation does not claim lossless
collection during outages. Freshness, scrape/export errors and queue metrics
make gaps visible.

## Operator checks

Grafana provisions the `Network SNMP` dashboard at `/d/network-snmp` and the
`Network SNMP (547 days)` datasource. Panels show fleet coverage, sample age,
uptime, interface bit rates, utilization, errors, discards and state. Missing
samples mean unknown, not zero traffic. Stale-device VMRule alerts query the
existing VictoriaMetrics store; the history dashboard independently exposes
history-store freshness.

```promql
count by (device) (snmp_interface_oper_status)
count(time() - timestamp(snmp_device_uptime_ticks) < 180)
rate(snmp_interface_in_octets_total[5m]) * 8
```

The `VMServiceScrape` reads Collector self-metrics through the existing vmagent.
No Prometheus server, ServiceMonitor or external application receiver is added.
The SNMP receiver is alpha in this pinned distribution; verify real counters,
not just process readiness. Unsupported OIDs can yield partial data while the
process stays healthy. Acceptance must cover every required metric family and
every device across repeated polls.

Pinned artifacts: Collector chart 0.162.0 and contrib image 0.154.0 (digest in
generated values); VictoriaMetrics single chart 0.46.0 and image v1.151.0;
PyYAML 6.0.2. Charts are served by the lab mirror. Image pulls use the existing
management-network registry caches. Rebuild the mirror using the procedure in
`demo-lab/09-lab-artifact-mirror.md`.
