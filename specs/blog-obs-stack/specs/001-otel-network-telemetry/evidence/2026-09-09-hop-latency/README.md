# Fabric latency investigation, 2026-09-09 evening

Live read-only investigation resumed after the automation workstation restart.
No device, hypervisor, offload, MTU, storage or Kubernetes configuration was changed.

## Findings

The traced flow is DCC-k3s-w4 (192.168.100.30) to DCA-k3s-m2
(192.168.100.11), TCP 6443. Their management SSH addresses are 192.168.3.69
and 192.168.3.64. The nine K3s nodes were Ready on the initial read-back;
VictoriaMetrics remained attached/degraded and Grafana attached/healthy.
The worker's three management-path HTTPS probes completed in 4.2-4.4 ms.
Fabric HTTPS probes were substantially slower. These unauthenticated probes
return 401, proving transport/TLS/HTTP completion, not authenticated readiness.

Two matched capture batches completed 8/8 and 12/12 requests. The second
batch took 0.566-2.805 seconds per request. Successful completion concealed
TCP retransmissions, so these results are not evidence of reliable transport.

### Oversized VXLAN and retransmissions

For all 12 repeat-batch connections, the DC-A leaf emitted an outer IPv4 VXLAN
packet of 1522-1524 bytes with DF set. These packets were observed entering
DCA-Spine01 from either DCA-Leaf01 or DCA-Leaf02. Matching packets were not
observed leaving that spine. The initial TCP payload was subsequently retransmitted.

For port 48100, the evidence is especially direct:

1. EVE delivered two TCP segments to DCA-Leaf01 Ethernet5, carrying sequence
   3534697795:3534699143 (1348 bytes) and 3534699143:3534699216 (73 bytes).
2. The leaf emitted their combined 1421-byte TCP payload inside a 1523-byte
   outer IPv4 VXLAN packet. DCA-Spine01 Ethernet1 received it.
3. The original combined packet was not observed leaving the spine. A later
   retransmission of the tail arrived at the worker, which selectively
   acknowledged it while still requesting the first 1348 bytes.
4. The first 1348 bytes were retransmitted roughly one second after their
   original transmission and then traversed the path successfully.

See [oversized packets](hop-trace-repeat/oversized-vxlan.json),
[EVE capture](hop-trace-repeat/eve.txt), [worker capture](hop-trace-repeat/worker4.txt),
and [probe results](hop-trace-repeat/probes.jsonl). Packet captures contain decoded
headers only, without payload dumps or authentication traffic.

This identifies a failure boundary at the DC-A spine and makes receive
coalescing followed by incomplete segmentation across the leaf's VXLAN forwarding
path a specific repair hypothesis. GRO was observed enabled on the leaf's
vmnicet5. A dedicated DCA-Spine01 read-back recorded 2,481,831 MTU-exceeded
exceptions and its routed Ethernet10 MTU was 1500. The counter is cumulative,
not a count of this probe batch. The hypothesis still requires a controlled GRO-off comparison.
A large packet in a host capture alone does not prove a wire-MTU fault; the
combination of separate ingress segments, merged leaf output, missing spine
output, MTU exception counters and later retransmission is the relevant evidence.

### Per-switch delay

All EVE hop timestamps use the same host clock. Matching TCP headers and
sequence numbers show the following repeat-batch medians, restricted to packet
keys with exactly one ingress and egress observation at each switch:

| Switch | Matched packets | Median transit (ms) |
| --- | ---: | ---: |
| DCC-Leaf02 | 85 | 13.195 |
| DCC-Spine01 | 347 | 11.084 |
| DCA-Spine01 | 347 | 10.819 |
| DCA-Leaf02 | 260 | 14.807 |
| DCA-Leaf01 | 87 | 22.810 |
| DCC-Leaf01 | 262 | 18.249 |

The CML router path plus PVE handoffs between EVE's CE-facing interfaces had a
1.485 ms median in the repeat batch and 2.986 ms in the first batch. This is an
aggregate span, not an individual router measurement. The data narrows the
present latency to vEOS processing and its local virtual I/O path rather than
justifying a C8000V CPU increase.

The EVE scheduler sample recorded about 0.8-3.1 ms of runnable wait for the busy
sampled QEMU threads across ten seconds. EVE vmstat showed 61-63% idle during
five intervals with no reported steal or swap. These short samples do not rule
out other scheduling effects inside the nested switch or on PVE.

DCA-Leaf01 and DCC-Spine01 report Arfa personality on EOS 4.34.6M (i686).
The Etba process being a Python executable is not proof that Arfa is disabled;
the installed launcher also initializes native Arfa components. A forwarding-agent
switch is therefore not proposed on the basis of its process name.

## Capture limitations

Capture start was confirmed on both endpoints and EVE before probes began.
The repeat capture reported zero kernel drops at all three collectors. Capture
and received-by-filter totals differ at the timeout boundary. There was a long
quiet tail after the probes; the evidence does not rely on packets at shutdown.
The first run did not save final capture-drop statistics.

`analyze-experiment.py` reports header-preserving transit spans. Segmentation or
coalescing changes a packet's key, so unmatched egress in `missing-egress.json`
is a diagnostic candidate, not a packet-loss count. The oversized-packet analysis
uses sequence ranges and endpoint retransmissions separately. Unsupported CLI
commands and delayed output from the broad kernel-offload CLI are retained as
incomplete observations; use the dedicated preflight queries for exact settings.

## Proposed canary

The [canary plan](gro-canary.md) was subsequently executed with user approval.
See [the results](../2026-09-09-gro-canary/README.md): the treated path improved,
the defect returned after restoration, and no permanent fix was applied.
The test targets only DCA-Leaf01's master-2-facing receive interface. It must
restore the original state automatically and verify restoration explicitly.
A successful canary would justify preparing a persistent source-controlled fix,
not immediate fleet expansion. The previous source-host TSO/GSO test did not
change this leaf receive path.

Longhorn repair remains gated on transport reliability and preserving the
surviving VictoriaMetrics replica. No volume or replica was deleted or detached.

## References

- [Linux segmentation offloads](https://docs.kernel.org/networking/segmentation-offloads.html)
  explains GRO/GSO and tunnel segmentation. Applying it to this trace is an inference.
- [Arista Arfa overview](https://www.arista.com/en/support/toi/tag/veos-lab)
  identifies the newer forwarding agent. The detailed TOI required login and was
  not available; no unverified feature-matrix claim is made.
