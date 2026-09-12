The approved standard jumbo rollout is complete on the live lab. Final checks
on 2026-09-11 reached all 28 network devices, verified all ten hosts, and found
all nine K3s nodes and all 65 pods Ready. The three Argo CD Applications were
Synced and Healthy. The additional persistence-source publication remains
pending approval, as described below.

| Layer | Verified MTU |
| --- | ---: |
| Proxmox, EVE and CML data transport | 9500 |
| Cisco data interfaces, all 55 modeled ports | 9216 |
| Arista routed fabric and CE handoffs | 9214 |
| Server bonds, bond members and service VLAN gateways | 9000 |
| Flannel, existing CNI bridges and 56 pod network namespaces | 8950 |

Management and the external NAT uplink retain their existing settings. These
results establish jumbo service inside the lab. They do not establish jumbo
capacity through an external physical switch or the Internet.

The required packet tests passed without loss: nine CE handoffs and six directed
site pairs at 9050 outer IP bytes, all six directed host site pairs at 9000 bytes
for both IPv4 and IPv6, and all six directed pod site pairs at 8950 bytes.
These are 33 required DF probe cases. A 9214-byte cross-site boundary probe
received the expected fragmentation-needed response advertising MTU 9208.
That leaves room for the 9050-byte fabric VXLAN packet carrying a 9000-byte
host packet. Both directions of the canary's direct CE handoff exchange
supported a 9214-byte ping request/reply.

The final routing checks found all 14 IS-IS adjacencies up, counted as 28 directed
neighbors. All 42 switch underlay peers, 60 EVPN peers and three service-VRF
peers were established. One final sample showed 19 queued messages toward CE2
on DCB-Spine02; the follow-up sample drained to zero without a session reset.
The final saved evidence has no queued BGP rows. Running and startup MTUs were
verified on every Arista switch, and fresh backups showed zero MTU drift from
intent. Successful compliance-job execution is not a claim that unrelated
features have no preexisting compliance differences.

The host deployment used the Git-sourced Ansible network role, one host at a
time. The full dry-run showed only three MTU changes per host. Flannel computed
8950 after each local K3s service restart, but retained 1350 on existing
flannel.1 devices. Those existing interfaces were reconciled to the computed
MTU. Existing pod interfaces and their host veth peers were updated in place,
with host-network pods excluded. This preserved storage workloads during
rebuilding. A single engine-image DaemonSet pod was recreated through the
Eviction API with disruption-budget enforcement; its replacement became Ready
and received MTU 8950 automatically.

All nine K3s services were active at the final check. DNS queries succeeded
from all nine nodes. All 54 unauthenticated API transport probes returned the
expected HTTP 401 without connection failures; the authenticated API readyz
check returned `ok`. Argo CD reported root-app, longhorn and
victoria-metrics-k8s-stack as Synced and Healthy.

One Longhorn volume, pvc-994a6887-25e7-4498-a3fc-96aeec99c8dd, remains degraded.
It was detached and degraded before maintenance, is now attached, and its
engine audit showed rebuilding in progress. The other volume was healthy at
the final check after a transient degraded state during the rollout. No volume
or replica was forcibly deleted.

TCP integrity passed with 1 MiB transferred in each direction between each pair
of sites. Host transfer times were 15.105, 42.524 and 48.462 seconds, so this
rollout does not establish a throughput improvement. The EOS control-plane TCP
test also passed but showed retransmissions. Its first diagnostic port was
blocked by the existing control-plane ACL; the successful test used already
permitted port 50099. CE1, SP1 and BORDER1 each reported a configured throughput
level of 20000 kb/s. CE1's later utilization sample was about 4 Mb/s and 7%
processing load, so that sample alone does not prove the cause of the slow
transfers. Performance remains a separate unresolved issue.

The initial validated source commit 2ed1024 was published and synced into
Nautobot. The model migration, intent regeneration, backups and MTU-only plans
were completed before device pushes. Fail Job on Task Failure was enabled.
The canary deployment was 626c151a-7282-4b1a-b86e-dd790a94e371. The multi-device
spine job a3aeef0c-71a6-4af6-8fc7-adbc910f2fb7 failed because the installed
dispatcher starts whole-inventory saves from each device task. Fresh backups
showed DCB-Spine01 already matched intent and only two interfaces remained on
DCC-Spine02. Its single-device recovery job
 eb1e1f14-0f46-4d5e-85f3-3c51917a62ad succeeded. Every remaining leaf used a
single-device job and passed. The failed job remains recorded as a failure;
see dispatcher-observation.md and the saved error evidence. Use single-device
jobs until that dispatcher behavior is corrected.

The final network backup job 6b0a18b4-222e-4960-a27b-928651571bea and compliance
job 502b4273-3367-4c78-8ebf-5062d267f941 succeeded without task errors. Source
checks passed make ci and make ci-full before deployment. Attached logs include
the initial source checks and the persistence-helper checks.

Controller persistence was tested through graceful shutdown/start of EVE VM118
and CML VM5001, followed by lab startup and dynamic link creation. All 45 scoped
data vNICs advertise 9500. The scoped reconciler reported no remaining changes
across 156 managed EVE links and 39 CML links. CML internal router links use UDP
over loopback. Host netplan files and saved network-device configurations were
verified; host VM reboot was not performed. Local K3s services were restarted
and replacement-pod MTU behavior was tested.

Protected rollback copies remain under /root/lab-jumbo-20260911 on Proxmox and
on each host. Host netplan originals are named 60-bond0.yaml.before. Private
router running/startup copies remain under /tmp/jumbo-maintenance-private in
the Nautobot container. Raw configurations and credentials are excluded from
this evidence directory. summary.json provides the measured totals, with the
individual checks in the adjacent files.

The installed transport persistence helper is saved in local commit 30eed0c
on branch lab-standard-jumbo. Automatic approval review rejected publishing
that additional commit because the earlier publication approval named
2ed1024. Publication approval was requested separately and remains pending.
The live helper is installed and verified; 30eed0c has not been pushed.
