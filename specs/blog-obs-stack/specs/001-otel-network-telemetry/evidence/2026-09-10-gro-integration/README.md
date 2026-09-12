# GRO source integration and MTU check, 2026-09-10

The source fix is implemented locally for DCA-Leaf01 Ethernet5 only. No device
configuration was changed during this integration. GRO remains restored from
the previous canary; no persistent handler has been deployed.

## GRO and MTU

Generic Receive Offload (GRO) combines compatible received packets so the kernel
can process fewer objects. A forwarding path must segment the combined data
appropriately before sending it through an interface with a smaller MTU.
See the [Linux offload documentation](https://docs.kernel.org/networking/segmentation-offloads.html).

The [controlled canary](../2026-09-09-gro-canary/README.md) showed that disabling
GRO on the receiving vEOS leaf interface removed the 1522-1524-byte VXLAN packets
on that path. The defect returned when GRO was restored. This supports a
coalescing/segmentation failure at the virtual forwarding boundary, rather than
an arbitrary reason to increase every MTU.

Current read-only samples:

| Layer or path | Reported MTU | Evidence scope |
| --- | ---: | --- |
| Master 2 cni0 and flannel.1 | 1350 | Live ip link read-back |
| Master 2 bond0 | 1400 | Live ip link read-back |
| Leaf-to-spine routed links | 8950 IP | DC-A/DC-C sampled leaves and Spine01 |
| Spine01 Ethernet10 toward CE | 1500 IP | DC-A and DC-C |
| CE3 Ethernet interfaces | 1500 | Live show interfaces |

The 1350-byte pod IP packet plus one IPv4 VXLAN encapsulation consumes roughly
1400 bytes at the host layer; another such encapsulation consumes roughly 1450
bytes as the outer fabric IP packet. This is header-budget reasoning for the
usual untagged inner Ethernet/IPv4 VXLAN headers, not a measured end-to-end PMTU
result for every pod flow, label stack or encapsulation variant. Correctly
segmented traffic has headroom at the sampled 1500-byte boundary.

The larger intra-DC MTU does not make the whole inter-DC path jumbo-capable.
GRO recreates larger packets despite the reduced host MTU, and the next smaller
boundary exposes that failure. A full-lab MTU inconsistency has not been established.
CE1's collection failed with NetmikoTimeoutException; no live MTU claim is made
for it. [Raw samples](mtu-path.json) retain results and failed observations.
The filtered output does not preserve every interface header, so use only named
Ethernet interfaces when attributing its MTU lines.

The existing EOS interface template documents an earlier 9214-versus-9000 virtual
wire issue as the reason for its 8950 default. That is historical source commentary,
not a newly reproduced finding in this run. Avoid conflating it with this GRO test.

## Source implementation

- Device-local context: config_contexts/devices/DCA-Leaf01.yaml. It selects the
  exact hostname, Ethernet number 5 and GRO state off.
- EOS platform template: renders one boot event handler with a 60-second delay
  and the successful ethtool command. Mismatched hostname, non-integer or
  out-of-range port, missing modeled port and invalid GRO state fail rendering.
  Only bounded integers and enumerated values enter the shell action.
- Active compliance loader: the EOS platform rule now includes only the managed
  event-handler lab-gro-off- prefix, preserving unrelated event handlers.
- Mock and tests: a separate synthetic canary fixture exercises full rendering
  and Batfish, scope rejection, unsafe values, and active restoration to gro on.

The context is device-local under the repository's existing devices/ convention;
there is no platform-wide activation or independently maintained fleet list.

## Validation and remaining deployment gates

make ci passed 71 tests and Jinja lint. make ci-full repeated those checks and
passed 149 additional Batfish/intended-config checks. Its four pytest fixture
deprecation warnings are unrelated to this change. The new canary fixture was
included in the Arista parser snapshot. No parser-warning exception was added.

Batfish parsing does not prove shell execution, event-handler privileges, boot
ordering or behavior after agent/interface recreation on EOS 4.34.6M. Those remain
live validation gates. Source files are uncommitted; unrelated Ansible edits were
preserved. Generated intended-configs and backup-configs were not edited.

For the next separately approved persistent-device run:

1. Review/commit/sync the source and run the active compliance setup job.
2. Regenerate intent, fresh backups, compliance and an exact Config Plan. Confirm
   it contains only the intended handler change for DCA-Leaf01; stop on unrelated
   device drift. Confirm Ethernet5 MAC 50:00:00:03:00:05, kernel vmnicet5 and actual
   master-2 wiring. The interface description is stale.
3. Use Fail Job on Task Failure. Check per-device JobLogEntry, action exit status,
   saved configuration and actual ethtool state. A boot handler can also trigger
   when its configuration mode exits, so deployment is a live packet-handling change.
4. Repeat the matched traffic test and observe whether EOS overwrites the setting.
   A reboot or agent restart requires an explicitly scoped test run; it is not
   included in the completed runtime canary authorization.
5. Keep fleet expansion, residual latency work and Longhorn repair gated on results.

Rollback is explicit: change the context's gro value to "on", regenerate a fresh
Plan and verify the handler restores the live setting. Then remove the handler
through reviewed source/Plan cleanup if desired. Merely deleting its configuration
or its context does not reverse an existing ethtool setting, and a merge-only Plan
must not be assumed to remove an absent stanza. Retain an independent management
connection and a bounded restoration mechanism during the next canary deployment.

The [Arista event-handler reference](https://www.arista.com/en/um-eos/eos-command-line-interface-cli)
documents the command family; runtime persistence remains unverified here.
