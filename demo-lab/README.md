# SP Demo Lab — Design & Build Guide

A complete service provider demo lab running on Proxmox + CML, featuring an MPLS
L3VPN core with 3 datacenter customers running K3s clusters and distributed
services. Purpose: demonstrate network configuration, monitoring, and
observability across a realistic multi-tenant SP environment.

## Documents

| File | Content |
|------|---------|
| [01-addressing.md](01-addressing.md) | IPv4/IPv6 addressing plan |
| [02-sp-core-topology.md](02-sp-core-topology.md) | SP core design (routers, MPLS, BGP) |
| [03-vrf-design.md](03-vrf-design.md) | L3VPN / VRF customer design |
| [04-datacenter-design.md](04-datacenter-design.md) | Per-DC topology, K3s clusters, services |
| [05-cml-proxmox-integration.md](05-cml-proxmox-integration.md) | CML ↔ Proxmox bridging, VM specs |
| [06-services-distribution.md](06-services-distribution.md) | K3s workloads split across DCs |
| [06a-ansible-automation.md](06a-ansible-automation.md) | Nautobot-sourced Ansible: inventory, roles, BIND, K3s |
| [07-monitoring-scenarios.md](07-monitoring-scenarios.md) | Demo failure scenarios and observables |
