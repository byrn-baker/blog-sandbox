# SNMP interface names and event-source audit

The live audit reached all 28 network devices. SNMP held 372 interface rows:
318 names present in the devices' `show interfaces` output, 28 MPLS protocol-layer
rows and 26 IOS null sinks. The CLI contained nine additional internal Arista
`Vlan4097` interfaces absent from the collected IF-MIB rows. The normal dashboard
now displays the 318 matching names. The raw metric labels and stored rows remain
unchanged, and the MPLS diagnostic table remains available.

`interface-name-comparison.json` records the comparison before the display filters.
`snmp_only` includes the null sinks; it does not mean an interface was renamed.
`cli_only` records the nine internal VLAN exceptions. Live examples were
`Ethernet1` on DCA-Leaf01 and `GigabitEthernet2` on CE1. Cisco's separate `if_name`
label contained `Gi2`; the dashboard uses the full `interface` label instead.

## Event collection is not deployed

Four canaries were inspected: CE1, SP1, DCA-Leaf01 and DCA-Spine01. Each had zero
`snmp-server host` destinations. The Collector has polling receivers and no SNMP
trap listener or UDP 162 Service. No end-to-end trap receipt was demonstrated.
Existing device logs were read without creating a routing or interface flap.

| Source | Live evidence | Collection implication |
|---|---|---|
| Arista BGP/link events | EOS 4.34.6M `show snmp notification` lists BGP established/backward transitions and link-up/link-down | Notification support is present; a destination and receiver are still needed |
| Arista BFD events | No BFD entry in that notification catalog; device logs contain `%BFD-5-STATE_CHANGE`, peer IP, VRF and diagnostic reason | Use syslog for the observed BFD events; do not promise a BFD trap on this image |
| Arista IS-IS events | Notification catalog lists adjacency-change and related notifications | Capability only; the sampled Arista devices do not provide an active IS-IS test |
| Cisco BFD | IOS XE 17.15.01a registers Cisco BFD objects; direct SNMP GETNEXT returned data under the Cisco BFD subtree | Object availability is verified; notification delivery and complete peer-state polling are not |
| BGP state polling | Direct SNMP GETNEXT returned BGP peer-state rows on CE1 and both Arista canaries | Available to add to the polling configuration; not currently a collected metric family |
| Cisco IS-IS events | SP1 logs contain `%CLNS-5-ADJCHANGE` with neighbor and interface | Syslog provides the observed adjacency events |

`protocol-oid-probes.json` records bounded GETNEXT checks. An empty subtree does
not establish universal platform non-support: sessions may be absent, use another
MIB or live in another context. SP1 returned no row in the standard BGP peer-state
subtree. The probes did not find data in the standard IS-IS subtree on any canary.

Cisco documents BFD notification enablement in its
[SNMP command reference](https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/snmp/command/nm-snmp-cr-book/nm-snmp-cr-s4.html).
That documentation is not proof that a notification was emitted by this lab.
The [OpenTelemetry SNMP receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/v0.154.0/receiver/snmpreceiver)
collects polled metrics; enabling device traps alone would not deliver events to
this pipeline.

A collection rollout needs a reachable management-VRF destination, a trap
listener and decoder, and syslog ingestion for the BFD details observed on EOS.
The declared telemetry plan requires centralized logs. Event records should
retain device, peer, VRF, interface and reason so they can be correlated with the
interface graphs. Validate a safe test notification on one device per platform
before expanding; no interface shutdown is needed merely to test delivery.

## Dashboard verification

Sixteen generator tests passed, including a Helm regression test for legend placeholders. All 16 panel expressions were executed against
live data in three selections: the entire fleet, CE1/GigabitEthernet2 and
DCA-Leaf01/Ethernet1. All 48 queries completed successfully. The empty MPLS
diagnostic for the two selected canaries is expected. The saved query check
records contain only metric metadata, not credentials.

The initial Argo comparison rejected unescaped Grafana legend placeholders in
Helm's `tpl` pass. Collection and the old dashboard continued running. The
correction escapes those placeholders only when generating chart values. The
pinned Collector chart then rendered successfully, and its decoded dashboard
matched the generator definition exactly. The remaining Collector settings and
credential revision were unchanged.

After Argo reconciliation, all five Applications were Synced/Healthy and all 18
observability pods were Ready. Fresh samples covered all 28 network devices;
the normal interface view contained 318 rows. Browser checks of the deployed
dashboard confirmed `CE1 / GigabitEthernet2` and `DCA-Leaf01 / Ethernet1`, readable
Up states, explicit error/discard rates and no exposed `if_index` legends.
The screenshots in this directory show the deployed interface tables. These
checks validate the SNMP dashboard, not an event receiver or a network soak test.
