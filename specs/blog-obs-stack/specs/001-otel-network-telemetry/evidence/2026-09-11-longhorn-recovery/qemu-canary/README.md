# CML QEMU receive-stall canary

The user authorized testing the receive-path correction in an isolated CML clone on 2026-09-11. The live CML VM is 5001. The canary is Proxmox VM 108, named `cml-qemu-canary`.

All 18 cloned lab NICs have `link_down=1`. The clone has 64 GiB RAM and 12 vCPUs, with an additional outbound-only QEMU user network for dependencies. The copied CML target was stopped and licensing/telemetry units masked. No package or router restart was applied to live VM 5001.

## Build and reproduction

The build uses Ubuntu's `qemu_8.2.2+ds.orig.tar.xz` and `qemu_8.2.2+ds-0ubuntu1.18.debian.tar.xz`, with the Debian quilt series applied. The candidate backports upstream commit [f937309](https://github.com/qemu/qemu/commit/f937309fbdbb48c354220a3e7110c202ae4aa7fa). The 8.2.2 header needs the new function declaration inserted without an unrelated newer declaration used as patch context.

The test adds `rx-jumbo-wrap` to QEMU's existing virtio-net qtest suite. It advances a real emulated receive ring with short packets, advertises too few buffers for a 9229-byte frame across rollover, then replenishes all 256 buffers and explicitly kicks the queue. It checks that the original binary remains frozen, and that the patched binary consumes five buffers and delivers the complete frame with matching contents. The vectors match the observed last-consumed/cached-available pairs: (65535,1), (65534,1), and (65533,0).

The installed Ubuntu executable does not include the qtest accelerator. The original comparison binary was rebuilt from the same Ubuntu source with qtest enabled. This limitation is distinct from the real C8000V test, which boots the patched executable under KVM and libvirt inside the cloned CML system.

The final runtime build enables NUMA and seccomp to satisfy the existing CML VM definitions. Exact build options, executable hashes, and regression results are in `evidence/`. The firmware search directory points to firmware already installed in the clone. The clone's AppArmor policy allows this exact canary executable; confinement remains enabled.

## Router and traffic setup

Cloned SPE3 and SP1 run the patched binary with their existing IOS XE configurations and virtio NICs. Their core interfaces connect directly through loopback UDP sockets. Their other original lab connections remain disconnected.

Two Linux network namespaces provide test endpoints using unused core-facing interfaces within this isolated copy:

- `canary-a`, 10.0.0.1/31, through SP1 Gi2 (10.0.0.0).
- `canary-b`, 10.0.0.18/31, through SPE3 Gi3 (10.0.0.19).

The path is Linux A, SP1, SPE3, Linux B. Existing IS-IS advertises the connected networks. No IOS interface configuration changes were required. Linux endpoints use MTU 9000; router interfaces retain 9216. TAP-to-UDP relays preserve the CML-style QEMU backend. TSO/GSO/GRO are disabled on the synthetic Linux attachment interfaces.

The tests include five 9000-byte DF pings, 20-second bidirectional TCP controls at 1 Mbit/s with requested MSS 1200 and 8960, then 360 seconds of bidirectional jumbo TCP at 8 Mbit/s per direction. QMP receive-ring counters are sampled every ten seconds. IOS IS-IS details and adjacency logs are collected before and after the load test.

## Scope of approval and promotion

This is an experimental canary build, not a Cisco-supported package. Live installation has not been authorized by this clone-test approval or performed. Before promotion, retain the original package, preserve the current fault evidence and router configurations, prepare a rollback, and obtain approval for the exact live installation and node stop/start run. Replacing a binary does not change running QEMU processes; a full node stop/start is required.

A successful canary establishes that the tested receive stall is corrected under these conditions. It does not establish that all historical retransmissions, Longhorn rebuild failures, or K3s instability share this cause.

## Completed results

The original source build reproduced a frozen receive ring in all three observed index cases. The patched build delivered intact jumbo frames through three wraps in each case. Existing basic RX/TX, stop/continue RX, and NET_BUFSIZE TX tests passed. Both running C8000V processes were verified against the patched executable's SHA-256, `605b893d815e96962cca4a8960b5a32289745721774e2db40a4c5876c2446a3e`.

| TCP test | Duration | Rate in each direction | Retransmissions A to B / B to A | Result |
|---|---:|---:|---:|---|
| Small control, requested MSS 1200 | 20 s | 1.003 Mbit/s | 0 / 0 | Complete |
| Jumbo control, requested MSS 8960 | 20 s | 1.003 Mbit/s | 1 / 1 | Complete |
| Jumbo sustained test | 360 s | 8.000 Mbit/s | 15 / 17 | 360,003,840 bytes each direction |
| Jumbo with writes aligned to negotiated MSS 8948 | 30 s | 8.001 Mbit/s | 0 / 0 | 30,002,644 bytes each direction |

Five 9000-byte DF pings passed. Sampling across the controls and sustained test observed four counter wraps on all four traffic-facing NICs, with 285,388 to 286,652 receive descriptors consumed per NIC. IS-IS stayed up; the post-test logs contain only the initial adjacency-up event and the adjacency age covers the traffic test.

During the sustained test, socket counters showed retransmitted bytes in 12-byte units and matching DSACK duplicate counts. The generator wrote 8960-byte blocks against a negotiated MSS of 8948, producing short tails. The subsequent aligned-write test had no retransmissions. This supports a test-pattern explanation for those residual retransmissions, but the shorter follow-up does not establish that every historical retransmission shares that mechanism.

The cloned CML and its two routers remain available in isolation. Temporary management tunnels and the Proxmox loopback file-transfer service are removed after collection. The live CML VM and its QEMU installation remain unchanged.
