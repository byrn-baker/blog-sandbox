# Blog Sandbox — SP Demo Lab

Source code and configuration for a 28-device service provider MPLS/EVPN lab
with AI-driven monitoring. Accompanies the [10-part blog series](https://byrnbaker.me).

## What's in here

```
blog-sandbox/
├── demo-lab/                     # Design documentation + Design Builder job
│   ├── 01-addressing.md          # Full IPv4/IPv6 addressing plan
│   ├── 02-sp-core-topology.md    # SP core design (ISIS, MPLS, BGP)
│   ├── 03-vrf-design.md          # L3VPN / PE-CE design
│   ├── 04-datacenter-design.md   # DC leaf-spine EVPN/VXLAN
│   ├── 05-cml-proxmox-integration.md  # CML + EVE-NG on Proxmox
│   ├── 06-services-distribution.md    # K3s cluster placement
│   ├── 07-monitoring-scenarios.md     # Failure scenarios for testing
│   ├── SERIES-OUTLINE.md         # 10-part blog series plan
│   └── sp_demo_lab/              # Nautobot Design Builder job
│       ├── __init__.py           # DesignJob (deployment mode)
│       ├── context/__init__.py   # All topology data (28 devices, dual-stack)
│       └── designs/
│           ├── 0001_foundations.yaml.j2   # Sites, roles, VRFs, prefixes
│           ├── 0002_devices.yaml.j2       # Devices + interfaces + IPs
│           ├── 0003_cabling.yaml.j2       # Cables + P2P IPs + VRF assignments
│           ├── 0004_routing.yaml.j2       # ISIS + BGP (SP + DC fabric)
│           └── 0005_primary_ips.yaml.j2   # Device primary IPv4 assignments
│
└── golden-config/                # Nautobot Golden Configuration data source
    ├── templates/
    │   ├── cisco_ios.j2          # Entry point for IOS-XE (includes ios/*.j2)
    │   ├── arista_eos.j2         # Entry point for EOS (includes eos/*.j2)
    │   ├── ios/                  # Modular IOS-XE partials
    │   │   ├── hostname.j2
    │   │   ├── vrfs.j2
    │   │   ├── interfaces.j2
    │   │   ├── isis.j2
    │   │   ├── mpls.j2
    │   │   └── bgp.j2
    │   ├── eos/                  # Modular EOS partials
    │   │   ├── hostname.j2
    │   │   ├── vrfs.j2
    │   │   ├── interfaces.j2
    │   │   ├── routing.j2
    │   │   └── bgp.j2
    │   └── graphql_query.graphql # SoT aggregation query
    ├── intended-configs/         # Auto-populated by Golden Config
    ├── backup-configs/           # Auto-populated by Golden Config
    └── README.md                 # Setup instructions
```

## The Lab

28 network devices running on Proxmox:

- **CML** — 13 Cisco IOS-XE (CAT8000v): P routers, PE routers, Route
  Reflectors, Border router, CE routers
- **EVE-NG** — 15 Arista vEOS: 3 DC leaf-spine fabrics (2 spines + 3 leaves each)

Interconnected via shared Proxmox bridges (vmbr100/200/300).

## Nautobot Apps

| App | Purpose |
|-----|---------|
| Design Builder | Declarative topology population (single job creates everything) |
| BGP Models | ASNs, routing instances, peerings, address families |
| IGP Models | ISIS instances, configurations, interface configs |
| Golden Config | Intended config generation, backup, compliance |

## Quick Start

1. Deploy Nautobot via [nautobot-docker-compose](https://github.com/nautobot/nautobot-docker-compose)
3. Run the Design Builder job. It creates devices, VLANs, VRFs, anycast SVIs,
   prefixes, cabling, and SP/DC routing.
4. The lab loads jobs from `/home/ubuntu/nautobot-docker-compose/jobs/` through
   the container bind mount. Keep that mounted copy in step with `demo-lab/`.
5. Add this repo as the Git data source for contexts and Golden Config.
6. Run `Golden Config - Bootstrap Setup`, then generate intended configs.

## Blog Series

| Part | Topic |
|------|-------|
| 1 | Nautobot as Source of Truth |
| 2 | SP Core: ISIS, MPLS, BGP (Golden Config) |
| 3 | PE-CE and Customer VRFs |
| 4 | Datacenter Fabrics: Arista Leaf-Spine |
| 5 | K3s Clusters and Applications |
| 6 | Observability Stack |
| 7 | SuzieQ State History |
| 8 | NetClaw AI NOC |
| 9 | Failure Scenarios |
| 10 | Golden Config Compliance + Remediation |

## License

Apache-2.0
