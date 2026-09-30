# A file transfer visible in sFlow, September 30, 2026

Two completed runs transferred a 256 MiB temporary file from DCA-k3s-m1
(10.100.0.10) to DCC-k3s-w4 (10.100.0.30). Management SSH started the processes;
the TCP payload used bond0 and the inter-site data network. Hostnames, management
addresses and data addresses were reconciled against live Nautobot. The sender
was capped at 1 MiB/s and processes had a 720-second safety deadline.

| Run | Destination port | Source port | Received bytes | Receiver seconds | Exact forward samples |
|---|---:|---:|---:|---:|---|
| First | 47931 | 58785 | 268435456 | 258.44 | 3 from DCA-Leaf01 |
| Enriched repeat | 47933 | 51923 | 268435456 | 302.85 | 1 from DCA-Leaf02 |

Both receiver hashes matched the source:

```text
486cc817b95d853d3c357ff283b204c0144bd255e73fe2deb1389493b257e3c0
```

`transfer-1.json` and `transfer-3.json` record completed transfers. `samples-1.json`
and `samples-3.json` retain the exact forward TCP five-tuple queries, bounded
time windows and raw VictoriaLogs results. The verification allows 60 seconds
after completion for receipt. The enriched repeat's stored record contains
source, destination and exporter labels, namespace/status, snapshot time/hash,
and the original addresses, ports and 1:16384 sampling denominator.

The first run used the existing jumbo-MSS connection profile. An intermediate
trial requested a 1200-byte TCP MSS to increase sampling opportunities, but
its throughput projected beyond the safety deadline. I stopped its two test
processes and restored the original profile for the completed repeat. That
trial is recorded in `transfer-2-aborted.json` and `tcp-progress-2.json`; it is
not counted as a successful file transfer. Temporary files were unlinked and
their storage released when the test processes closed. No user files or device
configuration were removed or changed.

TCP retransmissions occurred. Neither successful hashes nor sampled records
prove a lossless forwarding path, maximum throughput or full path coverage.
Samples remain probabilistic; these runs establish observed visibility, not a
guarantee that every future short transfer will produce a sample.

## Ownership enrichment

`nautobot-snapshot.json` contains 301 assigned addresses across 38 modeled
devices, including ten servers. It is an exact assignment lookup, not longest-
prefix guessing. Shared IPs retain all owners; namespace collisions are marked
ambiguous; unassigned/unknown addresses retain raw IPs. The interface label is
address ownership, not the sampled ingress interface. Outer VXLAN endpoints
are not relabeled as inner workloads.

Seven unit tests and four processor-runtime cases passed against OTel contrib
0.154.0 before deployment. The full generated configuration also passed that
binary's validation. The runtime test injects synthetic OTLP only into an
isolated local container, not into lab VictoriaLogs. The completed file tests
use real TCP traffic and real switch-exported sFlow records.

The Collector and dashboard changes were deployed through Argo. The six
management/lab receiver checks passed after rollout. A Collector restart still
loses cached NetFlow v9 templates until exporters refresh them. The local
snapshot has no per-flow Nautobot dependency and must be regenerated when
assignments change. Older stored records are not backfilled.

## Repeating the check

Use the automation host's existing Nautobot access and SSH keys. In another
terminal, forward VictoriaLogs locally:

```sh
kubectl -n observability port-forward svc/victorialogs 19428:9428
```

Then, from blog-sandbox, choose an unused TCP port on the receiver:

```sh
python3 telemetry/sflow_transfer.py --port 47934 --report /tmp/part8-transfer.json
python3 telemetry/verify_sflow_transfer.py /tmp/part8-transfer.json \
  --require-enrichment --output /tmp/part8-transfer-samples.json
```

The verifier fails if there are no matching forward samples or the expected
endpoint labels are absent. Investigate rather than substituting unrelated
background samples. In Grafana, use the transfer's time window and the exact
destination-port regex, such as `^47934$`, in Network Telemetry.
