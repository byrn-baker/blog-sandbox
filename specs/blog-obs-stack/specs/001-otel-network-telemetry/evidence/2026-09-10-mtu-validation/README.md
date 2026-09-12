# Lab MTU validation, 2026-09-10

A coordinated MTU design is justified. Setting every interface to the same value is not sufficient. The measured cross-site IPv4 path MTU is 1492 bytes, while intra-site links can pass larger packets. The earlier GRO canary demonstrated a separate packet coalescing failure that must remain part of the fix.

This run changed no device configuration, MTU, offload setting or workload declaration. DF probes can populate ordinary kernel path-MTU caches. Sources are live Nautobot inventory, read-only Netmiko commands, bounded ICMP probes, and read-only PVE guest inspection. Collection began at 01:17 UTC.

## Measured configuration

The fleet inventory contains 28 network devices. Collection succeeded on 26. CE1 and RR1 failed twice with NetmikoTimeoutException. These are collection failures, not proof of reachability failure. All 15 EOS devices and 11 IOS XE devices returned interface state.

| Layer or interface | Observed MTU | Coverage |
| --- | ---: | --- |
| EOS leaf/spine fabric routed links | 8950 IP | All three sites |
| EOS spine Ethernet10 toward CE | 1500 IP | All six spines |
| IOS XE GigabitEthernet | 1500 | All 11 collected routers |
| Operational MPLS links | 1500 MPLS | Collected P/PE routers |
| EOS Leaf03 Ethernet10 | 8950 IP | All three sites |
| EOS tenant SVIs | 1500 IP | All nine leaves |
| EVE host non-loopback interfaces | 9000 | 250 interfaces |
| CML host data interfaces/links | 9000 | Management and ancillary bridges include 1500 |
| K3s master2 bond0 / flannel.1 / cni0 | 1400 / 1350 / 1350 | Earlier same-investigation read, not repeated fleet-wide here |

EOS Ethernet MTU 9214 on switchports and IP MTU on routed ports are different reported quantities. Loopback MTUs are not transport capacity measurements.

The modeled Leaf03 Ethernet10 to CE GigabitEthernet5 pairs have 8950 versus 1500 at DC-B and DC-C. DC-A CE1 could not be collected. LLDP on the two sampled Leaf03 ports reported zero neighbors, so actual wiring for these pairs remains to be independently checked before configuration changes. Source topology pairs are in jobs/sp_demo_lab/context/__init__.py. The EOS interface template defaults routed interfaces without explicit modeled MTU to 8950; the Leaf03 links need explicit treatment in any revised design.

## Packet-size tests

Sources and destinations were Leaf01 VTEP loopbacks: DC-A 10.3.1.4, DC-B 10.3.2.4, DC-C 10.3.3.4. Commands ran in the EOS default network namespace, with explicit source and DF set. Sizes below include the IPv4 header, not just ping payload. Three probes were sent per size and direction.

| Test | Result |
| --- | --- |
| Six directed cross-site pairs, 1450 bytes | 18/18 replies |
| Six directed cross-site pairs, 1492 bytes | 18/18 replies |
| Six directed cross-site pairs, 1493 bytes | 0/18 replies; ICMP fragmentation-needed or cached local MTU rejection |
| Initial DC-A/DC-C tests, 1500 bytes | Both directions received fragmentation-needed, MTU 1492 |
| DC-A Leaf01 to Leaf02, 1450/1500/1524/8000 bytes | 3/3 replies at every size |

The first oversized probes returned fragmentation-needed from the ingress PE addresses 172.16.1.0, 172.16.2.0 and 172.16.3.0. Later attempts could be rejected locally using the learned 1492 PMTU. Those local errors are not additional observed wire drops. Initial cross-site 1524 and 8000 attempts were also rejected by the cached PMTU.

Live CEF in CUST-A shows a VPN label plus a transport label for remote VTEPs. This supports the eight-byte reduction from the configured MPLS MTU: 1500 minus two four-byte labels equals 1492. Raw outputs are in labels/. The exploratory UNDERLAY VRF lookup in peers/ failed because that VRF does not exist; the subsequent CUST-A lookups are the valid evidence. Collector ok fields do not classify every CLI error or ping outcome; inspect the command output.

These probes establish the limit on sampled routes, not every ECMP member or a sustained reliability guarantee. Successful cross-site 1492-byte probes had average RTTs of roughly 63 to 86 ms. MTU fit does not remove the residual forwarding latency.

## Encapsulation budget

For the observed IPv4 encapsulation, VXLAN adds 50 bytes to the inner IP packet, including its inner Ethernet header. Flannel VXLAN adds another 50 bytes for pod traffic before the fabric VXLAN. The observed MPLS stack adds eight bytes.

| Traffic | Packet-size budget |
| --- | --- |
| Current host packet | 1400 + 50 fabric VXLAN + 8 MPLS = 1458 |
| Current pod packet | 1350 + 50 Flannel + 50 fabric VXLAN + 8 MPLS = 1458 |
| A 1500-byte host packet | 1500 + 50 fabric VXLAN + 8 MPLS = 1558 |

The existing 1400/1350 sizes fit the observed 1492-byte outer-IP path limit. Raising hosts to 1500 without increasing transport capacity would violate it. IPv6 outer headers, extra tags, additional labels and other tunnels require their own accounting.

GRO means Generic Receive Offload. It combines received packets so software processes fewer, larger units. The prior canary traced separate TCP segments becoming an oversized VXLAN packet at the leaf. On the treated leaf, disabling GRO produced 12/12 successful requests with no oversized packets, while the concurrent untreated leaf had 5/12 successes. Restoring GRO brought oversized packets back. See ../2026-09-09-gro-canary/README.md. A larger MTU could accommodate the particular 1522-1524-byte packets observed, but it has not been shown to bound all future GRO aggregates. The scoped workaround remains relevant.

## Platform limits and proposed direction

Live QEMU options confirm E1000 NICs for the 15 EVE switches and vmxnet3 for the CML router VMs. Cisco's CML documentation describes a 2034-byte DF limit for vmxnet3 and up to 9216 with virtio. This is a documented constraint, not a limit reproduced here. Driver replacement can require wiping/restarting CML nodes and is outside this validation.

Arista's AVD example recommends 1500 for virtual fabric uplinks. Our successful intra-DC 8000-byte probe shows that this recommendation alone is not proof that this installed vEOS version cannot pass jumbo packets. It is also not evidence for jumbo support across CML.

Recommended sequence:

1. Retain host 1400 and pod 1350 during stabilization. Complete the already prepared scoped GRO workaround canary before broader offload changes. Its persistent event-handler behavior is still unverified.
2. Declare separate service, fabric IP, MPLS and virtual transport budgets in source. Resolve the modeled Leaf03-to-CE mismatches after confirming wiring. Existing larger Linux bridge MTUs can remain as capacity ceilings; they need not equal service MTUs.
3. For eventual 1500-byte host service across VXLAN, prepare a 1600-byte fabric/CE transport and at least 1600-byte MPLS carrying capacity as a canary candidate. The calculated requirement for the observed stack is 1558 bytes. Exact IOS XE interface/IP/MPLS commands and semantics must be verified before rendering a deployment plan. This candidate is below the documented vmxnet3 limit but has not been tested live. It is not an approved fleet setting.
4. If retaining the smaller host service, a 1500-byte IP transport design with explicit MPLS label headroom is another valid target. A blanket 1500 everywhere would still leave the label overhead problem. Do not assume lowering EOS fabric MTUs fixes GRO; it could move the drop to another interface.
5. Before rollout, test the chosen budget on a complete approved path, including both directions, alternate routes, normal and oversized DF traffic, VXLAN TCP/TLS captures, pod traffic and storage traffic. Confirm no MTU exceptions or retransmission regression, then regenerate intent/backups/compliance/Config Plans and deploy in approved platform waves.

No fleet MTU change is validated for deployment by this read-only run. The validated result is the current 1492-byte cross-site boundary and the need to account for both encapsulation and GRO behavior.

## Sources and evidence

- [Cisco CML CAT 8000V limitations](https://developer.cisco.com/docs/modeling-labs/cat-8000v/)
- [Arista AVD fabric topology settings](https://avd.arista.com/6.0/docs/howto/fabric_topology/index.html)
- fleet-and-probes/: live inventory, configured MTUs, initial DF tests and boundary tests.
- labels/: CEF VPN and transport labels for all three site pairs.
- peers/: exploratory LLDP and MPLS reads, including the unsuccessful VRF lookup.
- virtualization-118.json and virtualization-5001.json: current host link MTUs and QEMU NIC models.
- Collection helpers accompany this report. They use existing Nautobot secrets in memory and do not contain credentials. Several helpers expect the initial collector at its recorded /tmp path; adapt paths before reuse.
