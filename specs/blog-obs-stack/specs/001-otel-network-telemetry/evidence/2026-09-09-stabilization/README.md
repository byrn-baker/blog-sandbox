# Stabilization run, 2026-09-09

The user authorized proceeding after review of the baseline and prepared fixes.
The cloud-controller runtime mitigation was applied through the repository's
Ansible k3s_config role, starting with master 1 and then rolling serially through
masters 2 and 3. All three runs passed with zero failed or unreachable hosts.

The control-plane play now uses any_errors_fatal so a failed host stops the rollout.
Rollback copies were saved on each master at
/etc/rancher/k3s/90-node-lifecycle.pre-cloud-20260909.bak, outside the YAML drop-in
directory. Restoring that file to config.yaml.d/90-node-lifecycle.yaml and restarting
one master at a time reverses this runtime change. The source template must also
be reverted before a later Ansible run to avoid reapplying it.

Master 1 passed the Ansible readiness check after its controlled restart at
01:06 UTC. The live k3s-cloud-controller-manager Lease subsequently identified
master 1 as holder and reported leaseDurationSeconds=30. This verifies the
running setting; a file read alone would not. Master 2 also passed readiness.
No claim of a completed stability window is made.

## Fabric and storage findings

[Repeated API probes](api-paths.json) sampled three requests per endpoint from
DC-A, DC-B and DC-C. Management endpoints returned HTTP 401 in roughly 4-6 ms.
Remote fabric endpoints ranged from tens of milliseconds to 1.8 seconds, with
connection timeouts to master 2 from DC-B and DC-C. HTTP 401 here measures
connectivity and TLS/request latency, not authenticated readiness.

[Bond read-back](bonds.json) shows up links, MTU 1400 and no reported bond errors
on the three sampled hosts. [Leaf summaries](leaf-summary.json) and
[details](leaf-detail.json) show established EVPN sessions, active static server
port-channels and learned master-2 MAC routes through both DC-A VTEPs. These
snapshots do not rule out intermittent forwarding faults. Unsupported CLI queries
are retained as failed observations and are not evidence of missing state.

[Longhorn logs](longhorn-errors.txt) show API timeouts and failed snapshot-update
verification while a VictoriaMetrics replica rebuild is already in progress.
The volume has schedulable disk space; capacity alone does not explain the stalled
rebuild. No replica, snapshot or volume was deleted or detached.

The configured Proxmox API still returns HTTP 503. A direct management endpoint
has been requested. Host resource pressure and the worker root-disk expansion
remain unresolved. Argo health customization and device SNMP deployment have not
been applied during this run.

## Completed rollout verification

At 01:15:49 UTC, all nine nodes reported Ready, with w6 still cordoned. The
cloud-controller lease remained on master 1, renewed successfully, and retained
30 seconds with no additional transition since its acquisition at 01:07:45.
VictoriaMetrics remained attached/degraded; Grafana reported attached/healthy.
See [final state](final-state.json), [master 1](DCA-k3s-m1.json),
[master 2](DCA-k3s-m2.json), and [master 3](DCA-k3s-m3.json).
The six-hour journal counts in those files include failures from before this
rollout and must not be interpreted as post-change failures.

The observation window is minutes, not the proposed 24-hour acceptance window.
The wider lab stabilization task remains incomplete. No network device config,
Argo bootstrap, storage replica or worker disk was changed. Source changes remain
uncommitted locally, and the pre-existing inventory edit was preserved.

## PVE access and worker disk repair, 01:18-01:22 UTC

The user supplied SSH root@192.168.100.20. This reaches r640-pve from the
automation host; do not confuse it with the overlapping fabric address used by
a K3s worker from inside the lab. The HTTPS endpoint failure did not prevent SSH
administration. PVE has 96 logical CPUs, about 490 GiB available RAM, no swap use,
and roughly 63-66% CPU idle in short vmstat samples. The vm_disk storage pool was
26% allocated. These samples do not establish historical or per-core behavior.
Inside EVE, a five-second vmstat sample showed roughly 64-67% idle CPU with no
reported swap, I/O wait or steal during the sampled intervals.

VM 3010 was matched to DCC-k3s-w6 using MAC BC:24:11:9E:2C:1E. Its scsi0 root
disk was 6.5 GiB; the other K3s VMs listed 60 GiB root disks. The separate scsi1
Longhorn data disk was 50 GiB. The following repair completed online:

1. Saved the guest partition table to /root/sda-before-grow-20260909.sfdisk.
2. Ran qm disk resize 3010 scsi0 60G on PVE.
3. Verified growpart -N /dev/sda 1 preserved the partition start and boot partitions.
4. Ran growpart /dev/sda 1 and resize2fs /dev/sda1 in the guest.
5. Verified root now reports 58G total, 53G available and 9% used, compared with
   92% used before repair. The Longhorn filesystem remained 49G, 1% used.
6. Confirmed Ready=True and MemoryPressure/DiskPressure/PIDPressure=False,
   then uncordoned dcc-k3s-w6.

No reboot or data-disk change was required. The partition-table copy is diagnostic
recovery material, not a rollback procedure for shrinking a grown filesystem.
The earlier statement that no worker disk was changed describes the first rollout
only; this follow-up resolves that capacity blocker. Fabric reliability and
VictoriaMetrics replica health still require verification and repair.
