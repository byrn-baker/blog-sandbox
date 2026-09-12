# Lab baseline, 2026-09-09

The lab is not ready for fleet telemetry rollout. Read-only checks found recurring
control-plane failures, degraded VictoriaMetrics storage, and no SNMP configuration
on the 26 devices whose running configuration could be read. Local mitigations are
prepared; none were deployed. This report records a point-in-time baseline, not a
completed stability test.

## Scope and method

Checks began around 00:11 UTC on 2026-09-09. Master journal summaries cover the
preceding six hours; other results are snapshots collected during this audit.
Nautobot returned 38 devices: 28 network devices and 10 servers. Existing API,
SSH and Kubernetes credentials were used without recording resolved secrets.
SNMP probes originated from management host 192.168.3.21. Device commands only
read running SNMP configuration and its access list.

Repository baselines before local changes:

- blog-sandbox: c5afce087f1845299fef25eb358aab2a8bf39b3c
- blog-sandbox-argo-cd: 1ccef4485dd9a030c48518863a541e30accce1e7

## Findings and gates

| Area | Measured result | Gate |
| --- | --- | --- |
| SNMP | All 28 polls timed out. Running configuration on 26 devices contains no snmp-server lines or ACL-SNMP-RO. CE1 and RR1 SSH read-back timed out twice. | Generate fresh intent, backups, compliance and plans; approve and verify one canary per platform before expanding. |
| Control plane | All three masters have recent leadership-related exits. Cloud-controller-manager losses appear on each; m3 also lost the internal k3s-etcd lease. | Correct the missing runtime cloud-controller settings, investigate fabric behavior and demonstrate stability. |
| Fabric/API | From dcb-k3s-w2, management API endpoints responded in roughly 4-5 ms; fabric endpoints took 189/237 ms and m2 timed out connecting. | Repeat across workers and trace the fabric path. These unauthenticated HTTP 401 responses measure connectivity, not readiness. |
| Observability | kube-state-metrics previous logs show Kubernetes Service TLS handshake timeout; operator logs show refused API requests and lost lease. | Verify successful API access and stable component restart counts after remediation. |
| Storage | VictoriaMetrics 20Gi volume is degraded; only two replicas were observed, one without a healthy timestamp. Grafana storage was healthy. | Restore VM replica health and confirm rebuild completes before adding stores. |
| Worker capacity | dcc-k3s-w6 is cordoned; root filesystem is 92% used with about 457 MiB free. Its separate Longhorn disk has space. | Plan root disk expansion/cleanup and verify node health before uncordoning. |
| Argo ordering | Root, Longhorn and VM Applications reported Synced/Healthy, but argocd-cm lacks child-Application health customization. | Apply and test prerequisite health gating; application status alone is insufficient evidence of runtime stability. |

Sources: [SNMP probes](snmp.json), [fleet read-back](fleet-readback.json),
[SSH retry](retry-readback.json), [master 1](DCA-k3s-m1.json),
[master 2](DCA-k3s-m2.json), [master 3](DCA-k3s-m3.json),
[worker API paths](worker-api-paths.json), [kube-state-metrics](kube-state-metrics.json),
[operator](victoria-metrics-operator.json), [storage](storage.json),
[replicas](longhorn-replicas.json), [Applications](applications.json),
[Argo health configuration](argocd-health.json).

All 25 nodes in the CML SP Demo Lab report BOOTED, including CE1 and RR1.
This does not establish guest SSH health or correct wiring. The configured
Proxmox API returned HTTP 503, so physical host resource pressure remains
unverified. See [CML node state](cml-nodes.json) and [Proxmox result](proxmox.json).

Etcd metrics collected since each process's latest start show mean WAL fsync
under 1 ms and peer round-trip means ranging roughly 53-207 ms. Histogram p99
bucket upper bounds for peer latency reach 819 ms. These samples prioritize
fabric investigation; they do not establish a root cause or rule out earlier
host stalls. They cover different windows on each master and are not the same
six-hour window as the journals. See [selected metrics](etcd-metrics.json).

The kubeconfig's fabric endpoint initially refused connections. Authenticated
read-only Kubernetes checks used an explicit management endpoint override and
the original TLS server name. The kubeconfig was not changed.

## Prepared local changes

The k3s_config runtime drop-in now includes cloud-controller-manager leader
lease duration 30s and renew deadline 20s. Existing serial control-plane handling
restarts one server at a time and checks readiness. Existing node lifecycle
settings remain. This mitigation does not change the internal k3s-etcd lease
and cannot repair fabric latency. Existing command-line controller-manager
lists may override corresponding YAML lists; this patch does not reconcile
that separate pre-existing behavior.

Argo bootstrap values now include child-Application health evaluation. A child
must report Healthy and Synced before the script reports Healthy. This supports
initial root sync ordering; it does not serialize later independent child auto-syncs.
The matching deployment notes are in blog-sandbox-argo-cd/apps/README.md.

Validation completed: Ansible syntax checks, strict Jinja rendering with the lab
variables, and a render of the pinned argo-cd 10.8.0 chart confirming the exact
health script in argocd-cm. Both repositories passed git diff --check. The normal
Nautobot inventory run also emits an existing platform.napalm_driver mapping
warning for server records; isolated syntax validation passed. Lua execution
and a live stalled-child test remain open. No live restart, Helm upgrade,
device deployment, commit or push was performed.

Configuration references: [K3s configuration precedence](https://docs.k3s.io/installation/configuration)
and [Argo Application health](https://argo-cd.readthedocs.io/en/stable/operator-manual/health/#argocd-app).

## Next lab sequence

1. Repeat fabric/API measurements from multiple workers and masters, inspect
   routing/interface counters, and recover Proxmox read access to check host
   pressure. Establish why the fabric path differs from management.
2. Review the runtime mitigation, then perform a controlled serial rollout in
   an approved maintenance run. Stop on failed readiness or new leadership
   failures. Confirm effective cloud settings, API reachability and restart counts.
3. Require a documented 24-hour stability window with no new leadership exits,
   no API-related component restarts and healthy VM replicas. This is a proposed
   acceptance window, not a result already achieved.
4. Apply Argo health customization through bootstrap management and prove a
   stalled prerequisite blocks initial dependent deployment.
5. Generate fresh SNMP compliance and Config Plans for BORDER1 and DCA-Leaf01.
   Obtain approval for that device run, then verify CLI and actual polls before
   proceeding to Collector, VictoriaLogs and VIP canaries.

T001 and T004 remain open. Constitution Principle VI interpretation, Collector
binary validation, dual-subnet VIP reachability, retention capacity and accounting
reconciliation still require evidence. This audit does not close those gates.

Subsequent work: [controlled stabilization rollout](../2026-09-09-stabilization/README.md). The baseline above remains the pre-change record.
