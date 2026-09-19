# Part 7 NOC dashboard integration notes

## Current implementation boundary

The first NOC-oriented dashboard slice is implemented in
`telemetry/network_operations_dashboard.py`. The SNMP generator packages it in
the same Git-managed Grafana ConfigMap as `Network SNMP`. It also copies each
device's Nautobot role into the metric resource attributes. This keeps site,
role, platform and device identity tied to the generated fleet rather than a
dashboard-maintained device list.

The generated desired state contains 28 devices and 31 receivers. The extra
three receivers poll the verified SERVERS VRF BGP contexts. Unit and Helm render
tests pass. All 12 overview queries executed successfully against the live
metrics stores before publication. The pinned Collector Helm chart also rendered
successfully. Browser verification remains outstanding. No device configuration
changed. Publication and Argo reconciliation are tracked with the Git revisions.

## Draft prose for Part 7

### Starting with exceptions instead of every interface

The interface dashboard worked once I knew which device and port I wanted to
inspect. It was a poor place to begin a shift, though. Selecting every device
put hundreds of healthy interfaces into the same graphs. The data was correct,
but it did not answer the first operational question: what needs attention now?

I kept Network SNMP and Network Routing as drill-down dashboards and added a
third view, Network Operations Overview. Its first row counts stale devices,
administratively enabled interfaces that are not operationally Up, non-up BGP,
IS-IS and BFD rows, and recent collector errors. The tables below show only
exceptions, the most utilized interfaces, interfaces producing errors or
discards, and BGP peers that entered Established during the last hour.

An interface that is deliberately shut should not appear as an outage. The
interface exception query therefore joins operational state with administrative
state using the device and IF-MIB index. It reports a row only when the
interface is administratively Up and operationally something other than Up.

The collector already attached each measurement to a device and site. I added
the Nautobot device role to the same generated resource attributes. That lets a
table distinguish a P router, PE router, leaf or spine without embedding another
inventory in Grafana. It is still device context, not service context. The
generic SNMP data cannot yet tell the dashboard which customer or L3VPN is
affected by a failed PE link.

This first overview intentionally stops at verified data. It does not label a
BGP transport session as healthy EVPN, infer an MPLS label-switched path from a
physical interface, or turn absent vendor counters into zero. Syslog, MPLS
service state and VXLAN/EVPN state need separate collection and validation.

## Screenshot and verification checklist

Before moving the draft prose into Part 7:

1. Commit and publish both repository changes through the existing workflow.
2. Confirm the `otel-snmp` Application is Synced and Healthy.
3. Confirm Grafana provisions `/d/network-operations` in the Network folder.
4. Run every overview query against both a healthy all-fleet view and a known
   exception fixture or approved observed event.
5. Check that role labels appear on newly collected samples. Older retained
   series will not gain labels retroactively.
6. Check that an administratively Down interface is absent from the unexpected
   outage table.
7. Capture a browser screenshot with no query errors or misleading empty-state
   values.
8. Record what was measured and what remains unverified. Do not claim syslog,
   MPLS service or EVPN/VNI coverage from this dashboard.
