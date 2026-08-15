"""SP Demo Lab context — provides topology data to design templates."""

from nautobot_design_builder.context import Context


class SPDemoLabContext(Context):
    """All data derived from the addressing plan (01-addressing.md). Dual-stack IPv4+IPv6."""

    # Management network prefix length (192.168.3.0/24)
    mgmt_prefix_len = 24

    # SP Core — Cisco IOS-XE (CAT8000v)
    # IPv6 loopbacks: fd10:0:1::<last-octet>/128
    sp_core_devices = [
        {"name": "BORDER1", "role": "Border-Router", "ip": "192.168.3.19", "loopback": "10.1.0.10", "loopback6": "fd10:0:1::10", "site": "SP-Core"},
        {"name": "RR1", "role": "Route-Reflector", "ip": "192.168.3.20", "loopback": "10.1.0.1", "loopback6": "fd10:0:1::1", "site": "SP-Core"},
        {"name": "RR2", "role": "Route-Reflector", "ip": "192.168.3.21", "loopback": "10.1.0.2", "loopback6": "fd10:0:1::2", "site": "SP-Core"},
        {"name": "SP1", "role": "P-Router", "ip": "192.168.3.22", "loopback": "10.1.0.3", "loopback6": "fd10:0:1::3", "site": "SP-Core"},
        {"name": "SP2", "role": "P-Router", "ip": "192.168.3.23", "loopback": "10.1.0.4", "loopback6": "fd10:0:1::4", "site": "SP-Core"},
        {"name": "SP3", "role": "P-Router", "ip": "192.168.3.24", "loopback": "10.1.0.5", "loopback6": "fd10:0:1::5", "site": "SP-Core"},
        {"name": "SP4", "role": "P-Router", "ip": "192.168.3.25", "loopback": "10.1.0.6", "loopback6": "fd10:0:1::6", "site": "SP-Core"},
        {"name": "SPE1", "role": "PE-Router", "ip": "192.168.3.26", "loopback": "10.1.0.7", "loopback6": "fd10:0:1::7", "site": "SP-Core"},
        {"name": "SPE2", "role": "PE-Router", "ip": "192.168.3.27", "loopback": "10.1.0.8", "loopback6": "fd10:0:1::8", "site": "SP-Core"},
        {"name": "SPE3", "role": "PE-Router", "ip": "192.168.3.28", "loopback": "10.1.0.9", "loopback6": "fd10:0:1::9", "site": "SP-Core"},
        {"name": "CE1", "role": "CE-Router", "ip": "192.168.3.29", "loopback": "10.2.1.1", "loopback6": "fd10:2:1::1", "site": "DC-A"},
        {"name": "CE2", "role": "CE-Router", "ip": "192.168.3.30", "loopback": "10.2.2.1", "loopback6": "fd10:2:2::1", "site": "DC-B"},
        {"name": "CE3", "role": "CE-Router", "ip": "192.168.3.31", "loopback": "10.2.3.1", "loopback6": "fd10:2:3::1", "site": "DC-C"},
    ]

    # DC-A fabric — Arista vEOS
    # IPv6 loopbacks: fd10:2:1::<last-octet>/128
    dc_a_devices = [
        {"name": "DCA-Spine01", "role": "Spine", "ip": "192.168.3.40", "loopback": "10.2.1.2", "loopback6": "fd10:2:1::2", "site": "DC-A"},
        {"name": "DCA-Spine02", "role": "Spine", "ip": "192.168.3.41", "loopback": "10.2.1.3", "loopback6": "fd10:2:1::3", "site": "DC-A"},
        {"name": "DCA-Leaf01", "role": "Leaf", "ip": "192.168.3.42", "loopback": "10.2.1.4", "loopback6": "fd10:2:1::4", "site": "DC-A", "vtep": "10.3.1.4"},
        {"name": "DCA-Leaf02", "role": "Leaf", "ip": "192.168.3.43", "loopback": "10.2.1.5", "loopback6": "fd10:2:1::5", "site": "DC-A", "vtep": "10.3.1.5"},
        {"name": "DCA-Leaf03", "role": "Leaf", "ip": "192.168.3.44", "loopback": "10.2.1.6", "loopback6": "fd10:2:1::6", "site": "DC-A", "vtep": "10.3.1.6"},
    ]

    # DC-B fabric
    dc_b_devices = [
        {"name": "DCB-Spine01", "role": "Spine", "ip": "192.168.3.50", "loopback": "10.2.2.2", "loopback6": "fd10:2:2::2", "site": "DC-B"},
        {"name": "DCB-Spine02", "role": "Spine", "ip": "192.168.3.51", "loopback": "10.2.2.3", "loopback6": "fd10:2:2::3", "site": "DC-B"},
        {"name": "DCB-Leaf01", "role": "Leaf", "ip": "192.168.3.52", "loopback": "10.2.2.4", "loopback6": "fd10:2:2::4", "site": "DC-B", "vtep": "10.3.2.4"},
        {"name": "DCB-Leaf02", "role": "Leaf", "ip": "192.168.3.53", "loopback": "10.2.2.5", "loopback6": "fd10:2:2::5", "site": "DC-B", "vtep": "10.3.2.5"},
        {"name": "DCB-Leaf03", "role": "Leaf", "ip": "192.168.3.54", "loopback": "10.2.2.6", "loopback6": "fd10:2:2::6", "site": "DC-B", "vtep": "10.3.2.6"},
    ]

    # DC-C fabric
    dc_c_devices = [
        {"name": "DCC-Spine01", "role": "Spine", "ip": "192.168.3.60", "loopback": "10.2.3.2", "loopback6": "fd10:2:3::2", "site": "DC-C"},
        {"name": "DCC-Spine02", "role": "Spine", "ip": "192.168.3.61", "loopback": "10.2.3.3", "loopback6": "fd10:2:3::3", "site": "DC-C"},
        {"name": "DCC-Leaf01", "role": "Leaf", "ip": "192.168.3.62", "loopback": "10.2.3.4", "loopback6": "fd10:2:3::4", "site": "DC-C", "vtep": "10.3.3.4"},
        {"name": "DCC-Leaf02", "role": "Leaf", "ip": "192.168.3.63", "loopback": "10.2.3.5", "loopback6": "fd10:2:3::5", "site": "DC-C", "vtep": "10.3.3.5"},
        {"name": "DCC-Leaf03", "role": "Leaf", "ip": "192.168.3.64", "loopback": "10.2.3.6", "loopback6": "fd10:2:3::6", "site": "DC-C", "vtep": "10.3.3.6"},
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
    pe_ce_links = [
        ("SPE1", "GigabitEthernet5", "CE1", "GigabitEthernet2", "172.16.1.0/31", "CUST-A", "fd10:c:1::", "fd10:c:1::1"),
        ("SPE2", "GigabitEthernet5", "CE2", "GigabitEthernet2", "172.16.2.0/31", "CUST-B", "fd10:c:2::", "fd10:c:2::1"),
        ("SPE3", "GigabitEthernet5", "CE3", "GigabitEthernet2", "172.16.3.0/31", "CUST-C", "fd10:c:3::", "fd10:c:3::1"),
    ]

    # DC fabric links — (a_device, a_intf, b_device, b_intf, prefix4, v6_a, v6_b)
    # IPv6: fd10:1:x::<v4-last-octet>/127
    dc_a_links = [
        ("CE1", "GigabitEthernet3", "DCA-Spine01", "Ethernet10", "10.1.1.0/31", "fd10:1:1::0", "fd10:1:1::1"),
        ("CE1", "GigabitEthernet4", "DCA-Spine02", "Ethernet10", "10.1.1.2/31", "fd10:1:1::2", "fd10:1:1::3"),
        ("DCA-Spine01", "Ethernet2", "DCA-Leaf01", "Ethernet1", "10.1.1.4/31", "fd10:1:1::4", "fd10:1:1::5"),
        ("DCA-Spine01", "Ethernet3", "DCA-Leaf02", "Ethernet1", "10.1.1.6/31", "fd10:1:1::6", "fd10:1:1::7"),
        ("DCA-Spine01", "Ethernet4", "DCA-Leaf03", "Ethernet1", "10.1.1.8/31", "fd10:1:1::8", "fd10:1:1::9"),
        ("DCA-Spine02", "Ethernet2", "DCA-Leaf01", "Ethernet2", "10.1.1.10/31", "fd10:1:1::10", "fd10:1:1::11"),
        ("DCA-Spine02", "Ethernet3", "DCA-Leaf02", "Ethernet2", "10.1.1.12/31", "fd10:1:1::12", "fd10:1:1::13"),
        ("DCA-Spine02", "Ethernet4", "DCA-Leaf03", "Ethernet2", "10.1.1.14/31", "fd10:1:1::14", "fd10:1:1::15"),
    ]

    dc_b_links = [
        ("CE2", "GigabitEthernet3", "DCB-Spine01", "Ethernet10", "10.1.2.0/31", "fd10:1:2::0", "fd10:1:2::1"),
        ("CE2", "GigabitEthernet4", "DCB-Spine02", "Ethernet10", "10.1.2.2/31", "fd10:1:2::2", "fd10:1:2::3"),
        ("DCB-Spine01", "Ethernet2", "DCB-Leaf01", "Ethernet1", "10.1.2.4/31", "fd10:1:2::4", "fd10:1:2::5"),
        ("DCB-Spine01", "Ethernet3", "DCB-Leaf02", "Ethernet1", "10.1.2.6/31", "fd10:1:2::6", "fd10:1:2::7"),
        ("DCB-Spine01", "Ethernet4", "DCB-Leaf03", "Ethernet1", "10.1.2.8/31", "fd10:1:2::8", "fd10:1:2::9"),
        ("DCB-Spine02", "Ethernet2", "DCB-Leaf01", "Ethernet2", "10.1.2.10/31", "fd10:1:2::10", "fd10:1:2::11"),
        ("DCB-Spine02", "Ethernet3", "DCB-Leaf02", "Ethernet2", "10.1.2.12/31", "fd10:1:2::12", "fd10:1:2::13"),
        ("DCB-Spine02", "Ethernet4", "DCB-Leaf03", "Ethernet2", "10.1.2.14/31", "fd10:1:2::14", "fd10:1:2::15"),
    ]

    dc_c_links = [
        ("CE3", "GigabitEthernet3", "DCC-Spine01", "Ethernet10", "10.1.3.0/31", "fd10:1:3::0", "fd10:1:3::1"),
        ("CE3", "GigabitEthernet4", "DCC-Spine02", "Ethernet10", "10.1.3.2/31", "fd10:1:3::2", "fd10:1:3::3"),
        ("DCC-Spine01", "Ethernet2", "DCC-Leaf01", "Ethernet1", "10.1.3.4/31", "fd10:1:3::4", "fd10:1:3::5"),
        ("DCC-Spine01", "Ethernet3", "DCC-Leaf02", "Ethernet1", "10.1.3.6/31", "fd10:1:3::6", "fd10:1:3::7"),
        ("DCC-Spine01", "Ethernet4", "DCC-Leaf03", "Ethernet1", "10.1.3.8/31", "fd10:1:3::8", "fd10:1:3::9"),
        ("DCC-Spine02", "Ethernet2", "DCC-Leaf01", "Ethernet2", "10.1.3.10/31", "fd10:1:3::10", "fd10:1:3::11"),
        ("DCC-Spine02", "Ethernet3", "DCC-Leaf02", "Ethernet2", "10.1.3.12/31", "fd10:1:3::12", "fd10:1:3::13"),
        ("DCC-Spine02", "Ethernet4", "DCC-Leaf03", "Ethernet2", "10.1.3.14/31", "fd10:1:3::14", "fd10:1:3::15"),
    ]

    # VRFs
    vrfs = [
        {"name": "MGMT-VRF", "rd": "65000:999"},
        {"name": "CUST-A", "rd": "65000:100"},
        {"name": "CUST-B", "rd": "65000:200"},
        {"name": "CUST-C", "rd": "65000:300"},
    ]

    # --- IPv6 Prefixes (parent containers for /127 and /128 assignments) ---
    ipv6_prefixes = [
        {"prefix": "fd10:0:0::/48", "description": "SP Core P2P (IPv6)"},
        {"prefix": "fd10:0:1::/48", "description": "SP Core Loopbacks (IPv6)"},
        {"prefix": "fd10:1:1::/48", "description": "DC-A Fabric P2P (IPv6)"},
        {"prefix": "fd10:1:2::/48", "description": "DC-B Fabric P2P (IPv6)"},
        {"prefix": "fd10:1:3::/48", "description": "DC-C Fabric P2P (IPv6)"},
        {"prefix": "fd10:2:1::/48", "description": "DC-A Loopbacks (IPv6)"},
        {"prefix": "fd10:2:2::/48", "description": "DC-B Loopbacks (IPv6)"},
        {"prefix": "fd10:2:3::/48", "description": "DC-C Loopbacks (IPv6)"},
        {"prefix": "fd10:c:1::/48", "description": "CUST-A PE-CE (IPv6)"},
        {"prefix": "fd10:c:2::/48", "description": "CUST-B PE-CE (IPv6)"},
        {"prefix": "fd10:c:3::/48", "description": "CUST-C PE-CE (IPv6)"},
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
        {"device": "CE1", "asn": 65001, "router_id": "10.2.1.1"},
        {"device": "CE2", "asn": 65002, "router_id": "10.2.2.1"},
        {"device": "CE3", "asn": 65003, "router_id": "10.2.3.1"},
    ]

    # iBGP Peerings: PE ↔ RR (VPNv4 + VPNv6, source = Loopback0)
    ibgp_peerings = [
        {"a_device": "SPE1", "a_ip": "10.1.0.7", "b_device": "RR1", "b_ip": "10.1.0.1"},
        {"a_device": "SPE1", "a_ip": "10.1.0.7", "b_device": "RR2", "b_ip": "10.1.0.2"},
        {"a_device": "SPE2", "a_ip": "10.1.0.8", "b_device": "RR1", "b_ip": "10.1.0.1"},
        {"a_device": "SPE2", "a_ip": "10.1.0.8", "b_device": "RR2", "b_ip": "10.1.0.2"},
        {"a_device": "SPE3", "a_ip": "10.1.0.9", "b_device": "RR1", "b_ip": "10.1.0.1"},
        {"a_device": "SPE3", "a_ip": "10.1.0.9", "b_device": "RR2", "b_ip": "10.1.0.2"},
    ]

    # eBGP Peerings: PE ↔ CE (IPv4 unicast in VRF)
    ebgp_peerings = [
        {"pe": "SPE1", "pe_ip": "172.16.1.0", "pe_asn": 65000, "ce": "CE1", "ce_ip": "172.16.1.1", "ce_asn": 65001, "vrf": "CUST-A"},
        {"pe": "SPE2", "pe_ip": "172.16.2.0", "pe_asn": 65000, "ce": "CE2", "ce_ip": "172.16.2.1", "ce_asn": 65002, "vrf": "CUST-B"},
        {"pe": "SPE3", "pe_ip": "172.16.3.0", "pe_asn": 65000, "ce": "CE3", "ce_ip": "172.16.3.1", "ce_asn": 65003, "vrf": "CUST-C"},
    ]

    # --- DC Fabric BGP ---

    dc_asn_map = {
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
