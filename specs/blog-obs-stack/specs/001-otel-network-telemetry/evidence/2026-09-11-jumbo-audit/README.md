# Live jumbo MTU audit, 2026-09-11

Read-only Nautobot-backed Netmiko checks succeeded on three CEs and fifteen
Arista switches. No configuration was changed and no end-to-end jumbo probe
was run during this audit.

| Segment | Live MTU |
| --- | --- |
| CE1/2/3 Gi3 and Gi4 toward spines | 9216 |
| All six spine Ethernet10 ports toward CEs | IP MTU 1500 |
| CE1/2/3 Gi5 toward Leaf03 | 9216 |
| All three Leaf03 Ethernet10 ports toward CEs | IP MTU 8950 |
| Spine-to-leaf routed links | IP MTU 8950 |
| Leaf server/storage VLAN interfaces | IP MTU 1500 |

Server-facing switched ports and port-channels report Ethernet MTU 9214;
this is not proof that host NICs, bonds, VLANs or routed paths support the
same IP packet size. Hosts, CNI and hypervisor bridges were not rechecked.

The source comment at golden-config/templates/eos/interfaces.j2:55 records
8950 as a deliberate workaround for historical 9000-byte EVE-NG/Proxmox virtual
transport limits and EVPN BGP stalls. It is historical rationale, not a fresh
measurement of those bridges. Verify actual virtual transport before raising
Arista MTUs. Router virtio changes do not establish the Arista transport limit.

End-to-end jumbo support is not established. CE-to-Arista, fabric transport,
routed VLANs and hosts require a coordinated packet-size budget including
encapsulation overhead and end-to-end validation.
