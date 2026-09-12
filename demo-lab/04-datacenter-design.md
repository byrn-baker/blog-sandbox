# 04: Datacenter Design

## Fabric and server network

Each site has two spines and three leaves. VLAN 100 is stretched across the
sites as VNI 10100, with gateway SVIs in VRF `SERVERS`. Every leaf uses
`10.100.0.1`, `fd10:a:100::1` and anycast MAC `00:1c:73:00:00:99`.
The CEs and MPLS L3VPN provide underlay reachability between sites; EVPN
supplies overlay endpoint reachability. DC-C participates in the fabric
control plane even though it hosts no Kubernetes control-plane members.

Each Ubuntu host uses `bond0` over `ens19` and `ens20`, attached to its site's
Leaf01 and Leaf02. The bond uses balance-xor with layer3+4 hashing and MTU
9000. Management uses `eth0` on `192.168.3.0/24`.

## One K3s cluster across three sites

| Site | Nodes | Data addresses | Role |
|---|---|---|---|
| DC-A | DCA-k3s-m1, m2, m3 | `10.100.0.10`–`10.100.0.12` | Three servers with embedded etcd |
| DC-B | DCB-k3s-w1, w2, w3 | `10.100.0.20`–`10.100.0.22` | Agents |
| DC-C | DCC-k3s-w4, w5, w6 | `10.100.0.30`–`10.100.0.32` | Agents |
| DC-A | DCA-DNS | `10.100.0.53` | Standalone BIND, outside K3s |

All three etcd members remain in DC-A following the earlier cross-site
latency and lease failures. The QEMU and GRO corrections improved measured
packet delivery, but residual latency under storage load remains. Short TCP
tests do not establish that distributing etcd across sites is now safe. This
placement does not survive loss of DC-A.

Agents register against m1 at `10.100.0.10:6443`. There is no separate API
VIP. The leaf anycast gateway routes traffic; it is not a Kubernetes API
load balancer.

## Managed installation and networking

Use the Nautobot-backed Ansible workflow in
[06a-ansible-automation.md](06a-ansible-automation.md), with the source in
[ansible](../ansible/). The September 12 rebuild uses K3s `v1.30.5+k3s1`,
`--flannel-iface=bond0`, and disables the bundled Traefik and ServiceLB.
The managed configuration replaces the older manual installation examples.

Flannel uses VXLAN with MTU 8950 over the 9000-byte host data network.
The Pod CIDR is `10.42.0.0/16`; the Service CIDR is `10.43.0.0/16`.
Hosts also have addresses in `fd10:a:100::/64`; that does not mean the
Kubernetes Pod and Service networks are dual-stack.

Ansible manages `/etc/netplan/60-bond0.yaml`. All nine K3s hosts also have
`/etc/netplan/75-management-routes.yaml`, managed by `management_routes`,
with the workstation route `192.168.100.32/32 via 192.168.3.1 dev eth0`.
The default route stays on `bond0` through `10.100.0.1`. The route was
read back on all nine hosts; browser access from that workstation was not
verified in the recorded check.

## Storage and applications

Longhorn is installed through the Argo CD root Application, with its chart
and values in `blog-sandbox-argo-cd`. Do not use an unpinned upstream manifest
as an alternative installation path. Replicas run on workers across DC-B
and DC-C over the Kubernetes network. The modeled site-local storage VLANs
101, 201 and 301 are not the current Longhorn replication path.

The September 12 recovery placed all ten lab OS disks on Proxmox `vm_disk`,
after the smaller `local-lvm` thin pool filled. K3s root disks are 60 GiB;
BIND's is 43.5 GiB. Worker Longhorn data disks are separate 50 GiB disks.
See [the rebuild record](10-server-network-rebuild.md) for the identity
checks, recovery sequence and measured limitations.

The verified application set is Longhorn, VictoriaMetrics/Grafana, the
separate SNMP history store and the OTel SNMP collector. MetalLB, ingress,
VictoriaLogs and the broader flow/syslog pipeline remain future work.
