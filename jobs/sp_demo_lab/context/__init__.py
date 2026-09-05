"""SP Demo Lab context — provides topology data to design templates."""

from nautobot_design_builder.context import Context


class SPDemoLabContext(Context):
    """All data derived from the addressing plan (01-addressing.md). Dual-stack IPv4+IPv6."""

    # SP Core — Cisco IOS-XE (CAT8000v)
    # IPv6 loopbacks: fd10:0:1::<last-octet>/128
    sp_core_devices = [
        {"name": "BORDER1", "role": "Border-Router", "ip": "192.168.3.50", "loopback": "10.1.0.10", "loopback6": "fd10:0:1::10", "site": "SP-Core"},
        {"name": "RR1", "role": "Route-Reflector", "ip": "192.168.3.51", "loopback": "10.1.0.1", "loopback6": "fd10:0:1::1", "site": "SP-Core"},
        {"name": "RR2", "role": "Route-Reflector", "ip": "192.168.3.52", "loopback": "10.1.0.2", "loopback6": "fd10:0:1::2", "site": "SP-Core"},
        {"name": "SP1", "role": "P-Router", "ip": "192.168.3.53", "loopback": "10.1.0.3", "loopback6": "fd10:0:1::3", "site": "SP-Core"},
        {"name": "SP2", "role": "P-Router", "ip": "192.168.3.54", "loopback": "10.1.0.4", "loopback6": "fd10:0:1::4", "site": "SP-Core"},
        {"name": "SP3", "role": "P-Router", "ip": "192.168.3.55", "loopback": "10.1.0.5", "loopback6": "fd10:0:1::5", "site": "SP-Core"},
        {"name": "SP4", "role": "P-Router", "ip": "192.168.3.56", "loopback": "10.1.0.6", "loopback6": "fd10:0:1::6", "site": "SP-Core"},
        {"name": "SPE1", "role": "PE-Router", "ip": "192.168.3.57", "loopback": "10.1.0.7", "loopback6": "fd10:0:1::7", "site": "SP-Core"},
        {"name": "SPE2", "role": "PE-Router", "ip": "192.168.3.58", "loopback": "10.1.0.8", "loopback6": "fd10:0:1::8", "site": "SP-Core"},
        {"name": "SPE3", "role": "PE-Router", "ip": "192.168.3.59", "loopback": "10.1.0.9", "loopback6": "fd10:0:1::9", "site": "SP-Core"},
        {"name": "CE1", "role": "CE-Router", "ip": "192.168.3.60", "loopback": "10.2.1.1", "loopback6": "fd10:2:1::1", "site": "DC-A"},
        {"name": "CE2", "role": "CE-Router", "ip": "192.168.3.61", "loopback": "10.2.2.1", "loopback6": "fd10:2:2::1", "site": "DC-B"},
        {"name": "CE3", "role": "CE-Router", "ip": "192.168.3.62", "loopback": "10.2.3.1", "loopback6": "fd10:2:3::1", "site": "DC-C"},
    ]

    # DC-A fabric — Arista vEOS
    # IPv6 loopbacks: fd10:2:1::<last-octet>/128
    dc_a_devices = [
        {"name": "DCA-Spine01", "role": "Spine", "ip": "192.168.3.30", "loopback": "10.2.1.2", "loopback6": "fd10:2:1::2", "site": "DC-A"},
        {"name": "DCA-Spine02", "role": "Spine", "ip": "192.168.3.31", "loopback": "10.2.1.3", "loopback6": "fd10:2:1::3", "site": "DC-A"},
        {"name": "DCA-Leaf01", "role": "Leaf", "ip": "192.168.3.32", "loopback": "10.2.1.4", "loopback6": "fd10:2:1::4", "site": "DC-A", "vtep": "10.3.1.4"},
        {"name": "DCA-Leaf02", "role": "Leaf", "ip": "192.168.3.33", "loopback": "10.2.1.5", "loopback6": "fd10:2:1::5", "site": "DC-A", "vtep": "10.3.1.5"},
        {"name": "DCA-Leaf03", "role": "Leaf", "ip": "192.168.3.34", "loopback": "10.2.1.6", "loopback6": "fd10:2:1::6", "site": "DC-A", "vtep": "10.3.1.6"},
    ]

    # DC-B fabric
    dc_b_devices = [
        {"name": "DCB-Spine01", "role": "Spine", "ip": "192.168.3.35", "loopback": "10.2.2.2", "loopback6": "fd10:2:2::2", "site": "DC-B"},
        {"name": "DCB-Spine02", "role": "Spine", "ip": "192.168.3.36", "loopback": "10.2.2.3", "loopback6": "fd10:2:2::3", "site": "DC-B"},
        {"name": "DCB-Leaf01", "role": "Leaf", "ip": "192.168.3.37", "loopback": "10.2.2.4", "loopback6": "fd10:2:2::4", "site": "DC-B", "vtep": "10.3.2.4"},
        {"name": "DCB-Leaf02", "role": "Leaf", "ip": "192.168.3.38", "loopback": "10.2.2.5", "loopback6": "fd10:2:2::5", "site": "DC-B", "vtep": "10.3.2.5"},
        {"name": "DCB-Leaf03", "role": "Leaf", "ip": "192.168.3.39", "loopback": "10.2.2.6", "loopback6": "fd10:2:2::6", "site": "DC-B", "vtep": "10.3.2.6"},
    ]

    # DC-C fabric
    dc_c_devices = [
        {"name": "DCC-Spine01", "role": "Spine", "ip": "192.168.3.40", "loopback": "10.2.3.2", "loopback6": "fd10:2:3::2", "site": "DC-C"},
        {"name": "DCC-Spine02", "role": "Spine", "ip": "192.168.3.41", "loopback": "10.2.3.3", "loopback6": "fd10:2:3::3", "site": "DC-C"},
        {"name": "DCC-Leaf01", "role": "Leaf", "ip": "192.168.3.42", "loopback": "10.2.3.4", "loopback6": "fd10:2:3::4", "site": "DC-C", "vtep": "10.3.3.4"},
        {"name": "DCC-Leaf02", "role": "Leaf", "ip": "192.168.3.43", "loopback": "10.2.3.5", "loopback6": "fd10:2:3::5", "site": "DC-C", "vtep": "10.3.3.5"},
        {"name": "DCC-Leaf03", "role": "Leaf", "ip": "192.168.3.44", "loopback": "10.2.3.6", "loopback6": "fd10:2:3::6", "site": "DC-C", "vtep": "10.3.3.6"},
    ]

    # SP Core P2P links — (a_device, a_intf, b_device, b_intf, prefix4, v6_a, v6_b)
    # IPv6 P2P: /127 per link from fd10:0:0::/48
    # Last value matches IPv4 last octet (decimal, not hex)
    sp_core_links = [
        ("SP1", "GigabitEthernet2", "SP2", "GigabitEthernet2", "10.0.0.0/31", "fd10:0:0::0", "fd10:0:0::1"),
        ("SP2", "GigabitEthernet3", "SP4", "GigabitEthernet2", "10.0.0.2/31", "fd10:0:0::2", "fd10:0:0::3"),
        ("SP3", "GigabitEthernet5", "SP4", "GigabitEthernet5", "10.0.0.4/31", "fd10:0:0::4", "fd10:0:0::5"),
        ("SP1", "GigabitEthernet3", "SP3", "GigabitEthernet3", "10.0.0.6/31", "fd10:0:0::6", "fd10:0:0::7"),
        ("SP2", "GigabitEthernet4", "SPE1", "GigabitEthernet2", "10.0.0.8/31", "fd10:0:0::8", "fd10:0:0::9"),
        ("SP4", "GigabitEthernet4", "SPE1", "GigabitEthernet4", "10.0.0.10/31", "fd10:0:0::10", "fd10:0:0::11"),
        ("SP4", "GigabitEthernet3", "SPE2", "GigabitEthernet2", "10.0.0.12/31", "fd10:0:0::12", "fd10:0:0::13"),
        ("SP3", "GigabitEthernet4", "SPE2", "GigabitEthernet3", "10.0.0.14/31", "fd10:0:0::14", "fd10:0:0::15"),
        ("SP1", "GigabitEthernet4", "SPE3", "GigabitEthernet2", "10.0.0.16/31", "fd10:0:0::16", "fd10:0:0::17"),
        ("SP3", "GigabitEthernet2", "SPE3", "GigabitEthernet3", "10.0.0.18/31", "fd10:0:0::18", "fd10:0:0::19"),
        ("SP1", "GigabitEthernet5", "RR1", "GigabitEthernet2", "10.0.0.20/31", "fd10:0:0::20", "fd10:0:0::21"),
        ("SP2", "GigabitEthernet5", "RR2", "GigabitEthernet2", "10.0.0.22/31", "fd10:0:0::22", "fd10:0:0::23"),
        ("SP1", "GigabitEthernet6", "BORDER1", "GigabitEthernet2", "10.0.0.24/31", "fd10:0:0::24", "fd10:0:0::25"),
        ("SP2", "GigabitEthernet6", "BORDER1", "GigabitEthernet3", "10.0.0.26/31", "fd10:0:0::26", "fd10:0:0::27"),
    ]

    # PE-CE links — (a_device, a_intf, b_device, b_intf, prefix4, vrf, v6_a, v6_b)
    # All three sites land in CUST-A: the border-leaf design carries every DC's
    # server routes to a single customer VRF so one BORDER1 internet edge and
    # NAT policy serves them all. SPE1/SPE2 land the CE on Gi5; SPE3 uses Gi4
    # because its Gi5 is unused in the lab wiring and CE3 cables to SPE3 Gi4.
    pe_ce_links = [
        ("SPE1", "GigabitEthernet5", "CE1", "GigabitEthernet2", "172.16.1.0/31", "CUST-A", "fd10:c:1::", "fd10:c:1::1"),
        ("SPE2", "GigabitEthernet5", "CE2", "GigabitEthernet2", "172.16.2.0/31", "CUST-A", "fd10:c:2::", "fd10:c:2::1"),
        ("SPE3", "GigabitEthernet4", "CE3", "GigabitEthernet2", "172.16.3.0/31", "CUST-A", "fd10:c:3::", "fd10:c:3::1"),
    ]

    # DC fabric links — (a_device, a_intf, b_device, b_intf, prefix4, v6_a, v6_b)
    # IPv6: fd10:1:x::<v4-last-octet>/127
    dc_a_links = [
        ("CE1", "GigabitEthernet3", "DCA-Spine01", "Ethernet10", "10.1.1.0/31", "fd10:1:1::0", "fd10:1:1::1"),
        ("CE1", "GigabitEthernet4", "DCA-Spine02", "Ethernet10", "10.1.1.2/31", "fd10:1:1::2", "fd10:1:1::3"),
        ("DCA-Spine01", "Ethernet1", "DCA-Leaf01", "Ethernet1", "10.1.1.4/31", "fd10:1:1::4", "fd10:1:1::5"),
        ("DCA-Spine01", "Ethernet2", "DCA-Leaf02", "Ethernet1", "10.1.1.6/31", "fd10:1:1::6", "fd10:1:1::7"),
        ("DCA-Spine01", "Ethernet3", "DCA-Leaf03", "Ethernet1", "10.1.1.8/31", "fd10:1:1::8", "fd10:1:1::9"),
        ("DCA-Spine02", "Ethernet1", "DCA-Leaf01", "Ethernet2", "10.1.1.10/31", "fd10:1:1::10", "fd10:1:1::11"),
        ("DCA-Spine02", "Ethernet2", "DCA-Leaf02", "Ethernet2", "10.1.1.12/31", "fd10:1:1::12", "fd10:1:1::13"),
        ("DCA-Spine02", "Ethernet3", "DCA-Leaf03", "Ethernet2", "10.1.1.14/31", "fd10:1:1::14", "fd10:1:1::15"),
    ]

    dc_b_links = [
        ("CE2", "GigabitEthernet3", "DCB-Spine01", "Ethernet10", "10.1.2.0/31", "fd10:1:2::0", "fd10:1:2::1"),
        ("CE2", "GigabitEthernet4", "DCB-Spine02", "Ethernet10", "10.1.2.2/31", "fd10:1:2::2", "fd10:1:2::3"),
        ("DCB-Spine01", "Ethernet1", "DCB-Leaf01", "Ethernet1", "10.1.2.4/31", "fd10:1:2::4", "fd10:1:2::5"),
        ("DCB-Spine01", "Ethernet2", "DCB-Leaf02", "Ethernet1", "10.1.2.6/31", "fd10:1:2::6", "fd10:1:2::7"),
        ("DCB-Spine01", "Ethernet3", "DCB-Leaf03", "Ethernet1", "10.1.2.8/31", "fd10:1:2::8", "fd10:1:2::9"),
        ("DCB-Spine02", "Ethernet1", "DCB-Leaf01", "Ethernet2", "10.1.2.10/31", "fd10:1:2::10", "fd10:1:2::11"),
        ("DCB-Spine02", "Ethernet2", "DCB-Leaf02", "Ethernet2", "10.1.2.12/31", "fd10:1:2::12", "fd10:1:2::13"),
        ("DCB-Spine02", "Ethernet3", "DCB-Leaf03", "Ethernet2", "10.1.2.14/31", "fd10:1:2::14", "fd10:1:2::15"),
    ]

    dc_c_links = [
        ("CE3", "GigabitEthernet3", "DCC-Spine01", "Ethernet10", "10.1.3.0/31", "fd10:1:3::0", "fd10:1:3::1"),
        ("CE3", "GigabitEthernet4", "DCC-Spine02", "Ethernet10", "10.1.3.2/31", "fd10:1:3::2", "fd10:1:3::3"),
        ("DCC-Spine01", "Ethernet1", "DCC-Leaf01", "Ethernet1", "10.1.3.4/31", "fd10:1:3::4", "fd10:1:3::5"),
        ("DCC-Spine01", "Ethernet2", "DCC-Leaf02", "Ethernet1", "10.1.3.6/31", "fd10:1:3::6", "fd10:1:3::7"),
        ("DCC-Spine01", "Ethernet3", "DCC-Leaf03", "Ethernet1", "10.1.3.8/31", "fd10:1:3::8", "fd10:1:3::9"),
        ("DCC-Spine02", "Ethernet1", "DCC-Leaf01", "Ethernet2", "10.1.3.10/31", "fd10:1:3::10", "fd10:1:3::11"),
        ("DCC-Spine02", "Ethernet2", "DCC-Leaf02", "Ethernet2", "10.1.3.12/31", "fd10:1:3::12", "fd10:1:3::13"),
        ("DCC-Spine02", "Ethernet3", "DCC-Leaf03", "Ethernet2", "10.1.3.14/31", "fd10:1:3::14", "fd10:1:3::15"),
    ]

    # BORDER1 internet edge. INET imports the customer routes (65000:100) so
    # it can NAT them, plus the leak RT it owns; it exports only the leak RT
    # (65000:950), which CUST-A imports to pull the default toward NAT.
    internet_edge = {
        "device": "BORDER1",
        "vrf": {
            "name": "INET",
            "rd": "65000:900",
            "description": "Internet edge and NAT routing table",
            "import_targets": ["65000:100", "65000:950"],
            "export_targets": ["65000:950"],
        },
        "inside_interfaces": ["GigabitEthernet2", "GigabitEthernet3"],
        "outside_interface": {
            "name": "GigabitEthernet4",
            "description": "to ext-internet",
            "address_mode": "dhcp",
        },
        "advertise_networks": ["0.0.0.0"],
    }

    # VRFs and route targets. RT 65000:900 carries the shared DCI underlay
    # between the otherwise distinct site VRFs.
    #
    # SERVERS is the DC fabric tenant VRF. It lives on every leaf as an
    # EVPN type-5 L3 VRF (L3 VNI 10000). Its routes leave the fabric only at
    # the border leaf, which hands them to its CE over an eBGP session inside
    # SERVERS. Intra-fabric reachability rides the EVPN route target the
    # template derives from the VNI, so SERVERS carries no MPLS import/export
    # targets of its own.
    vrfs = [
        {
            "name": "MGMT-VRF",
            "rd": "65000:999",
            "description": "Out-of-band management",
            "import_targets": [],
            "export_targets": [],
        },
        {
            "name": "SERVERS",
            "rd": "65000:10000",
            "vni": 10000,
            "description": "DC fabric server tenant (EVPN type-5)",
            "import_targets": [],
            "export_targets": [],
        },
        {
            "name": "CUST-A",
            "rd": "65000:100",
            "description": "Customer A - all DCs",
            # Imports its own routes, the shared DCI RT, and the internet
            # leak RT (65000:950) that INET exports. Exports its own routes
            # and the DCI RT so the servers reach BORDER1's NAT edge.
            "import_targets": ["65000:100", "65000:900", "65000:950"],
            "export_targets": ["65000:100", "65000:900"],
        },
    ]
    route_targets = ["65000:100", "65000:900", "65000:950"]

    # VLAN 100 is one EVPN segment stretched across all sites. Storage stays
    # site-local until its DCI behavior is explicitly defined. Every service
    # SVI lives in the SERVERS VRF so the fabric carries them as EVPN type-5.
    service_vlans = [
        {
            "id": 100,
            "name": "SERVER_K3S",
            "vni": 10100,
            "vrf": "SERVERS",
            "locations": ["DC-A", "DC-B", "DC-C"],
            "location_refs": ["dc_a", "dc_b", "dc_c"],
            "ipv4_prefix": "192.168.100.0/24",
            "ipv4_gateway": "192.168.100.1/24",
            "ipv6_prefix": "fd10:a:100::/64",
            "ipv6_gateway": "fd10:a:100::1/64",
        },
        {
            "id": 101,
            "name": "STORAGE",
            "vni": 10101,
            "vrf": "SERVERS",
            "locations": ["DC-A"],
            "location_refs": ["dc_a"],
            "ipv4_prefix": "192.168.101.0/24",
            "ipv4_gateway": "192.168.101.1/24",
            "ipv6_prefix": "fd10:a:101::/64",
            "ipv6_gateway": "fd10:a:101::1/64",
        },
        {
            "id": 201,
            "name": "STORAGE",
            "vni": 10201,
            "vrf": "SERVERS",
            "locations": ["DC-B"],
            "location_refs": ["dc_b"],
            "ipv4_prefix": "192.168.201.0/24",
            "ipv4_gateway": "192.168.201.1/24",
            "ipv6_prefix": "fd10:a:201::/64",
            "ipv6_gateway": "fd10:a:201::1/64",
        },
        {
            "id": 301,
            "name": "STORAGE",
            "vni": 10301,
            "vrf": "SERVERS",
            "locations": ["DC-C"],
            "location_refs": ["dc_c"],
            "ipv4_prefix": "192.168.31.0/24",
            "ipv4_gateway": "192.168.31.1/24",
            "ipv6_prefix": "fd10:a:301::/64",
            "ipv6_gateway": "fd10:a:301::1/64",
        },
    ]

    # --- Server VMs (EVPN ESI dual-homed hosts on VLAN 100) ---
    #
    # Every lab VM is dual-homed to Leaf01 + Leaf02 of its site (never the
    # border leaf) over an EVPN Ethernet Segment. The two leaves present a
    # port-channel on the same Ethernet member, share one ESI, and forward
    # all-active. The server bundles its two NICs into one bond.
    #
    # The bond is a static LAG, not LACP. In this nested virtual lab the
    # server's NICs reach the leaves across stacked Linux bridges that will
    # not forward LACP's slow-protocols multicast, so LACP can never form.
    # A static LAG needs no control frames and is transparent to the bridges.
    # The ESI (designated-forwarder election, split-horizon, all-active) is an
    # EVPN control-plane function and is unaffected by the static/LACP choice.
    #
    # Deterministic per-server scheme, keyed off the VLAN 100 host octet:
    #   port-channel number = the leaf Ethernet member index (same on both
    #                         leaves in the pair)
    #   ESI identifier      = 00<oct>:00<oct>:00<oct>:00<oct>:00<oct>
    #   ES import RT        = 00:<oct>:00:<oct>:00:<oct>
    #
    # NOTE: DNS is live with an older .71-keyed ESI (0071:...). The model
    # re-keys it to its VLAN 100 octet (.53) so the whole fleet follows one
    # rule; the live leaves reconcile to this on the next deploy.
    #
    # host_octet drives the VLAN 100 IP (192.168.100.<octet>), the ESI, and
    # the ES import RT. eth_index is the leaf Ethernet port (Ethernet<index>)
    # and the port-channel number, identical on both leaves of the pair.
    servers = [
        {"name": "DCA-k3s-m1", "site": "DC-A", "mgmt": "192.168.3.63", "host_octet": 10, "leaves": ["DCA-Leaf01", "DCA-Leaf02"], "eth_index": 4},
        {"name": "DCA-k3s-m2", "site": "DC-A", "mgmt": "192.168.3.64", "host_octet": 11, "leaves": ["DCA-Leaf01", "DCA-Leaf02"], "eth_index": 5},
        {"name": "DCA-k3s-m3", "site": "DC-A", "mgmt": "192.168.3.65", "host_octet": 12, "leaves": ["DCA-Leaf01", "DCA-Leaf02"], "eth_index": 6},
        {"name": "DCA-DNS", "site": "DC-A", "mgmt": "192.168.3.71", "host_octet": 53, "leaves": ["DCA-Leaf01", "DCA-Leaf02"], "eth_index": 7},
        {"name": "DCB-k3s-w1", "site": "DC-B", "mgmt": "192.168.3.66", "host_octet": 20, "leaves": ["DCB-Leaf01", "DCB-Leaf02"], "eth_index": 4},
        {"name": "DCB-k3s-w2", "site": "DC-B", "mgmt": "192.168.3.67", "host_octet": 21, "leaves": ["DCB-Leaf01", "DCB-Leaf02"], "eth_index": 5},
        {"name": "DCB-k3s-w3", "site": "DC-B", "mgmt": "192.168.3.68", "host_octet": 22, "leaves": ["DCB-Leaf01", "DCB-Leaf02"], "eth_index": 6},
        {"name": "DCC-k3s-w4", "site": "DC-C", "mgmt": "192.168.3.69", "host_octet": 30, "leaves": ["DCC-Leaf01", "DCC-Leaf02"], "eth_index": 4},
        {"name": "DCC-k3s-w5", "site": "DC-C", "mgmt": "192.168.3.70", "host_octet": 31, "leaves": ["DCC-Leaf01", "DCC-Leaf02"], "eth_index": 5},
        {"name": "DCC-k3s-w6", "site": "DC-C", "mgmt": "192.168.3.72", "host_octet": 32, "leaves": ["DCC-Leaf01", "DCC-Leaf02"], "eth_index": 6},
    ]

    # Border leaves: one per site (DCx-Leaf03). Each has a routed link to its
    # CE inside the SERVERS VRF and an eBGP handoff that carries the fabric
    # server routes out to the CE, which lands them in CUST-A at the PE.
    border_leaves = ["DCA-Leaf03", "DCB-Leaf03", "DCC-Leaf03"]

    # Border links — (leaf, leaf_intf, ce, ce_intf, prefix4, leaf_vrf).
    # Leaf side (.16) sits in SERVERS; the CE side (.17) is global so the CE
    # can advertise the learned routes into its existing PE-CE session.
    border_links = [
        ("DCA-Leaf03", "Ethernet10", "CE1", "GigabitEthernet5", "10.1.1.16/31", "SERVERS"),
        ("DCB-Leaf03", "Ethernet10", "CE2", "GigabitEthernet5", "10.1.2.16/31", "SERVERS"),
        ("DCC-Leaf03", "Ethernet10", "CE3", "GigabitEthernet5", "10.1.3.16/31", "SERVERS"),
    ]

    # Border eBGP handoff — (leaf, leaf_ip, leaf_asn, ce, ce_ip, ce_asn).
    # The leaf peers from its SERVERS interface; the CE peers globally.
    border_ebgp_peerings = [
        {"leaf": "DCA-Leaf03", "leaf_ip": "10.1.1.16", "leaf_asn": 65113, "ce": "CE1", "ce_ip": "10.1.1.17", "ce_asn": 65001, "vrf": "SERVERS"},
        {"leaf": "DCB-Leaf03", "leaf_ip": "10.1.2.16", "leaf_asn": 65213, "ce": "CE2", "ce_ip": "10.1.2.17", "ce_asn": 65002, "vrf": "SERVERS"},
        {"leaf": "DCC-Leaf03", "leaf_ip": "10.1.3.16", "leaf_asn": 65313, "ce": "CE3", "ce_ip": "10.1.3.17", "ce_asn": 65003, "vrf": "SERVERS"},
    ]

    # --- IPv6 Prefixes (parent containers for /127 and /128 assignments) ---
    ipv6_prefixes = [
        {"prefix": "fd10::/48", "description": "SP Core P2P (IPv6)"},
        {"prefix": "fd10:0:1::/48", "description": "SP Core Loopbacks (IPv6)"},
        {"prefix": "fd10:1:1::/48", "description": "DC-A Fabric P2P (IPv6)"},
        {"prefix": "fd10:1:2::/48", "description": "DC-B Fabric P2P (IPv6)"},
        {"prefix": "fd10:1:3::/48", "description": "DC-C Fabric P2P (IPv6)"},
        {"prefix": "fd10:2:1::/48", "description": "DC-A Loopbacks (IPv6)"},
        {"prefix": "fd10:2:2::/48", "description": "DC-B Loopbacks (IPv6)"},
        {"prefix": "fd10:2:3::/48", "description": "DC-C Loopbacks (IPv6)"},
        {"prefix": "fd10:c:1::/48", "description": "CUST-A PE-CE DC-A (IPv6)"},
        {"prefix": "fd10:c:2::/48", "description": "CUST-A PE-CE DC-B (IPv6)"},
        {"prefix": "fd10:c:3::/48", "description": "CUST-A PE-CE DC-C (IPv6)"},
    ]

    # --- Routing context (ISIS + BGP) ---

    # ISIS area (49.0001 = private, Level-2 only)
    isis_area = "49.0001"

    # Devices running ISIS (all P, PE, RR, Border — not CEs)
    isis_devices = ["RR1", "RR2", "SP1", "SP2", "SP3", "SP4", "SPE1", "SPE2", "SPE3", "BORDER1"]

    # Autonomous Systems
    autonomous_systems = [
        {"asn": 65000, "description": "SP Core iBGP"},
        {"asn": 65001, "description": "Customer A (CE1)"},
        {"asn": 65002, "description": "Customer B (CE2)"},
        {"asn": 65003, "description": "Customer C (CE3)"},
        {"asn": 65101, "description": "DC-A Spines"},
        {"asn": 65111, "description": "DC-A Leaf01"},
        {"asn": 65112, "description": "DC-A Leaf02"},
        {"asn": 65113, "description": "DC-A Leaf03"},
        {"asn": 65201, "description": "DC-B Spines"},
        {"asn": 65211, "description": "DC-B Leaf01"},
        {"asn": 65212, "description": "DC-B Leaf02"},
        {"asn": 65213, "description": "DC-B Leaf03"},
        {"asn": 65301, "description": "DC-C Spines"},
        {"asn": 65311, "description": "DC-C Leaf01"},
        {"asn": 65312, "description": "DC-C Leaf02"},
        {"asn": 65313, "description": "DC-C Leaf03"},
    ]

    # BGP Routing Instances — device, ASN, router-id (loopback IP)
    bgp_instances = [
        {"device": "RR1", "asn": 65000, "router_id": "10.1.0.1"},
        {"device": "RR2", "asn": 65000, "router_id": "10.1.0.2"},
        {"device": "SPE1", "asn": 65000, "router_id": "10.1.0.7"},
        {"device": "SPE2", "asn": 65000, "router_id": "10.1.0.8"},
        {"device": "SPE3", "asn": 65000, "router_id": "10.1.0.9"},
        {"device": "BORDER1", "asn": 65000, "router_id": "10.1.0.10"},
        {"device": "CE1", "asn": 65001, "router_id": "10.2.1.1"},
        {"device": "CE2", "asn": 65002, "router_id": "10.2.2.1"},
        {"device": "CE3", "asn": 65003, "router_id": "10.2.3.1"},
    ]

    # iBGP Peerings: PE/Border ↔ RR (VPNv4 + VPNv6, source = Loopback0)
    ibgp_peerings = [
        {"a_device": "SPE1", "a_ip": "10.1.0.7", "b_device": "RR1", "b_ip": "10.1.0.1"},
        {"a_device": "SPE1", "a_ip": "10.1.0.7", "b_device": "RR2", "b_ip": "10.1.0.2"},
        {"a_device": "SPE2", "a_ip": "10.1.0.8", "b_device": "RR1", "b_ip": "10.1.0.1"},
        {"a_device": "SPE2", "a_ip": "10.1.0.8", "b_device": "RR2", "b_ip": "10.1.0.2"},
        {"a_device": "SPE3", "a_ip": "10.1.0.9", "b_device": "RR1", "b_ip": "10.1.0.1"},
        {"a_device": "SPE3", "a_ip": "10.1.0.9", "b_device": "RR2", "b_ip": "10.1.0.2"},
        {"a_device": "BORDER1", "a_ip": "10.1.0.10", "b_device": "RR1", "b_ip": "10.1.0.1"},
        {"a_device": "BORDER1", "a_ip": "10.1.0.10", "b_device": "RR2", "b_ip": "10.1.0.2"},
    ]

    # eBGP Peerings: PE ↔ CE (IPv4 unicast in VRF). All three land in CUST-A.
    ebgp_peerings = [
        {"pe": "SPE1", "pe_ip": "172.16.1.0", "pe_asn": 65000, "ce": "CE1", "ce_ip": "172.16.1.1", "ce_asn": 65001, "vrf": "CUST-A"},
        {"pe": "SPE2", "pe_ip": "172.16.2.0", "pe_asn": 65000, "ce": "CE2", "ce_ip": "172.16.2.1", "ce_asn": 65002, "vrf": "CUST-A"},
        {"pe": "SPE3", "pe_ip": "172.16.3.0", "pe_asn": 65000, "ce": "CE3", "ce_ip": "172.16.3.1", "ce_asn": 65003, "vrf": "CUST-A"},
    ]

    # Highest GigabitEthernet data port each Cisco device actually presents in
    # the lab (Gi1 is always management). The CAT8000v boots with a variable
    # port count per node, so the SoT must model each device's real inventory
    # rather than a uniform range, or the intended config references ports that
    # do not exist and can never be made compliant. Verified against the live
    # devices. Any device not listed falls back to the default (8).
    cisco_max_gi_port = {
        "RR1": 2, "RR2": 2,
        "SP1": 6, "SP2": 6, "SP3": 5, "SP4": 5,
        "SPE1": 5, "SPE2": 5, "SPE3": 5,
        "BORDER1": 4,
        "CE1": 8, "CE2": 8, "CE3": 8,
    }

    # --- BGP settings modeled as extra_attributes (not config context) ---
    # Every BGP knob the nautobot-bgp-models plugin can hold lives on the
    # model object, keyed as Extra Attributes JSON. The design job writes
    # these when it creates the routing instances and peer groups; the
    # templates read them back. Config context keeps only the prefix-list
    # and route-map bodies, which have no native Nautobot object.

    # Routing-instance-level settings, by ASN family.
    # SP core (iBGP 65000) and CE (65001-3) share IOS-XE instance knobs;
    # the DC fabric (Arista) adds maximum_paths/ecmp.
    sp_bgp_instance_attrs = {
        "timers": {"keepalive": 10, "hold": 30},
        "log_neighbor_changes": True,
        "default_ipv4_unicast": False,
    }
    dc_bgp_instance_attrs = {
        "timers": {"keepalive": 3, "hold": 9},
        "maximum_paths": 4,
        "ecmp": 4,
        "log_neighbor_changes": True,
        "default_ipv4_unicast": False,
        "redistribute": {"connected": {"route_map": "RM-CONN-2-BGP"}},
    }

    # Peer-group-level settings (Extra Attributes on the PeerGroup object).
    # SP core iBGP peers source from Loopback0 and fall over on BFD.
    sp_bgp_peer_group_attrs = {
        "RR-CLIENTS": {"update_source": "Loopback0", "fall_over_bfd": True},
        "PE-CLIENTS": {"update_source": "Loopback0", "fall_over_bfd": True, "route_reflector_client": True},
    }
    # DC fabric eBGP underlay + EVPN overlay peer groups. Underlay carries the
    # ipv4 send-community (standard) and a 12000-route limit; overlay carries
    # the EVPN transport knobs and an unlimited route count (0). These match
    # what the fabric actually runs.
    dc_bgp_peer_group_attrs = {
        "IPV4-UNDERLAY-PEERS": {"send_community": True, "maximum_routes": 12000},
        "EVPN-OVERLAY-PEERS": {
            "update_source": "Loopback0",
            "ebgp_multihop": 3,
            "bfd": True,
            "send_community_extended": True,
            "maximum_routes": 0,
            # Relax the overlay hold timer. At the 3/9 instance default the
            # leaf-spine EVPN sessions expire their hold timer under load in
            # this virtual fabric and flap, so EVPN routes never install. The
            # inter-DC DCI already carries the same 30/90 override per neighbor.
            "timers": {"keepalive": 30, "hold": 90},
        },
    }
    # next_hop_unchanged is a spine-only EVPN overlay attribute. Pre-merge the
    # spine overlay dict here so the design template needs no dict-merge filter.
    # ebgp_multihop is 10 on the spines (not 3) because the inter-DC DCI EVPN
    # sessions are spine-to-spine over Loopback0 across the MPLS core, which is
    # ~5-6 hops. At 3 the DCI TCP sessions fail with "No route to host" (TTL
    # exceeded) while ICMP still works. The leaf-spine overlay stays at the
    # peer-group default since those adjacencies are genuinely within 3 hops.
    dc_spine_overlay_attrs = {
        "update_source": "Loopback0",
        "ebgp_multihop": 10,
        "bfd": True,
        "send_community_extended": True,
        "maximum_routes": 0,
        "next_hop_unchanged": True,
        # Same relaxed overlay hold timer as the base peer group, so the
        # spine-side leaf-spine and inter-DC EVPN sessions match at 30/90.
        "timers": {"keepalive": 30, "hold": 90},
    }

    # --- DC Fabric BGP ---

    dc_asn_map = {
        "CE1": 65001, "CE2": 65002, "CE3": 65003,
        "DCA-Spine01": 65101, "DCA-Spine02": 65101,
        "DCA-Leaf01": 65111, "DCA-Leaf02": 65112, "DCA-Leaf03": 65113,
        "DCB-Spine01": 65201, "DCB-Spine02": 65201,
        "DCB-Leaf01": 65211, "DCB-Leaf02": 65212, "DCB-Leaf03": 65213,
        "DCC-Spine01": 65301, "DCC-Spine02": 65301,
        "DCC-Leaf01": 65311, "DCC-Leaf02": 65312, "DCC-Leaf03": 65313,
    }

    dc_bgp_instances = [
        {"device": "DCA-Spine01", "asn": 65101, "router_id": "10.2.1.2"},
        {"device": "DCA-Spine02", "asn": 65101, "router_id": "10.2.1.3"},
        {"device": "DCA-Leaf01", "asn": 65111, "router_id": "10.2.1.4"},
        {"device": "DCA-Leaf02", "asn": 65112, "router_id": "10.2.1.5"},
        {"device": "DCA-Leaf03", "asn": 65113, "router_id": "10.2.1.6"},
        {"device": "DCB-Spine01", "asn": 65201, "router_id": "10.2.2.2"},
        {"device": "DCB-Spine02", "asn": 65201, "router_id": "10.2.2.3"},
        {"device": "DCB-Leaf01", "asn": 65211, "router_id": "10.2.2.4"},
        {"device": "DCB-Leaf02", "asn": 65212, "router_id": "10.2.2.5"},
        {"device": "DCB-Leaf03", "asn": 65213, "router_id": "10.2.2.6"},
        {"device": "DCC-Spine01", "asn": 65301, "router_id": "10.2.3.2"},
        {"device": "DCC-Spine02", "asn": 65301, "router_id": "10.2.3.3"},
        {"device": "DCC-Leaf01", "asn": 65311, "router_id": "10.2.3.4"},
        {"device": "DCC-Leaf02", "asn": 65312, "router_id": "10.2.3.5"},
        {"device": "DCC-Leaf03", "asn": 65313, "router_id": "10.2.3.6"},
    ]

    # Full-mesh inter-site EVPN between the two spines at each site. The
    # MPLS L3VPN provides routed reachability between these Loopback0 sources.
    dci_evpn_peerings = [
        {"a_device": "DCA-Spine01", "a_ip": "10.2.1.2", "b_device": "DCB-Spine01", "b_ip": "10.2.2.2"},
        {"a_device": "DCA-Spine01", "a_ip": "10.2.1.2", "b_device": "DCB-Spine02", "b_ip": "10.2.2.3"},
        {"a_device": "DCA-Spine02", "a_ip": "10.2.1.3", "b_device": "DCB-Spine01", "b_ip": "10.2.2.2"},
        {"a_device": "DCA-Spine02", "a_ip": "10.2.1.3", "b_device": "DCB-Spine02", "b_ip": "10.2.2.3"},
        {"a_device": "DCA-Spine01", "a_ip": "10.2.1.2", "b_device": "DCC-Spine01", "b_ip": "10.2.3.2"},
        {"a_device": "DCA-Spine01", "a_ip": "10.2.1.2", "b_device": "DCC-Spine02", "b_ip": "10.2.3.3"},
        {"a_device": "DCA-Spine02", "a_ip": "10.2.1.3", "b_device": "DCC-Spine01", "b_ip": "10.2.3.2"},
        {"a_device": "DCA-Spine02", "a_ip": "10.2.1.3", "b_device": "DCC-Spine02", "b_ip": "10.2.3.3"},
        {"a_device": "DCB-Spine01", "a_ip": "10.2.2.2", "b_device": "DCC-Spine01", "b_ip": "10.2.3.2"},
        {"a_device": "DCB-Spine01", "a_ip": "10.2.2.2", "b_device": "DCC-Spine02", "b_ip": "10.2.3.3"},
        {"a_device": "DCB-Spine02", "a_ip": "10.2.2.3", "b_device": "DCC-Spine01", "b_ip": "10.2.3.2"},
        {"a_device": "DCB-Spine02", "a_ip": "10.2.2.3", "b_device": "DCC-Spine02", "b_ip": "10.2.3.3"},
    ]
