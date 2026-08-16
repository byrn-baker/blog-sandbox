# 03: VRF / L3VPN Design

## Overview

Each datacenter keeps its own PE VRF and route distinguisher (RD). All three
VRFs import and export `65000:900` for routed DCI reachability while retaining
a site route target (RT) for local identity. This shared RT carries spine and
VTEP loopback routes between sites. EVPN carries MAC, IP, and tenant prefix
reachability between the datacenter fabrics.

## Source of Truth

Nautobot owns the VRF definitions, RDs, device assignments, interface
assignments, and native import and export RouteTarget relationships. Design
Builder creates those objects from `SPDemoLabContext.vrfs` and assigns each
customer VRF to its SPE and PE-CE interface. Golden Config reads the native
relationships through the saved GraphQL query. Config contexts provide device
policy, not VRF inventory.

## VRF Table

| DC | Customer | VRF Name | RD | RT Import | RT Export | PE | CE ASN |
|----|----------|----------|-----|-----------|-----------|-----|--------|
| DC-A | Customer A | `CUST-A` | `65000:100` | `65000:100`, `65000:900` | `65000:100`, `65000:900` | SPE1 | 65001 |
| DC-B | Customer B | `CUST-B` | `65000:200` | `65000:200`, `65000:900` | `65000:200`, `65000:900` | SPE2 | 65002 |
| DC-C | Customer C | `CUST-C` | `65000:300` | `65000:300`, `65000:900` | `65000:300`, `65000:900` | SPE3 | 65003 |

## PE-CE Peering

| PE | VRF | PE IPv4 | CE IPv4 | CE ASN | BGP AFI |
|----|-----|---------|---------|--------|---------|
| SPE1 | CUST-A | `172.16.1.0` | `172.16.1.1` | 65001 | IPv4 unicast |
| SPE2 | CUST-B | `172.16.2.0` | `172.16.2.1` | 65002 | IPv4 unicast |
| SPE3 | CUST-C | `172.16.3.0` | `172.16.3.1` | 65003 | IPv4 unicast |

The PE-CE interfaces also have IPv6 addresses. IPv6 unicast BGP on those links
is not yet modeled or rendered.

## PE VRF Configuration (IOS-XE example)

```ios
! SPE1
vrf definition CUST-A
 rd 65000:100
 address-family ipv4
  route-target export 65000:100
  route-target export 65000:900
  route-target import 65000:100
  route-target import 65000:900
 address-family ipv6
  route-target export 65000:100
  route-target export 65000:900
  route-target import 65000:100
  route-target import 65000:900

interface GigabitEthernet5
 description PE-CE to CE1 GigabitEthernet2 (VRF CUST-A)
 vrf forwarding CUST-A
 ip address 172.16.1.0 255.255.255.254
 ipv6 address fd10:c:1::/127
 no shutdown

router bgp 65000
 address-family ipv4 vrf CUST-A
  neighbor 172.16.1.1 remote-as 65001
  neighbor 172.16.1.1 activate
```

## CE Configuration (IOS-XE example)

```ios
! CE1 in DC-A
interface GigabitEthernet2
 description PE-CE to SPE1 GigabitEthernet5
 ip address 172.16.1.1 255.255.255.254
 ipv6 address fd10:c:1::1/127
 no shutdown

router bgp 65001
 bgp router-id 10.2.1.1
 neighbor 172.16.1.0 remote-as 65000
 address-family ipv4
  neighbor 172.16.1.0 activate
```

## Route Flow

```
DCA-Spine01 Loopback0 (10.2.1.2/32)
  → advertised by eBGP to CE1
    → CE1 advertises it to SPE1 in CUST-A
      → SPE1 exports VPNv4 with RD 65000:100 and RTs 65000:100, 65000:900
        → RR1 and RR2 reflect the VPNv4 route
          → SPE2 and SPE3 import it through shared RT 65000:900
            → remote CE and spine devices gain routed loopback reachability
              → inter-site EVPN sessions use those spine loopbacks
```

## Monitoring Points

| What to monitor | How | Alert condition |
|-----------------|-----|-----------------|
| PE-CE BGP session state | `show bgp vpnv4 unicast all summary` | Peer state != Established |
| VRF route count | `show bgp vpnv4 unicast vrf CUST-A summary` | Route count drops to 0 |
| RT import/export | Config audit | Unexpected RT assignment |
| VPNv4 prefix count on RR | `show bgp vpnv4 unicast all` | Total VPN routes change unexpectedly |
| PE-CE BFD | `show bfd neighbors` | Session down |
