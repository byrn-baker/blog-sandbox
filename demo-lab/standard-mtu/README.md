# Standard lab MTU rollout

Status: prepared, not published or deployed. This replaces the former 1500-byte
core workaround after the CML router virtio migration. The scope is 28 network
devices and ten servers. Management and the external NAT uplink keep their
existing settings.

| Layer | Target |
| --- | ---: |
| Proxmox/EVE/CML lab transport capacity | 9500 |
| Cisco data interfaces | 9216 |
| Arista routed fabric and CE handoffs | 9214 |
| Server bonds, members and tenant VLAN gateways | 9000 |
| Flannel IPv4 VXLAN pod MTU | 8950, verify after restart |

A 9000-byte host IP packet needs 9050 bytes with fabric IPv4 VXLAN and 9058
bytes including the observed two MPLS labels. A 8950-byte pod packet first
becomes a 9000-byte host packet through Flannel. These budgets describe service
traffic; they do not promise a 9214-byte outer IP packet across a 9216-byte
MPLS link. Verify PMTU and full-size BGP traffic as well as service probes.
IPv6 outer tunnels require a different overhead calculation before use.

## Current evidence

The September 11 read-only audit collected all fifteen Arista switches, three
CEs and ten servers. Six spine CE-facing ports remain at IP MTU 1500. The
routed fabric and three Leaf03 CE handoffs are 8950. Tenant gateways are 1500.
All ten server bonds are 1400 and all nine K3s nodes report FLANNEL_MTU=1350.
The Cisco data interfaces already use 9216.

Live EVE VM 118 and CML VM 5001 data vNICs advertise a maximum of 9000. Their
nested router virtio fix did not update these outer vNIC capabilities. Proxmox
vmbr0 is also 9000; its eno1 member supports up to 9600. The separate enp NICs
have a 9000 hardware maximum and are outside this migration. All relevant lab
VM NICs are attached to vmbr0. Validate any physical path used by the lab;
this plan does not establish jumbo service through an external switch.

## Source changes

- Design Builder declares the router, fabric and server MTUs for future builds.
- Standard Lab MTU is a Git-sourced Nautobot job that changes only existing
  modeled MTU fields. It defaults to dry run and requires all 38 modeled devices.
  It excludes management, NAT Outside, loopbacks and dynamic Vlan4097.
- EOS templates consume modeled MTUs, with platform context defaults of 9214
  for routed Ethernet and 9000 for service VLANs.
- Ansible host_network renders 9000 on bond0 and its two members.

The live job preview contains 253 model-field changes: 55 Cisco fields to 9216,
150 EOS physical-interface fields to 9214, and 48 server/service fields to 9000.
This includes fields whose live devices already have the target setting. It is
not a count of required device commands. The model changes are transactional.

## Maintenance sequence

This sequence requires approval for the specific maintenance run under the lab
conventions. It includes loss of the nested lab while EVE/CML are restarted.

1. Capture fresh router/switch running and startup backups, CML/EVE topology,
   current VM NIC settings and controller network configuration. Preserve
   unsaved changes before stopping the nested nodes. Record K3s readiness,
   routing neighbors and storage health as the recovery baseline.
2. Raise the lab transport to 9500 before increasing network-device MTUs.
   The accompanying transport-nics.json contains exact current and proposed
   Proxmox NIC strings for EVE and CML data VLANs 401 through 429. Preserve all
   existing MACs, VLAN tags, firewall flags and other properties. Set persistent
   vmbr0/eno1 capacity to 9500 using the existing Proxmox network configuration.
   Save before/after files for rollback. Do not use a broad host-network restart.
3. Gracefully stop the nested nodes and shut down/start controller VMs 118 and
   5001 so QEMU presents the new vNIC limits. A guest-only reboot does not
   recreate the QEMU devices. Set and persist 9500 on the mapped EVE/CML data
   NICs, bridges and nested lab taps/veth links. Verify new links after lab
   startup too; a one-time ip-link change does not establish persistence.
   Inspect the installed EVE/CML link-creation configuration before changing
   its defaults. Stop if any participating interface still caps packets below
   the required size. Do not force an unsupported MTU.
4. Publish the validated source and sync Nautobot. Preview Standard Lab MTU
   again, then apply it. Regenerate intended configs, collect fresh backups,
   run compliance and create fresh Config Plans. The accompanying per-device
   command previews show only the intended EOS MTU delta and its reversal;
   recreate the actual plans from fresh data before execution.
5. Canary DCA-Spine01 using an MTU-only Config Plan, with Fail Job on Task
   Failure enabled. Verify save, both ends, BGP and bounded large-packet probes.
   Continue with DCA-Spine02, then the three DCA leaves. Complete DC-B and DC-C
   in the same staged order only while routing remains stable. Confirm BORDER1
   and the complete IS-IS graph still operate. Do not change the core MTU again.
6. Before increasing hosts, prove at least 9050-byte outer-IP reachability
   across all six directed site pairs and each CE handoff. Test large TCP/BGP
   transfers and ensure there are no queue stalls or hold-timer resets. Check
   both IPv4 and IPv6 service paths, accounting for the actual encapsulation.
7. Apply host_network through management SSH, one host at a time using
   pb.site.yml --tags network --limit <verified-Nautobot-name>. Start with a
   worker after checking its workloads, then remaining workers, masters one at
   a time, and DNS. Keep the three-master etcd quorum healthy. Restart the local
   K3s service as required for Flannel to re-detect the bond MTU. Inspect
   flannel.1, subnet.env, cni0 and pod veth MTUs; existing pod sandboxes may keep
   their old MTUs. Recreate affected workloads through controlled eviction and
   normal controllers, respecting disruption budgets and storage attachment.
   A successful K3s restart alone is not proof all pods have the new MTU.
8. Verify all nodes Ready, DNS and API reachability, cross-site 9000-byte host
   packets and 8950-byte pod packets, routes, TCP transfers and saved configs.
   Verify after an approved restart of a canary node/link that transport MTUs
   persist. Record remaining exceptions explicitly.

## Rollback

Keep the original VM NIC strings, persistent host-network files, model-field
preview and per-device command reversals. If a transport gate fails, stop
before raising device/host MTUs. If failure occurs after hosts are raised,
restore host/pod service MTUs first, then restore the EOS MTUs and modeled
values, and lower virtual transport last. Preserve the known-working Cisco
9216 settings and do not undo the router virtio migration. Restore only the
settings changed by this run.

## References

[Proxmox MTU default behavior](https://lore.proxmox.com/pve-devel/20250417104855.144882-4-s.hanreich%40proxmox.com/)
explains inheritance of bridge MTU for unspecified VirtIO NIC MTUs.
[Flannel backend documentation](https://github.com/flannel-io/flannel/blob/master/Documentation/backends.md)
and [K3s networking options](https://docs.k3s.io/networking/basic-network-options)
describe the interface and overlay used for the host/pod packet-size budget.
