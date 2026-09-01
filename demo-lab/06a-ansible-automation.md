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

There is no `hosts.yml`. Ansible uses the `networktocode.nautobot.gql_inventory`
(GraphQL) inventory plugin. The GraphQL plugin is deliberate: the REST inventory
plugin does not expose the merged config context or interface IPs as host vars
in a shape the group and compose expressions can reach, so grouping on K3s role
and reading the bond0 addresses both failed with it. The GraphQL plugin returns
exactly the queried fields under predictable names. On every run it queries
Nautobot for the Server-role devices and derives:

- Connection target: `ansible_host` is set automatically from `primary_ip4.host`
  (the eth0 management address, 192.168.3.0/24). Each server must therefore have
  its eth0 address assigned as `primary_ip4`.
- Data-plane addressing: the VLAN 100 IPv4 and IPv6 read off the `bond0`
  interface, composed into `vlan100_ipv4` / `vlan100_ipv6` host vars (split by
  the colon in the CIDR, mask stripped).
- Group membership and K3s attributes: read from each device's
  `local_config_context_data`, not from a file.

The device role filter matches the role name exactly (`Server`), not a
lowercased slug; `server` is rejected as an invalid choice.

### Groups built from the K3s config context

Cluster membership and node role are modeled as Git-synced device-local config
contexts, one file per device under `config_contexts/devices/`. Each server
device carries:

```yaml
k3s:
  member: true          # false for DCA-DNS (DNS-only, not in the cluster)
  role: "server"        # or "agent"
  cluster_init: true    # true on exactly one server (bootstraps embedded etcd)
  node_labels: "topology.kubernetes.io/zone=dc-a"
```

Two rules govern these files, both learned the hard way from a sync failure:

1. The filename must equal the device name exactly, case and hyphens included
   (`DCA-k3s-m1.yaml`). Nautobot resolves a device-local context by
   `Device.objects.get(name=<filename without extension>)`, not by anything
   inside the file. A mismatched name fails the whole sync with `record not
   found!`.
2. The file body is only the context data, no `_metadata` block. Nautobot
   stores the file verbatim as the device's `local_config_context_data`, so a
   `_metadata` key would pollute the merged context.

There is a `K3s Properties` schema in `config_context_schemas/` that documents
the intended shape, but device-local contexts loaded this way are not
schema-validated (schema binding is a global-context feature). The schema is
kept as documentation, not enforcement. To enforce it, model these as
schema-bound global contexts scoped per device instead.

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
  requirements.txt         python deps (ansible-core>=2.18, pynautobot, netutils, netaddr)
  requirements.yml         collections (networktocode.nautobot, ansible.posix, community.general)
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
# One-time control-node setup: python deps + Ansible collections
pip install -r requirements.txt
ansible-galaxy collection install -r requirements.yml

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
