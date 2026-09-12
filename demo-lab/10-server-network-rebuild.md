# Rebuild the disposable cluster on a distinct server subnet

The server network moved from 192.168.100.0/24 to 10.100.0.0/24 on
2026-09-12. The former subnet overlapped the home network. For example,
192.168.100.20 identified both the Proxmox host outside the lab and a K3s
worker inside it. Management remains on 192.168.3.0/24. Proxmox addressing
is unchanged.

The user authorized discarding the cluster and its volume data for this
rebuild. Existing Grafana and SNMP credentials were retained in restricted
local files. No credential files belong in Git.

## Source and execution order

1. Change VLAN 100 in the topology context, server address template, BORDER1
   NAT context, corresponding test fixtures, Ansible variables, and current
   addressing documentation. Leave historical evidence unchanged.
2. Run `make ci` and `make ci-full`. The migration passed 88 template/structure
   checks and 149 configuration/Batfish checks.
3. Sync the repository into Nautobot. Run the Git-sourced **Lab Server
   Addressing** job with `dry_run=true`, then apply it. Nautobot IP host values
   are immutable, so this job replaces address records and transfers their
   interface assignments in a transaction. It checks all ten server bonds
   and all nine leaf SVI assignments. The old prefix remains empty.
4. Regenerate intent, fresh backups, compliance, and Config Plans. Deploy one
   IOS-XE and one EOS canary, verify, then deploy the remaining leaves in waves.
   Keep Fail Job on Task Failure enabled. The device changes remove the old
   Vlan100 virtual IPv4 gateway, add 10.100.0.1/24, and replace the old subnet
   in BORDER1's NAT-INET ACL. MTUs and IPv6 addressing remain unchanged.
5. Reset only the modeled K3s members using the separate destructive playbook:

   ```sh
   cd ansible
   .ansible/bin/ansible-playbook pb.reset_k3s.yml -e rebuild_disposable_cluster=true
   ```

   The play verifies host identity and K3s membership. It uninstalls K3s and
   removes contents of the verified Longhorn secondary-disk mounts. BIND is
   outside the reset group. Two workers required a reboot when old Longhorn
   mounts blocked uninstallation; rerunning the reset then completed.
6. Apply `pb.site.yml --tags network`, then `--tags dns`. Verify addresses,
   gateways, DNS, internet access, and jumbo pings before restoring workloads.
   The BIND VM had an obsolete `60-vlan100-bond.yaml` which Netplan merged
   with the managed file. The host role now retires that file and replaces
   the overlapping DNS resolver inherited from the VM template.
7. Run `pb.site.yml --tags k3s`. The pinned offline installation uses bond0
   for Flannel, keeps the three servers in DC-A, and disables Traefik and
   ServiceLB. Allow the runtime-tuning and registry-mirror restarts to finish
   before bootstrapping applications. The fetched kubeconfig uses the
   management address, with an explicit API certificate SAN.
8. Bootstrap the pinned Argo CD chart with the repository's bootstrap values.
   Restore externally managed credentials, then apply `bootstrap/root-app.yaml`
   from blog-sandbox-argo-cd. Its child Applications restore Longhorn and the
   monitoring stack. Check actual storage replicas, dashboard access, and fresh
   SNMP samples before declaring recovery complete.

These commands use the existing Nautobot environment credentials and dynamic
inventory. Do not replace the inventory with a static host list.

## Verification boundaries

All ten hosts passed new-address, gateway, DNS, and 9000-byte IPv4 ping checks
after removal of BIND's duplicate Netplan file. All nine leaf gateways were
independently checked in running and startup configuration with MTU 9000.
BORDER1's fresh backup confirms the new NAT source and removal of the old one;
an actual host reached the internet through the new subnet.

Two deployment waves reported an `end` prompt timeout, on DCB-Leaf02 and
DCB-Leaf03. Their running configurations, saved configurations, and subsequent
backups were checked instead of treating the failed jobs as successful. The
failures remain in job history. Broader compliance also reports older interface
descriptions, the DNS Ethernet Segment Identifier, and IOS formatting/default
commands; a successful compliance job does not mean every feature is compliant. Network evidence is in
../specs/blog-obs-stack/specs/001-otel-network-telemetry/evidence/2026-09-12-server-renumber/.

This renumbering does not deploy MetalLB, ingress, split DNS, or home-firewall
rules. It removes the address collision those future changes otherwise need
to work around. A short recovery check is not proof of site-failure tolerance
or a long-running stability test.

## Hypervisor storage interruption during restoration

Application restoration exposed a second capacity limit. Proxmox's `local-lvm`
thin pool reached 100% of its approximately 130 GiB backing capacity. VM 3001
and BIND VM 3009 reported `qmpstatus: io-error` and failed writes on `scsi0`,
although the summary VM status still said `running`. Their network interfaces
stopped responding because QEMU had paused the guests.

Eight K3s OS disks and BIND's OS disk were on this small pool. The affected
guests still had free space inside their filesystems. Longhorn's separate
50 GiB disks were already on `vm_disk`, which had approximately 10.6 TiB free.
The ninth K3s node, VM 3010, already had its OS disk on `vm_disk` too.

Recovery moved the affected OS disks to `vm_disk` and retains the existing
VMs, network interfaces, disk contents, and data disks. VM identity is checked
against Nautobot's management addresses and Proxmox's `ipconfig0` and `net0`,
since several hypervisor display names predate the current K3s roles. The
sequence for each affected VM is:

```sh
qm stop <verified-vmid> --timeout 5
qm disk move <verified-vmid> scsi0 vm_disk --delete 1
qm config <verified-vmid>
qm start <verified-vmid>
```

The move deletes the original volume only after its copy succeeds. BIND was
moved first to release space; the remaining eight moves ran two at a time.
Do not run this against unrelated VMs or delete the shared template volumes.
For future lab VM provisioning, place OS disks on `vm_disk` as well as the
Longhorn data disks. Guest free-space monitoring alone cannot detect an
exhausted hypervisor thin pool.


All ten lab VMs subsequently reported `qmpstatus: running`, with their OS disks
on `vm_disk`. The original thin pool fell to 9.68% usage. The final network play
passed on all ten hosts and the registry play passed on all nine K3s nodes.

One extracted container image on DCB-k3s-w2 contained a zero-byte
`/usr/local/bin/grpc_health_probe`. The other five Longhorn instance managers
had the same intact 14,072,256-byte executable. Restarting the affected pod
reused the damaged image and did not fix its replica health checks. We drained
that worker, stopped K3s, ran `k3s-killall.sh`, cleared only
`/var/lib/rancher/k3s/agent/containerd`, and restarted the agent to extract clean
images. The separate Longhorn data disk was retained. The timing is consistent
with the full-pool interruption, but we did not trace the original failed write
to this individual file.

After the VM moves, all ten hosts again passed addressing, gateway, BIND DNS,
and 9000-byte IPv4 DF ping checks. Three cross-site pairs each transferred
1 MiB in both directions with MSS 8948, matching SHA-256 hashes and zero
retransmissions across the six streams. Each sender was limited to 125,000
bytes per second, so this verifies delivery rather than maximum throughput.

The low-rate TCP result does not describe storage traffic under load. While
Longhorn formatted volumes and rebuilt replicas, an actual cross-site replica
connection had roughly 3 MiB retransmitted out of 31 MiB sent, with a TCP RTT
estimate near 734 ms. Transfers were progressing, but this remains a performance
limitation to investigate. All 13 running CML router QEMU processes still used
the patched executable SHA-256
`605b893d815e96962cca4a8960b5a32289745721774e2db40a4c5876c2446a3e`.
The nine leaves retained GRO disabled on all 90 data NICs and saved handlers.


Grafana's default liveness probe restarted the fresh database during migrations.
The pinned Grafana subchart exposes liveness and readiness settings, but no
main-container startup probe. Commit `53a93bd` in blog-sandbox-argo-cd therefore
sets a 1,800-second initial liveness delay and a 2,100-second deployment progress
deadline, while leaving readiness active. It also uses `Recreate` for the single
Grafana instance and its RWO database. This allows initialization to finish; it
does not improve the underlying storage latency. A future chart with a startup
probe can gate liveness until initialization succeeds instead of using a fixed
delay. See the [Kubernetes probe documentation](https://kubernetes.io/docs/concepts/workloads/pods/probes/).

The initial strategy update was rejected because server-side apply retained
Kubernetes' defaulted `rollingUpdate` fields alongside `Recreate`. The follow-up
Argo repository commit `a07291e` explicitly clears those fields and selects
client-side apply for this Deployment only. A server dry run accepted that
manifest, and the live Deployment showed `Recreate` with the 2,100-second
deadline after Argo CD applied it. Other workloads retain server-side apply.


## Final recovery checks

At approximately 20:56 UTC on 2026-09-12, all nine nodes were Ready with fresh
leases, every non-completed pod was Ready, and all five Argo CD Applications
were Synced and Healthy. All three Longhorn volumes were attached and healthy;
each engine reported three replicas in `RW` mode. The Kubernetes readiness
endpoint returned `ok`.

Both VictoriaMetrics stores had fresh samples from all 28 network devices and
372 interfaces. Each device had at least five polls in the preceding five
minutes; the oldest uptime sample was under 60 seconds old. Export queues were
empty, all receiver refused-point counters were zero, and the collector reported
no failed exports. All 16 Network SNMP dashboard panel queries returned data.
Authenticated dashboard access, unauthenticated access rejection, login pages,
and database health were checked through NodePort 30300 at management addresses
192.168.3.63, 192.168.3.66, and 192.168.3.69.

Grafana is available at http://192.168.3.66:30300/d/network-snmp using the existing
login. This verifies management access from the automation host. It does not
verify home-network routing, a border port forward, MetalLB, ingress, or split
DNS. The three control-plane nodes remain in DC-A.

### SQLite contention remains a separate limitation

During concurrent provisioning and storage initialization, Grafana returned
HTTP 503 and logged `SQLITE_BUSY`; a direct health request also exceeded ten
seconds. Argo repository commit `4e8a51a` declares `database.wal: true` and gives
the readiness request five seconds. Rendering and server dry runs passed,
and the restarted container's configuration contains `wal = true`.

However, a read-only `PRAGMA journal_mode` against the mounted database still
returned `delete`. Do not describe this setting as a verified WAL fix. The
[v13.1.1 SQLite connection adapter](https://github.com/grafana/grafana/blob/v13.1.1/pkg/util/sqlite/sqlite_nocgo.go)
is a candidate for further investigation: its DSN conversion constructs a
pragma from the parameter key, including the leading underscore. No patched
Grafana binary or upstream issue was published in this rebuild. Compare that
behavior with Grafana's [documented WAL setting](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/#wal).

The final dashboard and database health checks passed after provisioning
completed. That establishes recovery at the time of the checks, not sustained
performance under load. Cross-site storage latency, load-related retransmissions,
and SQLite contention still need a dedicated performance investigation before
we claim the lab is fully stabilized or move etcd across all three datacenters.
