# Persistent vEOS GRO rollout

Approved rollout source: commit d3fdafe in blog-sandbox main. Publication and Nautobot sync received separate explicit approval after automatic review blocked the first publication attempt.

Scope: nine lab vEOS leaves, ten modeled Ethernet data NICs per leaf. All 90 Linux vmnicet interfaces were present and initially had GRO enabled. Management interfaces are outside this scope.

Each NIC has an EOS on-boot event handler with a 60-second delay. The handler runs `sudo -n /sbin/ethtool -K vmnicetN gro off`. EOS executes it after configuration as well as at boot. Runtime readback, handler execution, and saved startup configuration must all be checked. A saved on-boot handler is not evidence of a completed reboot test.

Validation: 82 template/structure tests and 149 Batfish/config tests passed. Intent, backups and compliance were regenerated. Nine manual Config Plans were compared exactly with the GRO handler blocks in fresh intent. Deployment uses Fail Job on Task Failure and stops between waves for verification.

Rollback requires setting the modeled GRO state to on, regenerating intent and plans, deploying the handlers, and verifying GRO on. Removing a handler alone does not restore the current kernel setting. Do not rerun temporary canary restore scripts after this rollout.

The rollout completed on all nine leaves. Runtime readback confirmed GRO off on all 90 data NICs, all 90 handlers are in startup configuration, and platform compliance passes on all nine leaves. The on-boot handlers executed after configuration; a cold-boot test was not performed.

DCA-Leaf01 canary: Config Plan job ecb9e5ef-69f5-424a-9c07-70808645fc4d succeeded with no per-device errors. All ten NICs read GRO off, all ten handlers were saved in startup configuration, and both EVPN peers remained established. Early readbacks occurred during the merge and handler delay; they were not the final result.

The first four-leaf wave succeeded. The final wave reported a genuine DCC-Leaf02 failure: Netmiko did not detect the final end echo, and its startup file had only nine handlers despite all ten NICs having GRO off. Fresh backup/compliance preceded recovery plan 1fa47d17-f34f-499a-8ed6-c9f43e55c9c6, containing only the intended vmnicet10 handler. Recovery job a3c68c29-4398-482f-832c-f45552a08db8 succeeded and the final startup readback passed. Final backup and compliance jobs also succeeded.

Network validation reached all 28 devices, with 28 directed IS-IS adjacencies up and no non-established peers in collected BGP summaries. The captured small-segment replay completed with matching hashes and 0/1 retransmissions. All observed leaf TCP checksums were valid. Nine bidirectional host-pair tests covered all nine K3s hosts and all site pairs: all completed, with 41 total endpoint retransmissions. A separate 180-second DC-A/DC-B test at 1 Mbit/s each direction transferred 22,504,220 bytes each way with matching hashes and 2/8 retransmissions. The planned three-pair 4 Mbit/s soak was not run because Longhorn was already consuming much of the configured 20 Mbit/s CE throughput.

The cluster snapshots from 21:19:00 to 21:56:26 UTC showed all nine nodes and 65 pods Ready, with no pod replacements. The first 23-minute comparison had no container restart increases, but the final comparison found increases in four Longhorn CSI sidecars: attacher, provisioner, resizer and snapshotter. See restart-deltas.json. Argo CD root-app, longhorn, and victoria-metrics-k8s-stack were Healthy/Synced. Grafana storage remained healthy. VictoriaMetrics storage remained degraded: a rebuild reached 97%, then failed with replica read/write timeout and connection resets; Longhorn removed/replaced replicas automatically. Another attempt reset too. No manual replica deletion, salvage, or storage settings change was performed.

Do not equate ready pods with complete storage recovery. CE2/CE3 traffic near 17–18 Mbit/s leaves little headroom, but sampled QFP/BQS counters showed no licensed oversubscription or tail drops. That does not establish the throughput limit as the cause of the remaining resets. Sampled hosts had available memory, low load, and no matching kernel OOM events. Further correlation of Longhorn's failing flows with packet captures and process logs remains necessary.
