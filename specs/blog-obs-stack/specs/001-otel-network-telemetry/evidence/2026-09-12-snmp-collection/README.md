# SNMP collection and control-plane placement review

On September 12, the operator requested full network SNMP collection and an
assessment of returning K3s masters to all three datacenters. Collection was
deployed through Git and the existing Argo root. No router/switch CLI changes
or master migration were performed in this run.

## Collection outcome

At 18:53 UTC, both VictoriaMetrics stores contained fresh samples for all 28
Nautobot-selected devices: 13 IOS-XE and 15 EOS. Every device had all ten metric
families. The final five-minute query window contained five operational-state
samples per interface. Maximum device uptime sample age was under 60 seconds.
See [fleet-final.json](fleet-final.json).

There are 372 interface rows and 3,264 current series: uptime, interface
operational/admin status, in/out 64-bit octets, errors, discards and speed.
Error/discard counters cover 344 rows. The remaining 28 are IOS MPLS-layer rows,
not missing physical-interface polls. They share short names with their parent
interfaces but have distinct descriptions, indices and types. Direct SP1 GETs
returned a Counter32 zero for physical Gi2 and `NoSuchInstance` for its MPLS
layer's error OIDs. Those missing values remain absent. The dashboard shows the
exceptions instead of filling them with zero. See [direct-oids.json](direct-oids.json).

CE1 and DCA-Leaf01 were verified first, across repeated polls in both stores,
before expanding. All 28 then collected successfully. One RR1 uptime request
timed out during the initial simultaneous fleet polls with a three-second
timeout, and recovered on the next poll. The final configuration spreads initial
poll phases across the minute and uses the receiver's default five-second
timeout. The final process had zero reported scrape errors, refused points,
export failures or queued requests at the captured boundary. Both destinations
reported 16,875 exported points at that instant. This equality is a snapshot,
not a guarantee of transactional or lossless delivery.

The Collector polls through a worker's management NIC. A metadata-only capture
observed UDP/161 requests leaving eth0 with source 192.168.3.69, inside the
existing 192.168.3.0/24 SNMP ACL. Communities came from Nautobot's existing context
into a Kubernetes Secret; generated Git values contain references only. Existing
device VRF/ACL configuration was reused. See [snmp-egress.json](snmp-egress.json).

Grafana provisions `Network SNMP`, UID `network-snmp`, with a datasource pointing
at the history store. Panels cover coverage, freshness, uptime, rates,
utilization, errors, discards, state and unsupported rows. Collector error,
queue and export-rate panels use the existing `VictoriaMetrics` datasource.
Datasource and panel queries were checked through Grafana's API.

## Delivery, ownership and persistence

The Argo bootstrap was upgraded using its existing pinned chart and reviewed
values. The live ConfigMap contains the child-Application health rule. An
isolated first child with a missing source path held the second child back even
though Argo labeled the first Healthy, because it was not Synced. After repairing
the source, both children and the test root became Healthy/Synced. All test
resources were removed. See [wave-blocked.json](wave-blocked.json) and
[wave-recovered.json](wave-recovered.json).

`snmp-metrics` is wave 4, `otel-snmp` wave 5. All five live Applications were
Healthy/Synced in the final snapshot. A VMRule default of `record: ""` initially
caused repeated Argo correction; matching that server default in generated
source resolved the drift. The Collector uses Recreate and one replica so a
rollout does not start a second fleet poller.

The final cluster had 9/9 Ready nodes and 67/67 Ready pods. All three Longhorn
volumes were healthy with three replicas, including the new SNMP history volume.
See [final-cluster.json](final-cluster.json). This verifies current health, not
future failure recovery.

## Retention and capacity budget

SNMP goes over native OTLP to two VictoriaMetrics destinations from a single
poll: the existing store for current queries/alerts and a dedicated store for
547-day history. The existing cluster metrics retention is unchanged. It was
already receiving about 11,938 samples/second on a 20 GiB volume; extending that
whole store to 547 days was not justified by its capacity.

The new history store has a 20 GiB Longhorn volume, three replicas, and an
effective `--retentionPeriod=547d` argument. Current SNMP is 3,264 samples/minute,
or 54.4/second. Over 547 days that is approximately 2.571 billion samples. A
planning allowance of four bytes/sample plus 50% overhead is about 14.4 GiB
logical, below 20 GiB; three replicas consume up to 60 GiB when fully allocated.
These are sizing assumptions, not a measured compression guarantee. A 24-hour
growth measurement and continued disk monitoring remain necessary. The first
minutes' storage size is too small and immature for a reliable long-term ratio.

Observed resource use at one check was approximately 5m CPU/63 MiB for the
Collector and 6m CPU/79 MiB for the history store. Requests are respectively
100m/192 MiB and 100m/256 MiB; memory limits are 512 MiB and 768 MiB. Both run on
workers. Export queues are bounded, in memory, and lost on restart; retries stop
after 300 seconds. Poll gaps and unknown intervals must remain visible.

## Can the masters return to three datacenters?

The architecture is possible, but this run does not establish that migration is
ready. Keep the current master placement for now.

The fixes are still present: 13/13 running CML QEMU processes match the patched
binary and use virtio; all 90 leaf data NICs have GRO off, with the startup
handlers saved on all nine leaves. Neither a cold boot nor a site failure was
introduced in this run. See [qemu-summary.json](qemu-summary.json) and
[gro-current.json](gro-current.json).

All 600 small ping probes and 30 jumbo probes arrived across six directed
cross-datacenter paths. Small-packet medians varied from 19.1 to 108 ms, with a
403 ms maximum in the sampled windows. Three bidirectional jumbo TCP tests
transferred 1 MiB each way at a bounded rate, with matching hashes and no stalled
transfers. They recorded four retransmissions in total. Those samples establish
delivery, not uniformly low latency or a long soak. See
[ping-summary.json](ping-summary.json) and [tcp-summary.json](tcp-summary.json).

During roughly 20 minutes of this work, the colocated etcd peers averaged
61.8–72.3 ms round trips. The later 30-minute log windows had 551, 343 and 143 slow
apply warnings. No leader changes or failed proposals were added in the measured
interval. A Kubernetes log-proxy request also returned a 502 during inspection;
direct node access succeeded, and that isolated proxy error was not assigned a
root cause. See [etcd-delta.json](etcd-delta.json).

Cross-site placement makes inter-site latency part of quorum writes. It can
improve site fault tolerance, but healthy pods and working jumbo transfers are
not sufficient evidence for that move. This follows the tradeoff documented in
the [etcd FAQ](https://etcd.io/docs/v3.5/faq/) and
[performance guide](https://etcd.io/docs/v3.6/op-guide/performance/).

Before migration, measure a sustained period under storage and telemetry load,
resolve the remaining latency variation, and validate a disposable three-member
etcd cluster across the intended sites, including a controlled link/site
interruption. That follow-up was not performed here. This recommendation is
based on the measurements above, not a claim that stretched etcd is inherently
unsupported.

## Validation and limits

The 14 generator tests passed, including failed/empty-query preservation,
membership changes, duplicate detection, Secret synchronization failure and
rotation idempotence. `make ci` passed 88 tests. Both pinned charts rendered and
passed server-side dry runs; the pinned Collector binary validated the final
configuration. Fresh Nautobot generation matched the committed values, with no
credential values in the output. No Golden Config template/context changed,
so this deployment required no router regeneration or Batfish revalidation.

This completes the requested SNMP slice. Flow/syslog ingestion, MetalLB,
VictoriaLogs, SuzieQ, broader raw/count reconciliation, 24-hour capacity evidence
and master migration remain outside this completed slice. The initial early
check during staggered startup saw only 17–18 devices; acceptance waited for the
full fleet and repeated cycles. Full local evidence is retained in
`/home/ubuntu/snmp-collection-20260912`.
