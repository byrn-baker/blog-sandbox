# Forwarding capacity audit

All ten sampled Cisco routers reported a configured throughput level of 20000 kb/s. During active Longhorn rebuilding, the one-minute non-priority input/output datapath rates were approximately 20.05/20.06 Mb/s on CE3, 19.54/19.55 Mb/s on SPE2, and 20.18/20.16 Mb/s on SPE3. Processing load was modest. These observations strongly support a forwarding-capacity bottleneck during recovery.

The global QFP drop counters are cumulative and do not establish which device discarded each TCP segment. The vNIC mapping command confirms virtio but does not expose detailed queue counters on these images. Neither the capacity cap nor these counters explain the separate receive stalls conclusively.

The architectural concern is the dependency of Kubernetes control communication and Longhorn replication on the simulated fabric being modified and rebooted. A stable infrastructure network, or a properly sized and supported forwarding path for all infrastructure traffic, is needed before treating jumbo reachability as evidence of a usable storage network.

Cisco CML platform limitations: https://developer.cisco.com/docs/modeling-labs/cat-8000v/
