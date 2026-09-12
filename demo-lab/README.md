# SP Demo Lab: Design & Build Guide

A complete service provider demo lab running on Proxmox, CML and EVE-NG, featuring an MPLS
L3VPN core with 3 datacenter customers sharing one K3s cluster and distributed
services. Purpose: demonstrate network configuration, monitoring, and
observability across a realistic multi-tenant SP environment.

## Documents

| File | Content |
|------|---------|
| [01-addressing.md](01-addressing.md) | IPv4/IPv6 addressing plan |
| [02-sp-core-topology.md](02-sp-core-topology.md) | SP core design (routers, MPLS, BGP) |
| [03-vrf-design.md](03-vrf-design.md) | L3VPN / VRF customer design |
| [04-datacenter-design.md](04-datacenter-design.md) | Per-DC topology, K3s cluster, services |
| [05-cml-proxmox-integration.md](05-cml-proxmox-integration.md) | CML ↔ Proxmox bridging, VM specs |
| [06-services-distribution.md](06-services-distribution.md) | K3s workloads split across DCs |
| [06a-ansible-automation.md](06a-ansible-automation.md) | Nautobot-sourced Ansible: inventory, roles, BIND, K3s |
| [07-monitoring-scenarios.md](07-monitoring-scenarios.md) | Demo failure scenarios and observables |
| [08-hypervisor-interconnect.md](08-hypervisor-interconnect.md) | **As-built** VLAN map: CML ↔ EVE-NG ↔ VMs, MTU chain, underlay troubleshooting |
| [09-lab-artifact-mirror.md](09-lab-artifact-mirror.md) | Why large downloads bypass the fabric, and how the mirror on blog-demo-vm works |
| [10-server-network-rebuild.md](10-server-network-rebuild.md) | September 12 server renumber, storage recovery and verified telemetry |

The current server network is `10.100.0.0/24` on VLAN 100, gateway
`10.100.0.1`. Management remains `192.168.3.0/24`. The former server prefix
`192.168.100.0/24` appears in historical evidence and rollback artifacts;
it is also the external home network, where the Proxmox endpoint remains
`192.168.100.20`. Do not replay historical artifacts as current configuration.
