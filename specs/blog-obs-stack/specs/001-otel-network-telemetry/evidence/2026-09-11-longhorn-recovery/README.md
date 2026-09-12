# Longhorn recovery and TCP checks, 2026-09-11

Status at approximately 15:36 UTC: application service restored, full storage redundancy and fabric stability unresolved.

The user rebooted CE2 and SPE2 after a one-way receive failure isolated DC-B. Post-reboot reads verified bidirectional traffic, MTU 9216, established PE-CE BGP and nine Ready Kubernetes nodes. All 12 IPv4/IPv6 host jumbo tests passed at 9000 bytes.

Longhorn automatically salvaged VictoriaMetrics. Removed 253 orphan snapshot attachment tickets from VictoriaMetrics and 12 from Grafana. Existing snapshot records and live CSI tickets were preserved. CSI attachment subsequently succeeded. Both application pods became Ready, and a historical query returned 59 up series over the last 24 hours. This does not establish complete historical sample integrity following salvage.

Grafana has three healthy replicas. VictoriaMetrics has two synchronized replicas on DC-B workers w2 and w3. Its third replica on DC-C worker w6 failed during rebuilding with `replica is already rebuilding`; Longhorn created a replacement and restarted the transfer. The volume remains attached and degraded.

## TCP samples during recovery

Each completed test sent 1 MiB and echoed 1 MiB. These are application transfer times, not an iperf saturation benchmark. Replica rebuilding was active, so they are not a clean post-recovery baseline.

| Path | Earlier seconds | Current seconds | Combined Mbps | Retransmissions |
| --- | ---: | ---: | ---: | ---: |
| DC-B w1 to DC-A m1 | 15.105 | 48.388 | 0.347 | 97 |
| DC-C w4 to DC-A m1 | 42.524 | Incomplete | Not measured | Not measured |
| DC-B w1 to DC-C w4 | 48.462 | 39.712 | 0.422 | 63 |

The DC-C to DC-A retry exceeded the 80-second SSH probe deadline; the first attempt also failed. The exact network cause of that incomplete transfer is not established. Completed probes negotiated MSS 8948 and PMTU 9000 and verified echoed bytes. TCP remains slow despite jumbo reachability.

## Outstanding network fault

The fleet readback found all 42 EOS underlay and 60 EVPN sessions established, but only 26 directed IS-IS neighbors UP instead of 28. SP3 sees SPE3 in INIT. SPE3 Gi3 reports up/up and MTU 9216 but no received packets for over 1 hour 40 minutes; SP3 Gi2 still receives SPE3 traffic. SPE3 retains its SP1 adjacency. This resembles the earlier SPE2 receive stall; the root cause is unproven.

The user approved targeted SPE3 recovery. The interface reset failed. Saved the configuration, verified operational running/startup equality allowing generated PKI representation differences, and gracefully reloaded SPE3. Both IS-IS adjacencies returned UP, and both links passed 3/3 9216-byte DF pings. The full fleet audit then verified all 28 directed IS-IS adjacencies UP, 42 EOS underlay sessions established, and 60 EVPN sessions established. All nine Kubernetes nodes and both application pods were Ready. Grafana was healthy; VictoriaMetrics retained two synchronized replicas and restarted rebuilding its third.

## After approved SPE3 restart

TCP was repeated during an initially idle rebuild window; Longhorn resumed rebuilding during the test sequence, so the sequence is not a fully idle baseline.

| Path | Seconds for 1 MiB each way | Retransmissions | Result |
| --- | ---: | ---: | --- |
| DC-C w4 to DC-A m1 | 52.213 | 54 | Byte integrity verified |
| DC-B w1 to DC-C w4 | Not completed | Not measured | Server socket timeout; client incomplete reply |
| DC-B w1 to DC-A m1 | 15.056 | 77 | Byte integrity verified |

Completed connections negotiated MSS 8948 and PMTU 9000. Repairing SPE3 restored routing redundancy but did not establish stable TCP performance. VictoriaMetrics remains degraded while Longhorn attempts the third replica. Full storage recovery and an idle-network TCP baseline remain unverified.
