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

## Readable interface panels

The Device and Interface selectors use full names from `ifDescr`, verified against
live `show interfaces` output, such as `DCA-Leaf01 / Ethernet1` and
`CE1 / GigabitEthernet2`. Short `ifName` aliases and numeric indices remain metric
metadata for joins and diagnosis; legends and tables hide them. Status values
render as Up, Down, Testing, Unknown, Dormant, Not present or Lower layer down.

Normal interface panels exclude MPLS protocol-layer rows (`ifType=166`) and IOS
`Null0`/`VoIP-Null0` sinks. A separate diagnostic table identifies MPLS rows missing
error counters. Arista's internal `Vlan4097` appears in CLI output but was absent
from the collected IF-MIB rows. The dashboard does not manufacture missing data.

For a presentation-only update, preserve the fleet, credential revision and all
Collector settings with:

```bash
python3 telemetry/generate_snmp.py --dashboard-only \
  --output ../blog-sandbox-argo-cd/values/otel-snmp-values.yaml
```

Publish the generated values through the existing Argo Application. This mode
does not query Nautobot or synchronize Secrets.

## Routing polling

`routing_metrics.py` extends the same receivers using Nautobot roles. BGP roles
collect BGP4-MIB peer state, remote AS, seconds established and the cumulative
count of entries into Established. Cisco core roles collect adjacency state
from CISCO-IETF-ISIS-MIB and session state from CISCO-IETF-BFD-MIB. The standard
IS-IS subtree was empty on the tested image; the Cisco subtree returned the
live adjacency table. Existing device SNMP access permits these reads. No new
SNMP host destination, notification configuration or device restart is needed.

The verified default-context baseline is 133 BGP peer rows on 24 devices,
28 directed IS-IS adjacencies on 10 core routers, and 56 BFD application rows
representing 28 local discriminators on those routers. The four P routers do
not run BGP. BGP peer transports include sessions carrying EVPN and VPNv4, but
these metrics do not measure prefixes or health separately for each address
family.

`bgp_vrf_profiles.yaml` selects the verified SERVERS contexts on DCA-Leaf03,
DCB-Leaf03 and DCC-Leaf03. Generation checks that each VRF exists on that
Nautobot device's modeled interfaces and rejects unsupported platforms.
The EOS context is selected with `${env:SNMP_DEVICE_KEY}@SERVERS`; the base
community remains a Secret reference. Each extra receiver polls only the
three BGP metrics, so it doesn't duplicate interface or uptime measurements.

Default BGP metrics carry `vrf="default"`; scoped metrics carry
`vrf="SERVERS"`. Peer identity includes device, VRF and peer address. The
expected fleet total is 136 rows: 133 default and three SERVERS peers. This
covers the verified IPv4 peer transports, not every possible VRF or address
family. New profiles require a direct SNMP/CLI comparison before rollout.

IS-IS circuit indices are joined to their reported IF-MIB indices, then to
`ifDescr`. This produces full CLI names without hard-coding a circuit-to-port
map. BFD needs different treatment on this IOS-XE image: its interface column
returns handles that disagree with IF-MIB, and its address column on SP1
reported local addresses despite the MIB describing neighbor addresses.
Neither field is used to label BFD sessions. The local discriminator matches
the CLI's `LD` column. Application IDs 9 and 15 each export a row for the same
session; the dashboard retains both and separately counts distinct local
discriminators. Their numerical IDs are not presented as protocol names.
No EOS BFD coverage is claimed.

The `Network Routing` dashboard and `routing-rules.yaml` live under
`blog-sandbox-argo-cd/observability/`. State mappings show Established or Up,
with a VRF selector and VRF/peer columns for BGP, and full interface names for IS-IS. The selector affects BGP panels only. Alerts
cover reported non-up states and device-level row counts below this recorded
baseline. Update the coverage rules after intentional topology changes.
A missing row must age out of the query lookback before the five-minute
coverage hold begins; these are not immediate failure notifications. Counts
cannot detect one missing peer replaced by a different peer. The three SERVERS
peers also have identity-specific absence rules using a three-minute window
and a two-minute hold. Default-context coverage remains independently checked.

A one-minute poll can miss a short down/up event. BGP established-transition
counters help identify recovered flaps, but do not provide the reason. Traps,
syslog ingestion, external alert notification delivery and VictoriaLogs remain
separate work. Enabling a device trap would not make this polling receiver
accept UDP 162.

Primary object definitions: [Cisco IS-IS MIB](https://github.com/cisco/cisco-mibs/blob/main/v2/CISCO-IETF-ISIS-MIB.my),
[Cisco BFD MIB](https://github.com/cisco/cisco-mibs/blob/main/v2/CISCO-IETF-BFD-MIB.my),
and [Arista MIB catalog](https://www.arista.com/en/support/product-documentation/arista-snmp-mibs).
Live comparison evidence takes precedence over assuming every documented field
is implemented correctly by the lab images.

The [VRF rollout verification](https://github.com/byrn-baker/blog-sandbox-argo-cd/blob/main/observability/evidence/bgp-vrf-verification.json) records both stores and all three dashboard selections. Newly labeled BGP series start with this rollout; older unlabeled history is retained but excluded from the VRF-aware panels to avoid double-counting.
