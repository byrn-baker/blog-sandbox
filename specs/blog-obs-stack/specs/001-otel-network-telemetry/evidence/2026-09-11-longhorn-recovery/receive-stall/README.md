# SPE3 receive stall observed 2026-09-11

SPE3 lost both core receive paths again after its previously approved reboot. This diagnostic run made no configuration changes and did not reboot nodes. Four controlled DC-C to DC-A TCP connection attempts failed before data transfer because the fabric could not resolve the remote endpoint. They are not valid small-packet versus jumbo throughput results.

## Measured fault boundary

CML captures show both directions of IS-IS hellos on SP1-SPE3 and SP3-SPE3. The jumbo Ethernet captures are 9229 bytes, with decoded IS-IS PDU length 9212. SPE3 Gi2 and Gi3 stay up/up with MTU 9216 but their IOS input counters stop advancing. SPE3 has no IS-IS neighbors and its route-reflector sessions are Idle. Management and the CE3-facing interface continue receiving.

These CML interfaces use QEMU UDP socket backends on 127.0.0.1. SPE3 receive ports 21071 and 21073 accumulated roughly 12 MB and 15 MB of kernel receive-queue accounting and continued growing. Management port 21069 and CE-facing port 21075 had no backlog. Thus the present core adjacency failure is localized to delivery into SPE3's virtual NICs inside CML. It is not necessary to traverse the outer EVE/Proxmox fabric to reproduce this failure.

## Ring state

| Interface | Last consumed index | Cached available index before element inspection | Actual guest available index | Available buffers modulo 65536 |
|---|---:|---:|---:|---:|
| Gi2 / net1 | 65535 | 1 | 255 | 256 |
| Gi3 / net2 | 65533 | 0 | 253 | 256 |

Both receive rings have 256 entries and writable head buffers of 2060 bytes. Mergeable receive buffers are negotiated. A jumbo frame needs multiple buffers. Both devices report started, unbroken, and enabled; their consumed indices remain frozen across repeated samples while working interfaces advance.

QMP queue-element introspection reads the actual guest available index and updates QEMU's cached index as a side effect. The repeat snapshot therefore shows cached indices 255 and 253. This inspection did not restore packet consumption; no notification, link reset, or packet injection into QEMU was performed.

## Source-level lead

Running QEMU reports 8.2.2, Ubuntu package 1:8.2.2+ds-0ubuntu1.18. Its upstream split-ring buffer availability scan uses an unsigned integer scan index against a 16-bit cached available index. When the scan crosses 65536, the full-width comparison can retain a stale cached index even though the 16-bit difference reaches zero. The resulting scan can report insufficient buffers despite the guest having replenished the ring.

The local arithmetic reproducer uses both observed index states. Original logic finds only 4120 or 6180 bytes, insufficient for a jumbo frame; a comparison narrowed to 16 bits discovers the replenished buffers and succeeds. Small-buffer requests and a non-wrapping control succeed. This is a model of the relevant arithmetic, not a compiled QEMU integration test or a validated deployable patch.

The exact Ubuntu source package's debian/patches was inspected and contains no patch referencing virtqueue_num_heads or virtqueue_split_get_avail_bytes. This strongly implicates a QEMU receive availability/cached-index defect. We have not proved that it explains all historical TCP retransmissions or validated a supported CML release that fixes it.

Sources:
- https://github.com/qemu/qemu/blob/v8.2.2/hw/virtio/virtio.c
- https://github.com/qemu/qemu/blob/v8.2.2/hw/net/virtio-net.c
- https://launchpad.net/ubuntu/+source/qemu/1:8.2.2+ds-0ubuntu1.18

A separate upstream receive-notification stall fix (f937309fbdbb48c354220a3e7110c202ae4aa7fa) was found during research. It must not be presented as the confirmed fix for this rollover condition without an integration test.

## Next validation

Preserve the stalled state for a supported CML/QEMU fix or isolated reproducer. Test any candidate on one router using jumbo traffic through several counter rollovers, then check IS-IS continuity and repeat bidirectional TCP tests. A reboot restoring service alone does not validate a repair. CML maintenance or device changes require approval for that specific run.

## Scope check

A subsequent read of SP1, SP3, SPE1, SPE2 and SPE3 found a third matching ring state: SP3 Gi4 / net3, last consumed index 65534 and cached available index 1. SP3 has lost its SPE2 adjacency, while SPE2 reports that neighbor INIT. SPE1 retains both core adjacencies. This is independent corroboration of the rollover pattern on a second router.

An alternate four-trial DC-B worker1 to DC-A master2 test also failed with No route to host before TCP connected. Its cause was not separately localized in this run. There is no valid small-versus-jumbo throughput comparison from either path.

SP3 Gi4 fresh interface output confirms up/up, MTU 9216, last input 01:13:33, and last output two seconds ago. Its failure is also receive-only.
