# Approved GRO canary, 2026-09-09

The user approved the five-minute test on DCA-Leaf01 Ethernet5. The test changed
only generic-receive-offload on its Linux vmnicet5. It strongly supports receive
coalescing across the vEOS VXLAN forwarding path as a cause of oversized-packet
loss and TCP retransmissions. It does not establish a complete latency repair.

## Result

| Phase and response path | HTTP completions | Oversized VXLAN packets at DC-A spine | Source TCP payload retransmissions |
| --- | ---: | ---: | ---: |
| GRO off, DCA-Leaf01 | 12/12 | 0 | 1 |
| Concurrent unchanged DCA-Leaf02 | 5/12 | 12 | 22 |
| GRO restored, DCA-Leaf01 | 1/4 | 4 | 8 |
| GRO restored, DCA-Leaf02 | 2/4 | 4 | 5 |

Each connection is classified by its actual server-response path observed in
EVE, not by an assumed bond hash. There were 12 connections through each leaf
during the test, and four each afterward. No bond leg or route was changed.

The treated-path median completion time was 1.269 seconds, range 0.787-2.033
seconds. Its 12 completions returned HTTP 401 on the unauthenticated /livez path.
This proves transport/TLS/HTTP completion, not API readiness or fleet reliability.
One payload retransmission remained, and latency is still much higher than the
roughly 4 ms management path measured before this canary. The pre-existing
virtual-switch processing delays and any other loss mechanisms remain open.

All seven timeouts during the GRO-off batch used the unchanged second leaf.
The same oversized-packet behavior returned on DCA-Leaf01 after GRO restoration,
with three timeouts in four requests. This treatment/control/reversal comparison
is stronger evidence than the earlier endpoint-only TSO/GSO experiment.

See [per-connection analysis](analysis.json), [GRO-off probes](gro-off/probes.jsonl),
[restored probes](restored/probes.jsonl), and the header-only captures in those
folders. The analyzer counts overlapping source TCP payload sequence ranges
on bond0, avoiding the duplicate slave-interface observations. It does not count
pure ACK retransmissions or treat each selective ACK as a unique lost packet.

## Execution and restoration

- All nine K3s nodes were Ready before the change.
- A unique systemd timer was created and confirmed active before disabling GRO.
  It was configured to restore GRO after 300 seconds independently of the session.
- GRO was verified off at 20:59:20 UTC and restored on at 21:00:59 UTC.
- Both leaf EVPN sessions remained Established with increasing uptime and
  unchanged received/accepted prefix counts in the before/after samples.
- All nine nodes were Ready after restoration.
- An independent final read verified GRO on, then stopped the now-unneeded
  timer and confirmed it inactive. A second GRO read again confirmed on.

See [device events](device-events.json), [cluster before](cluster-before.json),
[cluster after](cluster-after.json), and [final restoration](final-restoration.json).
This was a direct runtime diagnostic, not a Nautobot Job or Config Plan deployment.
Errors in the runner abort the experiment, and its finally block restores GRO;
the device-local timer supplies a second restoration path.

Each capture reported listening before probes began. All six captures reported
zero kernel drops. The probes used a 2-second connection timeout, which also
bounds TLS setup, and a 3-second overall limit. Failed requests were not discarded
from the result counts. No source-host offloads, MTUs, NIC models, CPU allocations,
startup configs, storage objects or other devices were changed.

## Persistent repair preparation

[The candidate config](gro-persistence-candidate.cfg) describes a source-managed
on-boot handler for this one verified interface. It is a draft, not deployed and
not yet integrated into the active template or compliance loader. The command
matches the successful canary; handler syntax and activation timing require
validation on the installed EOS release before deployment.

The next implementation should:

1. Render the handler from an explicitly scoped device context through the EOS
   platform template. Do not enable it globally for arista_eos, physical switches,
   or unverified interfaces. The current interface description is stale; preserve
   the verified MAC/interface binding as a gate.
2. Extend the active jobs/gc_compliance_setup loader's platform rule to include
   the managed handler, update mock contexts, and run make ci plus make ci-full
   when Batfish is available. Never hand-edit generated intended or backup files.
3. Verify the action's exit status, GRO read-back, behavior after an agent restart
   and after an approved reboot. An on-boot handler alone does not prove persistence
   across a driver/interface recreation or later offload reinitialization.
4. Regenerate intended config, fresh backup, compliance and the exact Config Plan;
   deploy only in a separately approved run with Fail Job on Task Failure enabled.
5. After verifying one device, prepare bounded expansion to the corresponding
   second leaf interface and other verified server-facing interfaces. Longer
   transport and storage verification must precede Longhorn recovery work.

Rollback must remove the managed handler from source and running configuration
and explicitly restore GRO on. Removing the handler alone does not reverse the
live ethtool setting. There is no persistent fix applied by this test.

Arista's [event-handler documentation](https://www.arista.com/en/um-eos/eos-command-line-interface-cli)
describes action bash, boot triggers and configurable delay. Boot-triggered
handlers may also execute when their configuration mode is exited, so deploying
the candidate is itself a live change. Boot timing on EOS 4.34.6M has not been tested.
