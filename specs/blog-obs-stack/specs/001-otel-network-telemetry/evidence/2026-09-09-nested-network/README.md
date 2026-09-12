# Nested network investigation, 2026-09-09

Read-only investigation of PVE, EVE-NG, CML and selected network nodes. No emulator
VM, virtual NIC, router configuration or kernel setting was changed in this run.
The evidence narrows useful experiments; it does not establish a single root cause.

## New findings

| Finding | Evidence | Interpretation |
| --- | --- | --- |
| Every running C8000V has one vCPU | CML QEMU command-line selections | Outer CML's 40 vCPUs do not give each router multiple CPUs. Test a supported larger node allocation on a canary. |
| CE3 reports 20000 kb/s throughput level | Router read-back | A 20 Mb/s configured ceiling matters for storage traffic. Sampled input/output was about 5 Mb/s each and QFP load 9% over five seconds, so saturation is not proven. |
| Every running vEOS uses two vCPUs and E1000 NICs | EVE QEMU selections | Hardware NIC emulation adds work inside the nested VM. Check exact-image compatibility before testing another model; E1000 may be the supported template default. |
| Sampled outer VirtIO NICs have one maximum/current combined queue | ethtool inside both emulators | A small multiqueue experiment is possible; there is no evidence that adding queues everywhere will fix the lab. |
| DCC-Leaf01 Et1 ingress discards rose from 96011 to 96074 | Two switch samples | 63 new discards on the uplink toward DCC-Spine01. The counter does not identify the dropped protocol or prove buffer exhaustion. DCA-Leaf01 counters were unchanged. |
| CE3 has 496 MaxTu drops since last clear | QFP counters | Historical MTU drops warrant attribution, not an immediate MTU change. |

Sources: [EVE host](nested-118.json), [CML host](nested-5001.json),
[initial device checks](lab-nested-devices.json),
[second discard sample](lab-discard-second.json),
[CE3 capacity](lab-router-capacity-partial.json).

CE3 platform CPU reported 68% over five seconds and 80% over one minute. QEMU
process CPU percentages from ps are lifetime averages, not synchronized load
samples. Polling dataplanes can consume CPU while idle; these numbers alone do
not establish saturation. The next CPU experiment needs interval measurements,
packet-loss and latency comparisons under the same offered traffic.

## Checks that reduce other suspicions

KVM acceleration, nested virtualization, EPT, APICv and shadow VMCS are enabled
in the sampled environments. Both outer VMs use host CPU passthrough, two sockets
with 20 cores each, and NUMA enabled. PVE has two physical 24-core sockets with
SMT, totaling 48 physical cores and 96 logical CPUs. Extra allocation is not a
substitute for checking per-node execution and scheduling.

No netem, tbf or htb shaping qdisc was found in the sampled guest qdisc lists.
Both hosts had zero cumulative softnet backlog drops, though time_squeeze counts
were nonzero. Those cumulative budget-exhaustion counters are not proof of current
loss. Offloads are enabled on sampled outer VirtIO NICs; no offload defect was
proven and no blanket disable was performed.

CML has extra outer interfaces on VLANs 407-412, which the design describes as
server links. VLAN 407's CML bridge currently has only its physical member;
other extra interfaces are not bridge members in the sample. This is configuration
drift, not an established forwarding loop. A firewall flag exists on CML net15
(VLAN 425), but no explicit VM firewall enable setting was returned. The cluster
firewall-options query failed, so active filtering was not established.

Low-rate DF ping probes from dcc-k3s-w4 to all three masters passed all 18 probes
at 1200 and 1372 bytes of ICMP payload (1228 and 1400-byte IP packets). RTTs were
approximately 190-380 ms at both sizes. This does not demonstrate full path MTU
for every encapsulation/ECMP leg, but it does not support lowering the current
1400-byte host MTU as the first repair.

## Prioritized experiments

1. Measure latency, TCP retransmissions, forwarding CPU and discard deltas on a
   fixed DC-C/DC-A test flow. Follow DCC-Leaf01 Et1 and isolate each ECMP/bond leg
   in a controlled test. Avoid interpreting ICMP success as TCP reliability.
2. Test a supported two-vCPU C8000V canary with the same image and traffic after
   saving its startup configuration and lab definition. Keep its throughput
   entitlement unchanged and compare CPU, tail latency and loss. If useful,
   expand by approved waves; do not assume every router needs more resources.
3. Validate an alternative NIC model for vEOS-lab 4.34.6M in a disposable clone.
   Verify boot, interface order, EVPN/ESI and forwarding before considering any
   live E1000-to-VirtIO change. CloudEOS/vEOS Router documentation does not prove
   compatibility for this vEOS-lab image.
4. Test two or four VirtIO queues on a selected outer handoff, with matching guest
   channel verification. Preserve MAC/VLAN/MTU. Compare before/after and revert
   on regression. Treat offload toggles as separate experiments only after a
   packet trace implicates segmentation/checksum handling.
5. Measure the actual inter-DC throughput ceiling and budget Longhorn rebuild
   traffic against it. Cisco documents limited CML C8000V forwarding performance;
   faster hypervisor NICs cannot remove an image or entitlement limit. If storage
   requires more than the fabric can deliver, use a suitable licensed forwarding
   platform or place infrastructure transport on a separate network.

Each experiment needs a concrete saved configuration and restoration procedure.
Network-device deployment follows the existing per-run approval and canary rules.
No arbitrary timer increases, fleet NIC replacement, licensing changes or broad
CPU pinning are justified by this evidence.

## Vendor references

- [Cisco CML C8000V limitations](https://developer.cisco.com/docs/modeling-labs/cat-8000v/): published throughput tests, not a measurement of this lab.
- [Cisco throughput configuration](https://www.cisco.com/c/en/us/td/docs/routers/C8000V/configure-licenses-throughput-c8000v.html): throughput and licensing must be considered together.
- [Proxmox multiqueue implementation](https://lists.proxmox.com/pipermail/pve-devel/2014-June/011699.html): multiple queues allow parallel host processing.
- [Linux multiqueue documentation](https://docs.kernel.org/networking/multiqueue.html).
- [EVE supported virtualization requirements](https://www.eve-ng.net/index.php/supported-hardware-and-software-systems/).
