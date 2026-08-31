# 06a: Ansible Automation (Server Provisioning)

## Scope

The network devices are owned by Nautobot Golden Config: intended config from
Jinja templates, pushed by Config Plans. The Linux servers are different. They
are provisioned by Ansible, and this doc describes that automation. It lives in
the repo at `ansible/`.

The dividing line is deliberate. Golden Config renders and enforces device CLI.
Ansible configures Ubuntu hosts (netplan, packages, K3s, BIND). Both draw from
the same source of truth, Nautobot, so neither owns a second copy of the data.

## Source of truth: Nautobot, no static inventory

There is no `hosts.yml`. Ansible uses the `nautobot.nautobot` dynamic inventory
plugin. On every run it queries Nautobot for the Server-role devices and derives:

- Connection target: each host's management primary IP (eth0, 192.168.3.0/24).
- Data-plane addressing: the VLAN 100 IPv4 and IPv6 read off the `bond0`
  interface, composed into `vlan100_ipv4` / `vlan100_ipv6` host vars.
- Group membership: built from the K3s config context, not from a file.

### Groups built from the K3s config context

Cluster membership and node role are modeled as a Git-synced config context
(`config_contexts/devices/*.yaml`) validated by the `K3s Properties` schema
(`config_context_schemas/k3s_properties.yaml`). Each server device carries:

```yaml
k3s:
  member: true          # false for DCA-DNS (DNS-only, not in the cluster)
  role: "server"        # or "agent"
  cluster_init: true    # true on exactly one server (bootstraps embedded etcd)
  node_labels: "topology.kubernetes.io/zone=dc-a"
```

The inventory turns that into groups:

| Group | Rule |
|-------|------|
| `k3s_cluster` | `k3s.member` is true |
| `k3s_servers` | member and `k3s.role == server` |
| `k3s_agents` | member and `k3s.role == agent` |
| `k3s_init` | `k3s.cluster_init` is true |
| `dns_servers` | Server-role device that is not a member |

Adding a node to the cluster is a config-context change committed to Git and
synced to Nautobot, not an inventory edit.

## Repository layout

```text
ansible/
  ansible.cfg              inventory + plugin config
  requirements.yml         collections (nautobot, ansible.posix, community.general)
  inventory/nautobot.yml   dynamic inventory (the only inventory)
  group_vars/
    all.yml                lab-wide (domain, VLAN 100 gateways, bond members)
    k3s_cluster.yml        K3s version, token, API host, etcd timers
  roles/
    common/                base host prep + K3s kernel prereqs
    host_network/          netplan bond0 static LAG (dual-stack)
    k3s_server/            embedded-etcd control plane (init + join)
    k3s_agent/             worker join
    bind_dns/              authoritative BIND for sandbox.lab from Nautobot
  bootstrap.yml            first-run SSH key + sudo
  site.yml                 full provisioning run
```

## Role responsibilities

- `common`: apt packages, hostname, timezone. Kernel modules and sysctls for
  K3s apply only to `k3s_cluster` members. All Ubuntu, so the Pi-specific
  branches from the reference repo are dropped (`is_pi: false` lab-wide).
- `host_network`: renders `/etc/netplan/60-vlan100-bond.yaml` for the VLAN 100
  bond. `ens19` and `ens20` bond as a static LAG (`balance-xor`,
  `transmit-hash-policy layer3+4`, `mii-monitor-interval 100`) carrying the
  dual-stack VLAN 100 address. Static, not LACP: the nested-lab bridges do not
  forward LACP slow-protocols multicast, so the bond forms without control
  frames while EVPN handles all-active forwarding. This matches the netplan
  Part 5 established by hand, now rendered from Nautobot.
- `k3s_server`: the cluster-init node runs `--cluster-init`; the other two join
  it. etcd heartbeat/election timers are relaxed for the cross-DC path.
- `k3s_agent`: registers against the cluster API on VLAN 100 and runs workloads.
- `bind_dns`: installs BIND9 on DCA-DNS, queries Nautobot for all device names
  and primary IPs, and renders the `sandbox.lab` forward zone plus the
  192.168.3.0/24 and 192.168.100.0/24 reverse zones. Serial is the run
  timestamp so caches see each regeneration.

## Run order

```bash
export NAUTOBOT_URL=http://localhost:8080
export NAUTOBOT_TOKEN=<token>

# Fresh VMs still on password auth: seed keys + sudo
ansible-playbook bootstrap.yml --ask-pass --ask-become-pass

# Full provisioning
ansible-playbook site.yml
```

`site.yml` runs `common` + `host_network` everywhere, `bind_dns` on the DNS
host, then the K3s control plane (`serial: 1`) and agents, and finally fetches
the kubeconfig to the control machine with the API address rewritten to the
reachable VLAN 100 IP.
