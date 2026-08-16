# 04 — Datacenter Design

## Architecture per DC

Each site has two spines and three leaves. The leaves terminate the shared
SERVER segment as VLAN 100, VNI 10100, in VRF `SERVERS`. Every leaf uses the
same IPv4 and IPv6 anycast gateway with MAC `00:1c:73:00:00:99`.

The CEs and MPLS L3VPN provide routed underlay reachability between spine and
VTEP loopbacks. The spines exchange EVPN routes between sites. DC-C stays in
the control plane at all times, while workload placement determines its DR
role.

```text
Leaf VTEP <-> local Spine <-> CE <-> PE/MPLS <-> CE <-> remote Spine <-> Leaf VTEP
                    eBGP IPv4 underlay     eBGP EVPN over Loopback0
```

Storage remains site-local on VLANs 101, 201, and 301. Its DCI behavior can be
changed later without changing the shared SERVER identity.

## K3s Cluster Model

**3 independent clusters** (one per DC) — most realistic for multi-tenant SP:

| DC | Cluster | Server node | Worker nodes | Total |
|----|---------|-------------|--------------|-------|
| DC1 | cluster-dc1 | k3s-m1 | k3s-w1, k3s-w2 | 3 |
| DC2 | cluster-dc2 | k3s-m2 | k3s-w3, k3s-w4 | 3 |
| DC3 | cluster-dc3 | k3s-m3 | k3s-w5 | 2 |

Cross-cluster connectivity relies entirely on the MPLS L3VPN fabric — pods in
DC1 reach services in DC2 by routing through CE1 → SPE1 → core → SPE2 → CE2.

## K3s Installation

### Server node (one per DC)

```bash
# On k3s-m1 (DC1)
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server \
  --cluster-init \
  --node-ip=192.168.100.10 \
  --flannel-iface=ens3 \
  --tls-san=192.168.100.10 \
  --disable=traefik \
  --write-kubeconfig-mode=644" sh -

# Get the token for workers
cat /var/lib/rancher/k3s/server/node-token
```

### Worker nodes

```bash
# On k3s-w1 (DC1)
curl -sfL https://get.k3s.io | K3S_URL=https://192.168.100.10:6443 \
  K3S_TOKEN=<token-from-server> \
  INSTALL_K3S_EXEC="agent --node-ip=192.168.100.11 --flannel-iface=ens3" sh -
```

### K3s node addresses

The SERVER subnet is stretched, so node addresses must be unique across all
three sites:

- DC-A: `192.168.100.10` through `192.168.100.12`
- DC-B: `192.168.100.20` through `192.168.100.22`
- DC-C: `192.168.100.30` and `192.168.100.31`

All nodes use `192.168.100.1` and `fd10:a:100::1` as their anycast gateways.

## K3s Networking

- **CNI:** Flannel (default, VXLAN mode) for intra-cluster pod networking
- **Service CIDR:** Default `10.43.0.0/16` per cluster (each cluster independent)
- **Pod CIDR:** Default `10.42.0.0/16` per cluster
- **Cross-DC traffic:** Goes through node IPs (192.168.x.x) — routed by the CE

For cross-cluster service discovery, use explicit DNS or a service mesh
(Skupper/Submariner) if you want to demonstrate that layer.

## Persistent Storage

Install Longhorn on each cluster for distributed block storage:

```bash
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/master/deploy/longhorn.yaml
```

Or use `local-path-provisioner` (default in K3s) for simplicity.

## Node Specs (Proxmox VMs)

| VM | vCPU | RAM | Disk | OS |
|----|------|-----|------|----|
| k3s-m* (server) | 4 | 8 GB | 50 GB | Ubuntu 22.04 |
| k3s-w* (worker) | 4 | 8 GB | 50 GB | Ubuntu 22.04 |

## Cloud-Init Template

```yaml
#cloud-config
hostname: k3s-m1
manage_etc_hosts: true
packages:
  - curl
  - open-iscsi
  - nfs-common
  - jq
network:
  version: 2
  ethernets:
    ens18:
      dhcp4: true          # Management NIC (vmbr0) — for SSH access
    ens19:
      addresses:
        - 192.168.100.10/24
        - fd10:a:100::10/64
      routes:
        - to: 0.0.0.0/0
          via: 192.168.100.1
        - to: ::/0
          via: fd10:a:100::1
runcmd:
  - echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
  - sysctl -p
```

## Default Routes on K3s Nodes

Each K3s node uses the leaf anycast gateway. The address is identical at every
site because VLAN 100 is one stretched segment:

| DC | Gateway (IPv4) | Gateway (IPv6) |
|----|----------------|----------------|
| DC-A | `192.168.100.1` | `fd10:a:100::1` |
| DC-B | `192.168.100.1` | `fd10:a:100::1` |
| DC-C | `192.168.100.1` | `fd10:a:100::1` |

EVPN advertises endpoint reachability between VTEPs. The MPLS path carries the
routed underlay traffic between those VTEPs.
