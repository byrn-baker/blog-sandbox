# 08 — Hypervisor Interconnect (CML ↔ EVE-NG ↔ VMs)

As-built reference for the layer that sits *underneath* the lab. Every link that
crosses an emulator boundary is a VLAN on one Proxmox bridge. If a lab adjacency
is down, this document tells you whether the problem is in the lab or in the
plumbing below it.

Verified against the live system on 2026-09-04 using the Proxmox API, the CML
API, the EVE-NG API, and the EVE-NG host's bridge table.

> This supersedes the bridging design in
> [05-cml-proxmox-integration.md](05-cml-proxmox-integration.md), which describes
> three separate bridges (`vmbr100`/`vmbr200`/`vmbr300`) that were never built.

---

## The one rule

There is exactly one bridge on the Proxmox host: **`vmbr0`**, VLAN-aware,
`bridge_vids 2-4094`, MTU 9000, uplinked on `eno1`. Every emulator-to-emulator
and emulator-to-VM link is a `tag=<vlan>` vNIC on that bridge.

One VLAN carries exactly one point-to-point link. There are no shared L2
segments between more than two endpoints, except VLAN 3 (out-of-band
management) and VLAN 17 (emulator management).

```
                      Proxmox host r640-pve
   ┌──────────────────────── vmbr0 (VLAN-aware, MTU 9000) ────────────────────┐
   │                                                                          │
   │   VLAN 401-406            VLAN 425-427          VLAN 407-424             │
   │   CE ↔ Spine              CE ↔ Leaf03           Leaf ↔ VM bond legs      │
   │        │                       │                      │                  │
   │   ┌────┴────┐             ┌────┴────┐            ┌────┴─────┐            │
   │   │ CML     │─────────────│ EVE-NG  │            │ K3s /    │            │
   │   │ vmid    │  9 VLANs    │ vmid    │  18 VLANs  │ DNS VMs  │            │
   │   │ 5001    │             │ 118     │            │ 3001-09  │            │
   │   └─────────┘             └─────────┘            └──────────┘            │
   │   IOS-XE SP core          Arista vEOS fabric     Ubuntu, bond0           │
   └──────────────────────────────────────────────────────────────────────────┘
```

The K3s and DNS VMs are **Proxmox VMs, not EVE-NG nodes**. Each one has two
tagged vNICs that land on two different leaf switches inside EVE-NG, bonded
into a single `bond0` in the guest.

---

## Endpoint identities

| Component | Proxmox VMID | Mgmt IP | Notes |
|-----------|--------------|---------|-------|
| CML | 5001 | 192.168.17.10 | 20 cores ×2 sockets, 250 GB RAM |
| EVE-NG | 118 | 192.168.17.2 | 10 cores ×4 sockets, 256 GB RAM, nested virt |
| blog-demo-vm (automation host) | 106 | 192.168.3.21 | Nautobot, Ansible, pyATS |
| K3s + DNS VMs | 3001–3009 | 192.168.3.63–.71 | see table below |

CML lab: `SP Demo Lab`, id `c11c5f8e-daf2-468c-89d9-dfd626f3b2ff`.
EVE-NG lab: `/Blog-SandBox.unl`, uuid `5913edeb-e573-47c6-b8f0-db65dfbb8e32`.

> The checked-in `Blog-SandBox.unl` export predates the K3s node rename (the
> old one-master-per-DC names). It is an archived topology snapshot, not a
> source of truth, so it is left as-is. The authoritative server names live in
> Nautobot and the Design Builder `servers` list; the tables in this doc use
> the current names.

---

## Interface naming, three times over

The same physical link has a different name at every layer. This is where most
of the confusion comes from, so here is the translation.

**Proxmox** calls it `netN` in the VM config. Order matters: `netN` maps to a
guest interface by PCI slot order, not by name.

**Inside CML** the first six vNICs come up as `ens18`–`ens23`, then the rest as
`enp2s1`–`enp2s12`. CML wraps each one in a Linux bridge named after the VLAN
(`vlan401`), which you select in the UI as an External Connector labelled
`VLAN 401`.

**Inside EVE-NG** vNIC `ethN` is enslaved to bridge `pnetN`, one-to-one, no
offset. `pnetN` shows up in the UI as `Cloud N`. The lab renames each cloud to
describe its far end (`CE1-Gi3`, `DCA-k3s-m1-Leaf01`), which is why the network
names read backwards from what you might expect.

**Inside the guest VMs** `net1` and `net2` come up as `ens19` and `ens20` and
get bonded.

---

## VLAN allocation

### Management VLANs

| VLAN | Subnet | CML | EVE-NG | VMs |
|------|--------|-----|--------|-----|
| 3 | 192.168.3.0/24 (gw .1) | `net14` → `enp2s9` → `vlan3` → connector `lab-mgmt` | `net2` → `eth2` → `pnet2` → cloud `MGMT` → all 15 × `Mgmt1` | `net0` → `eth0` on every VM |
| 17 | 192.168.17.0/24 | `net0` → `ens18` → `bridge0` (System Bridge) | `net0` → `eth0` → `pnet0` | — |

VLAN 3 is the out-of-band management network. Nautobot, Ansible, and pyATS all
reach devices here. VLAN 17 is the emulator management network and carries only
the CML and EVE-NG web UIs and APIs.

### CE ↔ Spine links (CML → EVE-NG)

Each CE has two spine uplinks. These are the only links where an IOS-XE routed
interface talks directly to an Arista routed interface.

| VLAN | CML node/interface | CML connector | CML guest if | EVE-NG cloud | EVE-NG guest if | Arista node/interface |
|------|--------------------|---------------|--------------|--------------|-----------------|-----------------------|
| 401 | CE1 Gi3 | `DCA-Spine01-E10` (`vlan401`) | `ens19` (net1) | `CE1-Gi3` (`pnet3`) | `eth3` (net3) | DCA-Spine01 Et10 |
| 402 | CE1 Gi4 | `DCA-Spine02-E10` (`vlan402`) | `ens20` (net2) | `CE1-Gi4` (`pnet4`) | `eth4` (net4) | DCA-Spine02 Et10 |
| 403 | CE2 Gi3 | `DCB-Spine01-E10` (`vlan403`) | `ens21` (net3) | `CE2-Gi3` (`pnet5`) | `eth5` (net5) | DCB-Spine01 Et10 |
| 404 | CE2 Gi4 | `DCB-Spine02-E10` (`vlan404`) | `ens22` (net4) | `CE2-Gi4` (`pnet6`) | `eth6` (net6) | DCB-Spine02 Et10 |
| 405 | CE3 Gi3 | `DCC-Spine01-E10` (`vlan405`) | `ens23` (net5) | `CE3-Gi3` (`pnet7`) | `eth7` (net7) | DCC-Spine01 Et10 |
| 406 | CE3 Gi4 | `DCC-Spine02-E10` (`vlan406`) | `enp2s1` (net6) | `CE3-Gi4` (`pnet8`) | `eth8` (net8) | DCC-Spine02 Et10 |

### CE ↔ Leaf03 border handoff (CML → EVE-NG)

Leaf03 in each DC is the services/border leaf. It gets its own CE link rather
than riding the spines.

| VLAN | CML node/interface | CML connector | CML guest if | EVE-NG cloud | EVE-NG guest if | Arista node/interface |
|------|--------------------|---------------|--------------|--------------|-----------------|-----------------------|
| 425 | CE1 Gi5 | `DCA-Leaf03-E10` (`vlan425`) | `enp2s10` (net15) | `CE1-GI5` (`pnet27`) | `eth27` (net27) | DCA-Leaf03 Et10 |
| 426 | CE2 Gi5 | `DCB-Leaf03-E10` (`vlan426`) | `enp2s11` (net16) | `CE2-GI5` (`pnet28`) | `eth28` (net28) | DCB-Leaf03 Et10 |
| 427 | CE3 Gi5 | `DCC-Leaf03-E10` (`vlan427`) | `enp2s12` (net17) | `CE3-GI5` (`pnet29`) | `eth29` (net29) | DCC-Leaf03 Et10 |

### Leaf ↔ VM bond legs (EVE-NG → Proxmox VMs)

Every VM gets two VLANs: one to Leaf01, one to Leaf02. The leaves present these
as EVPN ESI-multihomed single-member port-channels; the guest runs
`balance-xor` (static, no LACP), which is why the leaf side shows
`Protocol: Static`.

| VLAN | Arista node/interface | Po | EVE-NG cloud | EVE-NG guest if | VM (vmid) | VM guest if |
|------|-----------------------|-----|--------------|-----------------|-----------|-------------|
| 407 | DCA-Leaf01 Et4 | Po4 | `DCA-k3s-m1-Leaf01` (`pnet9`) | `eth9` (net9) | DCA-k3s-m1 (3001) | `ens19` (net1) |
| 408 | DCA-Leaf02 Et4 | Po4 | `DCA-k3s-m1-Leaf02` (`pnet10`) | `eth10` (net10) | DCA-k3s-m1 (3001) | `ens20` (net2) |
| 409 | DCA-Leaf01 Et5 | Po5 | `DCA-k3s-m2-Leaf01` (`pnet11`) | `eth11` (net11) | DCA-k3s-m2 (3002) | `ens19` (net1) |
| 410 | DCA-Leaf02 Et5 | Po5 | `DCA-k3s-m2-Leaf02` (`pnet12`) | `eth12` (net12) | DCA-k3s-m2 (3002) | `ens20` (net2) |
| 411 | DCA-Leaf01 Et6 | Po6 | `DCA-k3s-m3-Leaf01` (`pnet13`) | `eth13` (net13) | DCA-k3s-m3 (3003) | `ens19` (net1) |
| 412 | DCA-Leaf02 Et6 | Po6 | `DCA-k3s-m3-Leaf02` (`pnet14`) | `eth14` (net14) | DCA-k3s-m3 (3003) | `ens20` (net2) |
| 413 | DCB-Leaf01 Et4 | Po4 | `DCB-k3s-w1-Leaf01` (`pnet15`) | `eth15` (net15) | DCB-k3s-w1 (3004) | `ens19` (net1) |
| 414 | DCB-Leaf02 Et4 | Po4 | `DCB-k3s-w1-Leaf02` (`pnet16`) | `eth16` (net16) | DCB-k3s-w1 (3004) | `ens20` (net2) |
| 415 | DCB-Leaf01 Et5 | Po5 | `DCB-k3s-w2-Leaf01` (`pnet17`) | `eth17` (net17) | DCB-k3s-w2 (3005) | `ens19` (net1) |
| 416 | DCB-Leaf02 Et5 | Po5 | `DCB-k3s-w2-Leaf02` (`pnet18`) | `eth18` (net18) | DCB-k3s-w2 (3005) | `ens20` (net2) |
| 417 | DCB-Leaf01 Et6 | Po6 | `DCB-k3s-w3-Leaf01` (`pnet19`) | `eth19` (net19) | DCB-k3s-w3 (3006) | `ens19` (net1) |
| 418 | DCB-Leaf02 Et6 | Po6 | `DCB-k3s-w3-Leaf02` (`pnet20`) | `eth20` (net20) | DCB-k3s-w3 (3006) | `ens20` (net2) |
| 419 | DCC-Leaf01 Et4 | Po4 | `DCC-k3s-w4-Leaf01` (`pnet21`) | `eth21` (net21) | DCC-k3s-w4 (3007) | `ens19` (net1) |
| 420 | DCC-Leaf02 Et4 | Po4 | `DCC-k3s-w4-Leaf02` (`pnet22`) | `eth22` (net22) | DCC-k3s-w4 (3007) | `ens20` (net2) |
| 421 | DCC-Leaf01 Et5 | Po5 | `DCC-k3s-w5-Leaf01` (`pnet23`) | `eth23` (net23) | DCC-k3s-w5 (3008) | `ens19` (net1) |
| 422 | DCC-Leaf02 Et5 | Po5 | `DCC-k3s-w5-Leaf02` (`pnet24`) | `eth24` (net24) | DCC-k3s-w5 (3008) | `ens20` (net2) |
| 423 | DCA-Leaf01 Et7 | Po7 | `DNS-Leaf01` (`pnet25`) | `eth25` (net25) | DCA-DNS (3009) | `ens19` (net1) |
| 424 | DCA-Leaf02 Et7 | Po7 | `DNS-Leaf02` (`pnet26`) | `eth26` (net26) | DCA-DNS (3009) | `ens20` (net2) |

DC-C has no Et6 pair because it only runs two nodes. The DNS pair (423/424) is
DC-A only.

### VM addressing on the bonds

All VM data interfaces sit on the stretched `192.168.100.0/24` segment,
regardless of which DC the VM belongs to. Default gateway is the anycast
`192.168.100.1` on the fabric.

| VM | vmid | Mgmt (VLAN 3) | bond0 |
|----|------|---------------|-------|
| DCA-k3s-m1 | 3001 | 192.168.3.63 | 192.168.100.10/24 |
| DCA-k3s-m2 | 3002 | 192.168.3.64 | 192.168.100.11/24 |
| DCA-k3s-m3 | 3003 | 192.168.3.65 | 192.168.100.12/24 |
| DCB-k3s-w1 | 3004 | 192.168.3.66 | 192.168.100.20/24 |
| DCB-k3s-w2 | 3005 | 192.168.3.67 | 192.168.100.21/24 |
| DCB-k3s-w3 | 3006 | 192.168.3.68 | 192.168.100.22/24 |
| DCC-k3s-w4 | 3007 | 192.168.3.69 | 192.168.100.30/24 |
| DCC-k3s-w5 | 3008 | 192.168.3.70 | 192.168.100.31/24 |
| DCA-DNS | 3009 | 192.168.3.71 | 192.168.100.53/24 |

---

## MTU chain

Verified values, outside in:

| Layer | MTU |
|-------|-----|
| Proxmox `vmbr0`, `eno1` | 9000 |
| CML data connectors (`vlan401`–`vlan427`) | 9000 |
| CML `bridge0` (mgmt, VLAN 17) | 1500 |
| EVE-NG `eth0`–`eth29`, `pnet0`–`pnet29` | 9000 |
| Arista fabric ports (spine Et1–3, leaf Et1–3) | 9214 |
| Arista host-facing ports (leaf Et4–Et7) | 9214 |
| Arista Et10 toward CE (IP MTU) | 1500 |
| IOS-XE CE Gi3/Gi4/Gi5 | 1500 |
| VM `bond0` and slaves | 1450 |

The underlay is jumbo end to end, so the 1500-byte CE↔spine links and the
1450-byte VM bonds are deliberate choices inside the lab, not artifacts of the
hypervisor. VXLAN encap happens on the leaves (`Vxlan1`, source `Loopback1`,
UDP 4789) across 9214-byte fabric links, so the 1450 on the hosts leaves
headroom rather than being strictly required.

If you see fragmentation or PMTUD symptoms, check the lab interface MTU first.
Nothing in Proxmox, CML, or EVE-NG is going to clamp a frame below 9000.

---

## Troubleshooting: is it the plumbing or the lab?

The layers fail in distinguishable ways. Work down this list.

**1. Is the far-end vNIC even present?**

```bash
# On the Proxmox host, confirm the VLAN tag exists on both VMs
qm config 5001 | grep -E 'net[0-9]+:'
qm config 118  | grep -E 'net[0-9]+:'
```

A link that exists in the CML topology and the EVE-NG topology but has a
mismatched `tag=` on one side will show both interfaces up with zero traffic.
Interface up + no ARP is the signature of a VLAN mismatch. Interface down is
almost never a VLAN problem.

**2. Is the emulator actually bridging the vNIC?**

CML only forwards a VLAN if an External Connector exists for it *and* a node is
linked to that connector. A defined-but-unlinked connector looks healthy in the
connector list and silently drops everything.

```bash
# CML: connector definitions and their host interface
curl -sk https://192.168.17.10/api/v0/system/external_connectors \
  -H "Authorization: Bearer $TOKEN" | jq -r '.[] | "\(.device_name) \(.operational.interface)"'
```

EVE-NG is simpler: `pnetN` always has `ethN` enslaved, plus one `vunl0_<node>_<iface>`
tap per attached node interface. If the tap is missing, the node interface is not
attached to the cloud.

```bash
ssh root@192.168.17.2 'ls /sys/class/net/pnet9/brif'
# expect: eth9  vunl0_3_4     (node 3 = DCA-Leaf01, iface 4 = Ethernet4)
```

The `vunl0_<node_id>_<iface_index>` naming is the fastest way to confirm the
EVE-NG side. Node IDs come from the lab (`DCA-Spine01` is node 1, `DCA-Leaf01`
is node 3), and iface index 0 is `Management1`, so index *N* is `EthernetN`.

**3. Does L2 work across the boundary?**

ARP on the Arista side is the cheapest end-to-end proof. A CML-sourced MAC has
OUI `52:54:00`; an Arista-sourced MAC has OUI `50:00:00`.

```
DCA-Spine01# show ip arp vrf default
10.1.1.0   0:00:00  5254.0012.d256  Ethernet10   ← CE1 Gi3, learned across VLAN 401
```

Seeing a `5254.00xx` MAC on Et10 means Proxmox, CML's bridge, and EVE-NG's
`pnet` are all forwarding. Anything broken after that point is routing or
protocol config inside the lab.

**4. Bond legs specifically.**

A VM bond with one dead leg still passes traffic, so it hides failures. Check
both slaves, not just `bond0`:

```bash
ssh ubuntu@192.168.3.63 'cat /proc/net/bonding/bond0'
```

Then confirm the matching leaf sees both members:

```
DCA-Leaf01# show port-channel dense
   Po4(U)   Static   Et4(P)
```

`Et4(P)` = bundled. `Et4(I)` or a missing member points at the VLAN leg for that
specific leaf, which you can look up in the table above.

---

## Known issues in the current build

**CML management is isolated from VLAN 3.** All 13 IOS-XE devices attach `Gi1`
to the in-lab `mgmt-switch-0` unmanaged switch, but the `lab-mgmt` External
Connector (`vlan3`, host `enp2s9`) has **no link to that switch**
(`is_connected: false`, state `STOPPED`). The CML VM has the VLAN 3 vNIC and the
`vlan3` bridge exists, so this is purely a missing link inside the CML topology.

Effect: `192.168.3.50`–`.62` are unreachable. Nautobot golden-config backups and
pyATS both fail for the SP core while the Arista fabric (`192.168.3.30`–`.44`,
reached through EVE-NG's `pnet2`) works fine. The newest `sp-core` backup in
`golden-config/backup-configs/sp-core/` is dated 30 Aug; DC-A backups are
current as of 4 Sep, which brackets when this broke.

Fix: link `lab-mgmt` to a free port on `mgmt-switch-0`. Separately, `RR1 Gi1`
reports `down/down` while `CE1 Gi1` reports `up/up` on the same switch, so that
one interface may need a link bounce as well.

**Stale CML vNICs on VLAN 407–413.** The CML VM carries `net7`–`net13` tagged
407–413. Those VLANs now belong to the EVE-NG-leaf ↔ VM bond legs. Six of them
(408–413, guest `enp2s3`–`enp2s8`) have no CML bridge and are inert. VLAN 407
does have a live `vlan407` bridge on `enp2s2` with no node attached, so it
absorbs broadcast traffic from the DCA-k3s-m1 ↔ DCA-Leaf01 segment and drops it.

Harmless today. The risk is that attaching any CML node to the `VLAN 407`
connector would drop a third device into the middle of a bond leg. Recommend
removing `net7`–`net13` from the CML VM and deleting the `vlan407` connector.

**Unused capacity.** EVE-NG `net1` (`eth1`/`pnet1`, VLAN 220) is not referenced
by the `Blog-SandBox` lab. It is shared with the `containerlabs` VM (vmid 104).
