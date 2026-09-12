# Loopback0 restoration and K3s checks, 2026-09-10

The fix is deployed. All 13 routers have verified running/startup data MTU 9216.
K3s recovered from 3/9 to 9/9 Ready nodes. Worker fabric API probes improved
from 0/18 to 18/18 completed connections, and cluster DNS passed on all nine
nodes. This is recovery of availability, not full stabilization: fabric HTTPS
latency remains high, BORDER1 has no IS-IS neighbors, and four workloads remain
not Ready. See the final results and limitations below.

The user approved deploying the prepared fix and checking whether K3s improves.
Commit 57906da was rebased over generated backup and intended commits to
d7c4de3. Git range-diff confirmed the source patch was unchanged. Publication
completed. Nautobot sync 4226537f-f207-4e90-ba8f-efc407c6524b and active Git
loader job 4acc141f-f7f5-4e42-b79b-79be88505d75 succeeded. Live feature order
is routing_global 045, loopback_prerequisite 052, isis 055, interfaces 060.

The source passed 65 template/structure checks and 149 Batfish/config checks.
Fresh intent 41e7fb5a-d115-488d-82c4-704d17b6409e, backup
5f93560c-a1dd-4fe0-8f48-e91ed18dbc20, compliance
e23af0c7-5048-43a6-ba5d-4a5b4f169ed4 and plans
085c5563-7781-4892-bdde-68328601941d all completed successfully.
Plans were reviewed for Loopback0 before router IS-IS. SPE1 plan
696f1c36-3ad7-4906-8bd1-2ab30fea7af5 has 93 commands;
SPE2 plan 14d16bb0-a200-4864-aa16-a18fb93665d8 has 134 commands.

## Before deployment

At approximately 04:23-04:25 UTC, three control-plane nodes were Ready and
six workers were NotReady. The authenticated Kubernetes API readyz checks,
including etcd readiness, all passed. All nine node management endpoints were
reconciled against live Nautobot IP assignments; SSH hostnames matched.
All nine K3s services were active with NRestarts=0 in systemd. This does not
prove the fabric network was healthy.

The six workers completed 0 of 18 unauthenticated HTTPS probes to master-2's
fabric API address, 192.168.100.11:6443. Their management-path probes to
192.168.3.64:6443 completed 18 of 18. HTTP 401 counts as transport/TLS/HTTP
completion only, not an authenticated readiness result. Each probe had a
5-second timeout. Three probes per path per node are a short sample.

The control-plane 30-minute journal windows showed no lease losses, renewal
failures or process exits. Slow etcd apply counts were 4, 267 and 256 for
masters 1, 2 and 3. These improvements predate this deployment and cannot be
attributed to it. Worker deadline errors remained frequent.

The pod baseline was 65 Running and 21 Pending, with 74 nonterminal pods not
Ready. Longhorn reported VictoriaMetrics attached/degraded and Grafana
attached/healthy. No volume, replica or workload changes were made.

Read-only checks on the three Spine01 switches found spine-to-CE Ethernet10
IP MTU 1500 and spine-to-leaf IP MTU 8950. DCA-Leaf01 had routed uplinks at
8950. Router MTU 9216 therefore does not establish a uniform fabric MTU.

## Deployment checkpoint (superseded by final verification)

SPE1 canary job df37a225-7316-420b-94c5-ac323b222681 was running with
fail_job_on_task_failure enabled. SPE2 awaited canary verification at that point. Final results follow below.


## SPE1 verification and intermediate recovery

SPE1 deployment df37a225-7316-420b-94c5-ac323b222681 completed SUCCESS
and saved. Transcript scanning found no standard IOS or exact %ISIS: rejection.
Running and startup data MTUs, enabled states and IPv6 IS-IS activation matched
intent. Both expected IS-IS neighbors, SP2 and SP4, were UP. Both links passed
3/3 DF probes at 1500, 9000 and 9216 bytes.

After SPE1 restored DC-A's PE connection, all three DC-C workers became Ready,
bringing K3s to six Ready nodes. Their fabric HTTPS probes completed 9/9 at
approximately 0.97-1.79 seconds, versus approximately 3 ms over management.
This establishes recovered reachability, not acceptable latency. A later
workload sample showed 29 non-ready pods, down from 74, with no unscheduled
pods. SPE2 deployment 37cf573d-b70c-4e02-83a1-69a6eac97e72 is active.

BORDER1 received a bounded SP-ISIS protocol shutdown/no shutdown recovery.
A before/after router-section comparison was identical, but neighbors remained
absent and CLNS still reported internal if state DOWN. No further recovery or
router reboot was performed. This fault remains separate from the PE restore.


## Final verification

Both SPE1 and SPE2 jobs completed SUCCESS with save confirmation and no detected
IOS command rejections. All 13 routers passed authenticated running/startup
checks for data MTU 9216, modeled enabled state and IPv6 IS-IS activation.
Management and NAT Outside interfaces remain outside the approved MTU policy.
Twelve of 14 core IS-IS links are up, or 24 of 28 directed neighbor entries.
Only BORDER1-SP1 and BORDER1-SP2 are missing. Every core link, including both
BORDER1 links, passed three DF probes each at 1500, 9000 and 9216 bytes in the
final run: 42/42 test groups, 126/126 replies. This final success does not erase
packet losses recorded in earlier runs or prove long-duration transport stability.

Final backup 91a2cdf9-7b83-47d8-aeac-f7d701d6e64e and compliance
c71ff092-0f74-4d1d-98a4-f1d97db6e683 both completed successfully. Job success
does not mean full Golden Config compliance. Previously documented passive
Loopback0/explicit IS-IS activation and normalized interface/ACL differences
remain outside the validated MTU/port-state assertions.

All nine K3s nodes reached Ready by 04:39:45 UTC and remained Ready throughout
the remaining short observation. The final authenticated API readyz check
passed, including etcd readiness. K3s systemd start timestamps and NRestarts
were unchanged; no K3s node service was restarted by this work.

All six workers completed 18/18 fabric HTTPS probes, compared with 0/18 before
the PE restores. Final fabric times ranged from 556 to 1582 ms, median 1129 ms;
management-path median was 2.91 ms. HTTP 401 proves completed unauthenticated
transport/TLS/HTTP, not application authorization. Separate UDP queries to the
live CoreDNS service 10.43.0.10 resolved kubernetes.default.svc.cluster.local
from all nine nodes. These are short samples, not sustained throughput tests.

Non-ready workloads fell from 74 to four, and Pending pods from 21 to two.
The final non-ready workloads were argocd-repo-server, kube-state-metrics,
Grafana and VictoriaMetrics. The latter two had Pending replacement pods and
FailedAttachVolume events. Longhorn reported the VictoriaMetrics volume still
attached/degraded on DCB worker-3 and the Grafana volume detaching from DCC
worker-4. No storage replica, volume, pod or application was manually deleted,
detached, restarted or patched. Automatic controller reconciliation continued.

The after-deployment 30-minute journal samples overlap the outage and recovery.
They still contain deadline errors and slow etcd apply warnings; they cannot be
interpreted as a clean post-change stability window. No lease-loss or process-exit
events were found in the sampled windows. The old GRO/MTU failure hypothesis
was not retested with matched packet captures in this run. The sampled EOS MTUs
remain 1500 toward CEs and 8950 toward leaves. Router-only MTU changes did not
resolve that mismatch or the observed second-scale fabric HTTPS latency.
