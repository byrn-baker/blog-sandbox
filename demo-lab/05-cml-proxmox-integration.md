# 05 — CML & EVE-NG on Proxmox

> **Superseded in part.** The bridging model below (`vmbr100`/`vmbr200`/`vmbr300`,
> one bridge per DC) was never built. The lab actually runs a single VLAN-aware
> `vmbr0` with one VLAN per point-to-point link, and the K3s/DNS hosts are
> Proxmox VMs rather than EVE-NG nodes. See
> [08-hypervisor-interconnect.md](08-hypervisor-interconnect.md) for the verified
> as-built mapping. The concept and resource-sizing sections here still hold.

## Concept

Two network emulators run as VMs on the same Proxmox host, each handling the
platform it's best suited for:

- **CML** — SP core (Cisco IOS-XE): P routers, PE routers, Route Reflectors,
  BORDER1, and CE routers (13 nodes total)
- **EVE-NG** — Arista datacenter fabric (vEOS): spines, leaves, plus the Linux
  VMs for K3s clusters, servers, and storage nodes

They interconnect via shared Proxmox Linux bridges. The CE routers live in CML
but their Gi3/Gi4 downlinks map to Proxmox bridges that EVE-NG's Arista spines
also connect to — giving L2 adjacency between CEs and spines without either
hypervisor knowing about the other.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           PROXMOX HOST                                    │
│                                                                          │
│  ┌─────────────────────────────────────┐  ┌───────────────────────────┐  │
│  │            CML VM                    │  │        EVE-NG VM          │  │
│  │                                     │  │                           │  │
│  │  SP Core (Cisco IOS-XE):            │  │  DC Fabric (Arista vEOS): │  │
│  │    RR1, RR2                         │  │    DCA-Spine01/02         │  │
│  │    SP1, SP2, SP3, SP4               │  │    DCA-Leaf01/02/03       │  │
│  │    SPE1, SPE2, SPE3                 │  │    DCB-Spine01/02         │  │
│  │    BORDER1                          │  │    DCB-Leaf01/02/03       │  │
│  │    CE1, CE2, CE3                    │  │    DCC-Spine01/02         │  │
│  │                                     │  │    DCC-Leaf01/02/03       │  │
│  │  CE1 Gi3/Gi4 → ext-dc1             │  │                           │  │
│  │  CE2 Gi3/Gi4 → ext-dc2             │  │  Linux VMs:               │  │
│  │  CE3 Gi3/Gi4 → ext-dc3             │  │    K3s nodes, servers,    │  │
│  │                                     │  │    storage per DC         │  │
│  └──────────────┬────────┬────────┬────┘  └─────┬────────┬────────┬──┘  │
│                 │        │        │              │        │        │     │
│  Proxmox:    vmbr100  vmbr200  vmbr300        vmbr100  vmbr200  vmbr300 │
│                 │        │        │              │        │        │     │
│                 └────────┼────────┼──────────────┘        │        │     │
│                          └────────┼───────────────────────┘        │     │
│                                   └────────────────────────────────┘     │
│                                                                          │
│  Each vmbr bridge carries one DC's L2 domain:                            │
│    vmbr100 = DC-A (CE1 ↔ DCA-Spine01/02 ↔ Leaves ↔ K3s/Servers)        │
│    vmbr200 = DC-B (CE2 ↔ DCB-Spine01/02 ↔ Leaves ↔ K3s/Servers)        │
│    vmbr300 = DC-C (CE3 ↔ DCC-Spine01/02 ↔ Leaves ↔ K3s/Servers)        │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Create Proxmox Bridges

Add to `/etc/network/interfaces` on the Proxmox host:

```bash
# DC-A LAN segment (Customer A — 192.168.100.0/24)
auto vmbr100
iface vmbr100 inet manual
    bridge-ports none
    bridge-stp off
    bridge-fd 0
    description "DC-A - Customer A LAN"

# DC-B LAN segment (Customer B — 192.168.200.0/24)
auto vmbr200
iface vmbr200 inet manual
    bridge-ports none
    bridge-stp off
    bridge-fd 0
    description "DC-B - Customer B LAN"

# DC-C LAN segment (Customer C)
auto vmbr300
iface vmbr300 inet manual
    bridge-ports none
    bridge-stp off
    bridge-fd 0
    description "DC-C - Customer C LAN"
```

Apply:
```bash
ifreload -a
```

---

## Step 2: CML VM — NIC Mapping

The CML VM needs 3 additional network interfaces (beyond its management NIC)
to bridge the CE downlinks out to the shared Proxmox bridges:

| CML VM NIC | Proxmox Bridge | CML External Connector | Connected to |
|------------|----------------|------------------------|--------------|
| net0 (ens3) | vmbr0 | — | CML management UI |
| net1 (ens4) | vmbr100 | ext-dc1 | CE1 Gi3, CE1 Gi4 |
| net2 (ens5) | vmbr200 | ext-dc2 | CE2 Gi3, CE2 Gi4 |
| net3 (ens6) | vmbr300 | ext-dc3 | CE3 Gi3, CE3 Gi4 |

In Proxmox CLI:
```bash
qm set <CML_VMID> --net1 virtio,bridge=vmbr100
qm set <CML_VMID> --net2 virtio,bridge=vmbr200
qm set <CML_VMID> --net3 virtio,bridge=vmbr300
```

### CML External Connector Config

Create 3 External Connector nodes in CML configured for "Bridge" mode:

| CML Node | Maps to |
|----------|---------|
| ext-dc1 | ens4 → vmbr100 |
| ext-dc2 | ens5 → vmbr200 |
| ext-dc3 | ens6 → vmbr300 |

CML wiring (each CE has two downlinks to its DC fabric):
```
CE1 Gi3 ──┐
CE1 Gi4 ──┼── unmanaged-switch-dc1 ──── ext-dc1
           │
CE2 Gi3 ──┐
CE2 Gi4 ──┼── unmanaged-switch-dc2 ──── ext-dc2
           │
CE3 Gi3 ──┐
CE3 Gi4 ──┼── unmanaged-switch-dc3 ──── ext-dc3
```

---

## Step 3: EVE-NG VM — NIC Mapping

The EVE-NG VM also gets the same 3 DC bridges so the Arista spines can reach
the CEs:

| EVE-NG VM NIC | Proxmox Bridge | EVE-NG Cloud | Connected to |
|---------------|----------------|--------------|--------------|
| net0 (eth0) | vmbr0 | — | EVE-NG management UI |
| net1 (eth1) | vmbr100 | Cloud-DC-A | DCA-Spine01 Eth10, DCA-Spine02 Eth10 |
| net2 (eth2) | vmbr200 | Cloud-DC-B | DCB-Spine01 Eth10, DCB-Spine02 Eth10 |
| net3 (eth3) | vmbr300 | Cloud-DC-C | DCC-Spine01 Eth10, DCC-Spine02 Eth10 |

In Proxmox CLI:
```bash
qm set <EVENG_VMID> --net1 virtio,bridge=vmbr100
qm set <EVENG_VMID> --net2 virtio,bridge=vmbr200
qm set <EVENG_VMID> --net3 virtio,bridge=vmbr300
```

The Arista spine Ethernet10 interfaces connect to EVE-NG "Cloud" objects mapped
to the host interfaces. This gives them L2 adjacency with the CML CEs on the
same bridge.

The Linux VMs (K3s nodes, servers, storage) also run inside EVE-NG, connected
to the leaf switches via their access ports.

---

## Step 4: Linux VMs in EVE-NG

Each DC has a set of Linux VMs connected to the leaf switches:

| DC | VMs | Connected via | Bridge |
|----|-----|---------------|--------|
| DC-A | DCA-k3s-m1, DCA-k3s-m2, DCA-k3s-m3, DCA-DNS | DCA-Leaf01/02 | vmbr100 |
| DC-B | DCB-k3s-w1, DCB-k3s-w2, DCB-k3s-w3 | DCB-Leaf01/02 | vmbr200 |
| DC-C | DCC-k3s-w4, DCC-k3s-w5 | DCC-Leaf01/02 | vmbr300 |

These VMs are managed entirely within EVE-NG. Their application traffic routes
through the leaf-spine fabric → CE → MPLS core for cross-DC connectivity.

---

## Step 5: Verification

Once everything is wired:

```bash
# From a DC-A K3s node, ping CE1 (gateway)
ping 192.168.100.1

# From DC-A, ping a DC-B node — traffic traverses:
# K3s → Leaf → Spine → CE1 → SPE1 → MPLS Core → SPE2 → CE2 → Spine → Leaf → K3s
ping 192.168.200.10

# Traceroute shows the path
traceroute 192.168.200.10
```

From CML (SP core perspective):
```bash
# On SPE1, verify PE-CE peering
show ip bgp vpnv4 vrf CUST-A summary

# On SP1, verify MPLS forwarding
show mpls forwarding-table
```

From EVE-NG (Arista fabric perspective):
```bash
# On DCA-Spine01, verify eBGP to CE1
show ip bgp summary

# On DCA-Leaf01, verify VXLAN
show vxlan vtep
```

---

## Resource Summary

| Component | Count | vCPU | RAM | Disk | Notes |
|-----------|-------|------|-----|------|-------|
| CML VM | 1 | 8–16 | 32–64 GB | 100 GB | 13 Cisco IOS-XE nodes |
| EVE-NG VM | 1 | 16–24 | 64–96 GB | 200 GB | 15 Arista + Linux VMs |
| **Total Proxmox** | — | **~32–40 vCPU** | **~96–160 GB** | **~300 GB** | |

Minimum viable: CML (8 vCPU/32 GB) + EVE-NG (12 vCPU/48 GB) = 20 vCPU / 80 GB.
Scale up EVE-NG RAM if running many Linux VMs simultaneously.
