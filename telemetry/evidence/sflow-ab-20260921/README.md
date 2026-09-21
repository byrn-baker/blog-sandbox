# DCA-Leaf01 sFlow comparison, September 21, 2026

Disabling sFlow did not remove the UDP loss or forwarding receive-buffer
pressure. The captured EVE Linux bridge segments did not lose test packets.
The dominant loss remained across the vEOS forwarding path on DCA-Leaf01.
sFlow was restored and verified in both running and startup configuration.

## Approved change and method

The user approved a temporary, source-controlled sFlow-off comparison followed
by restoration on DCA-Leaf01. The only deployed commands were `no sflow run`
and then `sflow run`. Export destinations, sample rate, syslog, CE1 NetFlow,
bridges, MTUs, bonds, hypervisor settings and Kubernetes configuration were
unchanged. Both deployments used Fail Job on Task Failure and returned SUCCESS
with no warning, error or failure entries in their per-job logs.

The source template now allows the EOS run state to be selected through the
device context. The final `telemetry_canary.enabled` value is `true`.
Unit tests verify that changing it only replaces the run-state command, not
the rest of the generated configuration. Both off and restored source states
passed 88 template/structure checks, 149 Batfish/generated-configuration checks
and three focused canary checks before deployment. Batfish's known unsupported
sFlow statements have narrow exceptions; actual device read-back verifies the
operational state.

Fresh intent, backup, compliance and reviewed Config Plans preceded each
deployment. The off deployment was job
`762acf69-8242-4765-85a4-8c0274d1378a`; restoration was
`cd0ee2f2-e3cd-484d-9aa8-a8a8fda90ded`. Operational off state was verified at
01:56:47 UTC and restored on state at 02:00:01 UTC.

Each state had two captured, sequence-numbered UDP tests from DCB-k3s-w1
(10.100.0.20) to DCA-k3s-m1 (10.100.0.10). Each sent 5,000 datagrams with
128-byte payloads and a 4 ms sleep, about 242 packets/s rather than exactly
250. The receiver was ready before sending and allowed a drain interval.
Endpoint captures and an EVE host capture covered the test and its outer
VXLAN flow. Packet capture reported zero kernel capture drops in all six runs.

## Results

| sFlow state | Run 1 received / sent | Run 1 loss | Run 2 received / sent | Run 2 loss |
| --- | ---: | ---: | ---: | ---: |
| On, before change | 3,211 / 5,000 | 35.78% | 4,665 / 5,000 | 6.70% |
| Off | 3,706 / 5,000 | 25.88% | 4,721 / 5,000 | 5.58% |
| On, restored | 4,872 / 5,000 | 2.56% | 4,420 / 5,000 | 11.60% |

The outcome does not support sFlow being required to trigger the failure.
It does not prove that sFlow has zero overhead. Background traffic was not
held constant and the upstream path sometimes used DCA-Spine01, sometimes
DCA-Spine02. All six runs still traversed the same source and destination
leaves. Two runs per state do not establish a calibrated performance curve.
No agent restart or complete removal of sFlow configuration was performed.

In the first off run, 4,984 packets reached DCA-Leaf01 and only 3,706 left
toward the server. The other 16 of the original 5,000 disappeared across
DCB-Leaf02. In the second off run, all 5,000 reached DCA-Leaf01 and 4,721
left. The endpoint captures agree with the receiving application.

## Linux bridges versus the vEOS receive socket

Live EVE interface mappings identify the bridge members. Matching sequence
numbers across each observed bridge crossing found no missing test packets.
The measured median crossing times were roughly 2–4 microseconds. These
comparisons cover source attachment, leaf/spine links, CE-facing handoffs,
and destination attachment. They use timestamps from the same EVE host clock.
The largest measured bridge crossing across all six runs was 36 microseconds.

By contrast, delivered packets spent median spans of 1.41 and 1.39 seconds
across DCA-Leaf01 in the two off runs. The leaf span includes its virtual NIC
and forwarding path; it is not a measurement of one function inside EOS.

The first off run used the leaf's Ethernet2 uplink. Its Etba raw receive
socket reached 615,424 bytes against a 614,400-byte receive limit and added
1,634 socket drops during the observation interval. The inactive Ethernet1
socket remained nearly empty. Those counters include background traffic, so
they are not expected to equal the test-flow loss count.

The baseline monitored Ethernet1 and Ethernet5. After observing the alternate
spine path, monitoring included Ethernet2 for the off and restored phases.
Do not interpret an unmonitored baseline Ethernet2 as having zero drops.

The bridge captures and socket counters point away from a Linux bridge
forwarding-loss problem and toward packets arriving faster than vEOS's
forwarding process can drain them. They do not exclude guest scheduling,
QEMU/vNIC behavior, forwarding-agent performance or traffic burstiness as
reasons for that pressure. No bridge tuning, receive-buffer increase or CPU
change was performed.

Linux bridge counters alone are not proof of transit delivery. The primary
evidence here is matched packet observations on both sides of the bridge,
combined with guest socket-drop counters. The
[Linux bridge documentation](https://docs.kernel.org/networking/bridge.html)
describes bridge forwarding, and the
[ss manual](https://man7.org/linux/man-pages/man8/ss.8.html) defines the socket
memory and drop fields used in this analysis.

## NetFlow and evidence

CE1 NetFlow stayed enabled. The test's outer conversation is
`10.3.2.5:7966 -> 10.3.1.4:4789`. Stored records corroborate packets observed
at the router handoff; they cannot show which packet the downstream leaf
discarded. `final-audit.json` includes the traced records, restored sFlow
samples, final compliance, no-op plan generation and cluster health.

All six CE1 flow counts matched the corresponding captured router-handoff
counts: 4,999; 4,992; 4,984; 5,000; 4,977; and 4,987. A fresh leaf sFlow sample
was stored after restoration. Final flow-export and logging compliance both
passed. Plan generation job `f3f148bc-a4f5-4306-95fa-256c3c1b3c30` found no
missing configuration and created no plans. All nine K3s nodes were Ready,
all 12 Argo Applications were Healthy/Synced, and all four Longhorn volumes
were healthy at the final audit. These status checks do not imply loss-free
transport.

`comparison.json` records per-run bridge and leaf spans, counts, capture
statistics and socket summaries. The phase-labelled packet files and socket
monitor files retain the sanitized underlying observations locally. They
contain test sequence numbers and headers, not unrelated application payloads.
Large per-packet JSON files are not committed; the report and compact audit
artifacts are committed with the source tools.

The scripts are `telemetry/sflow_ab.py`, `telemetry/sflow_ab_report.py` and
`telemetry/sflow_ab_final.py`. The deployment helper rejects reused plans and
unexpected source or device state. This run's authorization does not authorize
another device change or a rerun of the experiment.
