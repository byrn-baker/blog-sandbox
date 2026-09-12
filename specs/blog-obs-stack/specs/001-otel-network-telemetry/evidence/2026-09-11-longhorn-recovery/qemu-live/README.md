# Live CML QEMU receive-stall correction

The user authorized this live rollout on 2026-09-11 after the isolated clone passed the compiled regression and router traffic tests.

The installed artifact is the exact clone-tested executable, built from Ubuntu QEMU 8.2.2 source package `1:8.2.2+ds-0ubuntu1.18` with upstream commit `f937309fbdbb48c354220a3e7110c202ae4aa7fa` backported. It is an experimental local build.

- Patched executable SHA-256: `605b893d815e96962cca4a8960b5a32289745721774e2db40a4c5876c2446a3e`
- Original vendor executable SHA-256: `8a35ccba41582fc6c38b9df85fc9e35fa1d42f414d2d7d8090ee9b2f5e7c0854`
- Live CML VM: Proxmox VM 5001, CML 2.10.0 build 13.
- Installed path: `/usr/bin/qemu-system-x86_64`.
- Preserved vendor path: `/usr/bin/qemu-system-x86_64.distrib`, managed with a local `dpkg-divert`.
- Rollback on the CML host: `python3 /opt/cml-qemu-canary/rollback.py`, followed by a CML stop/start of each affected router. An IOS reload does not replace the QEMU process.

The artifact was transferred through the Proxmox guest agent after direct HTTP routing failed. The first SPE3 restart happened before installation completed and still used the vendor binary. The first patched start failed because relocating the build changed its firmware lookup. Missing links under `/usr/share/qemu` now resolve to the packaged SeaBIOS and iPXE files; additions are recorded in `/opt/cml-qemu-canary/firmware-links.json` and removed by rollback. No existing firmware file was overwritten. A startup smoke test passed after adding the links.

Before restarting, all 13 router running/startup operational configurations matched and each save confirmed `[OK]`. Private configuration backups are intentionally excluded from this evidence directory. Post-restart comparisons exclude PKI trustpoint/certificate formatting and check the remaining operational configuration against the saved running configuration.

The local diversion protects the experimental binary from package replacement. Remove it when adopting a suitable vendor update. Current testing covers the lab's C8000V domains; other QEMU-based node types have not been validated with this build.

The rollout completed on 2026-09-11. All 13 C8000V processes match the patched hash, all configuration checks passed, and temporary launch priorities were restored. SPE3 was the live canary, followed by four waves. Wave 3 paused on an SP2 read timeout and incomplete adjacency sample; a fresh read showed all five adjacencies and advancing receive counters before rollout resumed.

The isolated test clone (VM 108) is shut down with its disks retained. The temporary artifact service on Proxmox is stopped. Live validation reached all 28 network devices with 28 directed IS-IS adjacencies up and no non-established peers in the collected BGP summaries. All six cross-site directions passed five 9000-byte DF pings each. Eight receive-ring samples over 115 seconds recorded 18 rollovers across ten NICs; 57 of 69 sampled NICs advanced. Unused interfaces were also sampled. No new IS-IS adjacency log entries appeared between the pre-test and post-test collections.

The first small-MSS TCP control failed, so the planned high-rate soak did not run. A bounded 256 KiB replay at requested MSS 1200 recorded 117/95 retransmissions and failed to complete. Its paired MSS 8960 replay negotiated 8948 and completed 256 KiB in each direction in about 2.2 seconds with zero retransmissions. Do not report all TCP problems as fixed.

Captured valid 1188-byte TCP segments entering DCA-Leaf01 became a combined 2376-byte segment with an invalid reconstructed checksum on its VXLAN egress. The receiver acknowledged those bytes only after valid retransmissions. The approved temporary GRO-off canary on DCA-Leaf01 vmnicet5 and DCB-Leaf01 vmnicet4 passed when the TCP source port was fixed to the baseline value, 38869. The 256 KiB bidirectional transfer at requested MSS 1200 completed within 2.5 seconds with matching hashes and zero retransmissions at both endpoints. Each source leaf ingress and VXLAN egress had 221 valid data segments and no invalid reconstructed TCP checksums. This validates a workaround on the tested path, without identifying the exact faulty vEOS code. Both ports were restored to GRO on and verified afterward. No persistent or fleet GRO change was made.

The first GRO-off replay used an ephemeral source port that selected Leaf02 at both sites, bypassing the changed ingress ports. It failed with 136/140 retransmissions. This was not a valid test of the two-port correction. Its paired jumbo test passed with zero retransmissions. Captures and current EVE interface mappings preserve this distinction. The fixed-port repeat verified the original Leaf01 ingress path.

The canary cluster snapshot showed all nine nodes and all 65 pods Ready. Grafana storage remained healthy; VictoriaMetrics remained degraded. No sustained fleet throughput test was performed.

All nine K3s nodes were Ready in the post-rollout snapshot. Both Longhorn volumes reattached automatically. Grafana was healthy with three running replicas; VictoriaMetrics remained degraded. No manual volume salvage or storage configuration change was made in this rollout.
