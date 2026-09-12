# pyATS baseline and TCP trace, 2026-09-09

Completed a live Nautobot inventory reconciliation, fleet pyATS collection and
matched TCP traces. The lab is not yet stable enough for additional telemetry
load. The tests narrowed the failure and rejected two proposed mitigations.

## Fleet result

All 28 selected names and management addresses matched the testbed. 25 devices
completed their command sets: 15 EOS switches and 10 IOS-XE routers. CE1, CE2 and
RR1 closed their pyATS sessions during setup on both the initial attempt and a
bounded retry. Their exception chains end in EOF; this is a collection failure,
not proof that those devices are down. Hostname learning was enabled throughout.
A later credential-redacted, in-memory CE1 transcript at 03:18:41 UTC showed
OpenSSH reporting "No route to host" before authentication. This identifies the
immediate CE1 failure as management-path reachability at that time; the other
two devices were not proven to have the same cause.

Every successfully checked IOS-XE device reported throughput level 20000 kb/s.
This is a configured ceiling, not evidence that current traffic saturates it.
The paired counters showed 31 new ingress discards on DCB-Leaf01 Et6/Po6, which
represent the physical interface and its aggregate and must not be double-counted.
SPE1 reported one additional MplsFragReq drop. Other successfully paired Cisco
QFP drop counters did not increase. DCC-Leaf01 counters were flat during this
sample, despite an increase in the previous investigation.

See [fleet summary](fleet/summary.json), [inventory](fleet/inventory.json),
[retry summary](retry/summary.json), [DCB-Leaf01](fleet/DCB-Leaf01.json),
[SPE1](fleet/SPE1.json). Each command has a UTC timestamp; samples are staggered.

## Targeted trace

Endpoints were verified as DCC-k3s-w4 (192.168.100.30) and DCA-k3s-m2
(192.168.100.11), reached through management SSH addresses .3.69 and .3.64.
Both captures had to report ready before probes started. Dedicated source ports
separate the tests from normal cluster traffic. Captures contain TCP header
summaries, not hex or ASCII packet dumps. Probes made unauthenticated /livez
requests; HTTP 401 counts as completed transport/TLS/HTTP, not API readiness.

The first capture-start attempt failed its local readiness detector and issued
no probes. The corrected run used raw pipe reads to avoid buffered-line ambiguity.

In the handshake batch, seven requests timed out, two completed and one failed
locally to bind its requested source port (curl code 45). The bind failure is
excluded from network failure counts. Every timed-out network request had both
its SYN arrive at master 2 and a SYN-ACK return to the worker. The earlier phrase
"connection timeout" must not be interpreted as failure of the initial TCP
handshake. See [handshake probes](handshake/probes.jsonl).

The detailed batch had five TLS timeouts and one completed request. On port
46000 the worker sent its 517-byte initial TLS payload, which master 2 acknowledged.
Master 2 then emitted sequence range 2808889551:2808890973 (1422 payload bytes
in the host's pre-segmentation capture). The worker subsequently received only
2808890899:2808890973 (74 bytes) and selectively acknowledged that tail while
continuing to acknowledge 2808889551 as the next required byte. The preceding
1348 bytes were missing at the receiving endpoint. The exact dropping hop is
not yet identified. See [master trace](tcp-detail/master2.txt),
[worker trace](tcp-detail/worker4.txt), and [probe results](tcp-detail/probes.jsonl).

Outgoing checksum warnings in host captures are not proof of corrupt packets:
observed arriving handshake packets had correct checksums. Pre-segmentation
capture sizes also do not establish the frame size on every downstream link.

## Controlled comparisons

| Test | Result | Interpretation |
| --- | --- | --- |
| Default MSS versus socket MSS 1200, alternating four requests each | Default: one success, three TLS timeouts. MSS 1200: four TLS timeouts. | Smaller segments did not resolve the failure. |
| TSO/GSO temporarily disabled on master-2 bond0, six requests | Three successes, three timeouts. | Not a complete fix; sample size and changing path conditions do not establish a performance improvement. |

The socket MSS test changed only its own sockets. The TSO/GSO test first scheduled
an independent 90-second rollback with systemd. Only master-2 bond0 was changed;
no interface was brought down. The settings were confirmed off during the test,
and on afterward. The API readiness check returned ok after restoration. An
attempt to stop the already-expired rollback timer returned unit-not-loaded;
this did not prevent restoration. See [restoration](restoration.json),
[MSS probes](mss-comparison/probes.jsonl), and [offload probes](tso-disabled/probes.jsonl).

Failures occurred with replies using either ens19 or ens20. Neither a single
master bond leg nor source-host TSO/GSO alone explains the sampled fault. No
permanent network tuning, device config deployment, commit or push was performed.

## Next repair boundary

Follow the missing server-to-worker sequence range through the EVE leaf-facing
taps and VXLAN/MPLS path. Use the same dedicated ports and captures with verified
start times to identify the first point where the bytes disappear. At that point,
correlate the exact hop's discard reason, encapsulated frame size and forwarding
load. Do not roll out CPU, MTU or offload changes based solely on these endpoint
captures. Resolve the three pyATS setup failures independently of the data-plane
trace. Longhorn repair remains gated on reliable transport and preserving its
surviving VictoriaMetrics replica.

The reusable collector is tools/lab_network_baseline.py in blog-sandbox. Its real
fleet run, Python compilation and git diff --check were used for validation.
