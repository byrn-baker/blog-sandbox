"""SP Demo Lab context — provides topology data to design templates."""

from nautobot_design_builder.context import Context


class SPDemoLabContext(Context):
    """All data derived from the addressing plan (01-addressing.md)."""

    # SP Core — Cisco IOS-XE (CAT8000v)
    sp_core_devices = [
        {"name": "BORDER1", "role": "Border-Router", "ip": "192.168.3.19", "loopback": "10.1.0.10", "site": "SP-Core"},
        {"name": "RR1", "role": "Route-Reflector", "ip": "192.168.3.20", "loopback": "10.1.0.1", "site": "SP-Core"},
        {"name": "RR2", "role": "Route-Reflector", "ip": "192.168.3.21", "loopback": "10.1.0.2", "site": "SP-Core"},
        {"name": "SP1", "role": "P-Router", "ip": "192.168.3.22", "loopback": "10.1.0.3", "site": "SP-Core"},
        {"name": "SP2", "role": "P-Router", "ip": "192.168.3.23", "loopback": "10.1.0.4", "site": "SP-Core"},
        {"name": "SP3", "role": "P-Router", "ip": "192.168.3.24", "loopback": "10.1.0.5", "site": "SP-Core"},
        {"name": "SP4", "role": "P-Router", "ip": "192.168.3.25", "loopback": "10.1.0.6", "site": "SP-Core"},
        {"name": "SPE1", "role": "PE-Router", "ip": "192.168.3.26", "loopback": "10.1.0.7", "site": "SP-Core"},
        {"name": "SPE2", "role": "PE-Router", "ip": "192.168.3.27", "loopback": "10.1.0.8", "site": "SP-Core"},
        {"name": "SPE3", "role": "PE-Router", "ip": "192.168.3.28", "loopback": "10.1.0.9", "site": "SP-Core"},
        {"name": "CE1", "role": "CE-Router", "ip": "192.168.3.29", "loopback": "10.2.1.1", "site": "DC-A"},
        {"name": "CE2", "role": "CE-Router", "ip": "192.168.3.30", "loopback": "10.2.2.1", "site": "DC-B"},
        {"name": "CE3", "role": "CE-Router", "ip": "192.168.3.31", "loopback": "10.2.3.1", "site": "DC-C"},
    ]

    # DC-A fabric — Arista vEOS
    dc_a_devices = [
        {"name": "DCA-Spine01", "role": "Spine", "ip": "192.168.3.40", "loopback": "10.2.1.2", "site": "DC-A"},
        {"name": "DCA-Spine02", "role": "Spine", "ip": "192.168.3.41", "loopback": "10.2.1.3", "site": "DC-A"},
        {"name": "DCA-Leaf01", "role": "Leaf", "ip": "192.168.3.42", "loopback": "10.2.1.4", "site": "DC-A"},
        {"name": "DCA-Leaf02", "role": "Leaf", "ip": "192.168.3.43", "loopback": "10.2.1.5", "site": "DC-A"},
        {"name": "DCA-Leaf03", "role": "Leaf", "ip": "192.168.3.44", "loopback": "10.2.1.6", "site": "DC-A"},
    ]

    # DC-B fabric
    dc_b_devices = [
        {"name": "DCB-Spine01", "role": "Spine", "ip": "192.168.3.50", "loopback": "10.2.2.2", "site": "DC-B"},
        {"name": "DCB-Spine02", "role": "Spine", "ip": "192.168.3.51", "loopback": "10.2.2.3", "site": "DC-B"},
        {"name": "DCB-Leaf01", "role": "Leaf", "ip": "192.168.3.52", "loopback": "10.2.2.4", "site": "DC-B"},
        {"name": "DCB-Leaf02", "role": "Leaf", "ip": "192.168.3.53", "loopback": "10.2.2.5", "site": "DC-B"},
        {"name": "DCB-Leaf03", "role": "Leaf", "ip": "192.168.3.54", "loopback": "10.2.2.6", "site": "DC-B"},
    ]

    # DC-C fabric
    dc_c_devices = [
        {"name": "DCC-Spine01", "role": "Spine", "ip": "192.168.3.60", "loopback": "10.2.3.2", "site": "DC-C"},
        {"name": "DCC-Spine02", "role": "Spine", "ip": "192.168.3.61", "loopback": "10.2.3.3", "site": "DC-C"},
        {"name": "DCC-Leaf01", "role": "Leaf", "ip": "192.168.3.62", "loopback": "10.2.3.4", "site": "DC-C"},
        {"name": "DCC-Leaf02", "role": "Leaf", "ip": "192.168.3.63", "loopback": "10.2.3.5", "site": "DC-C"},
        {"name": "DCC-Leaf03", "role": "Leaf", "ip": "192.168.3.64", "loopback": "10.2.3.6", "site": "DC-C"},
    ]

    # SP Core P2P links — (a_device, a_intf, b_device, b_intf, prefix)
    sp_core_links = [
        ("SP1", "GigabitEthernet2", "SP2", "GigabitEthernet2", "10.0.0.0/31"),
        ("SP2", "GigabitEthernet3", "SP4", "GigabitEthernet2", "10.0.0.2/31"),
        ("SP3", "GigabitEthernet5", "SP4", "GigabitEthernet5", "10.0.0.4/31"),
        ("SP1", "GigabitEthernet3", "SP3", "GigabitEthernet3", "10.0.0.6/31"),
        ("SP2", "GigabitEthernet4", "SPE1", "GigabitEthernet2", "10.0.0.8/31"),
        ("SP4", "GigabitEthernet4", "SPE1", "GigabitEthernet4", "10.0.0.10/31"),
        ("SP4", "GigabitEthernet3", "SPE2", "GigabitEthernet2", "10.0.0.12/31"),
        ("SP3", "GigabitEthernet4", "SPE2", "GigabitEthernet3", "10.0.0.14/31"),
        ("SP1", "GigabitEthernet4", "SPE3", "GigabitEthernet2", "10.0.0.16/31"),
        ("SP3", "GigabitEthernet4", "SPE3", "GigabitEthernet3", "10.0.0.18/31"),
        ("SP1", "GigabitEthernet5", "RR1", "GigabitEthernet2", "10.0.0.20/31"),
        ("SP2", "GigabitEthernet5", "RR2", "GigabitEthernet2", "10.0.0.22/31"),
        ("SP1", "GigabitEthernet6", "BORDER1", "GigabitEthernet2", "10.0.0.24/31"),
        ("SP2", "GigabitEthernet6", "BORDER1", "GigabitEthernet3", "10.0.0.26/31"),
    ]

    # PE-CE links — (a_device, a_intf, b_device, b_intf, prefix, vrf)
    pe_ce_links = [
        ("SPE1", "GigabitEthernet5", "CE1", "GigabitEthernet2", "172.16.1.0/31", "CUST-A"),
        ("SPE2", "GigabitEthernet5", "CE2", "GigabitEthernet2", "172.16.2.0/31", "CUST-B"),
        ("SPE3", "GigabitEthernet5", "CE3", "GigabitEthernet2", "172.16.3.0/31", "CUST-C"),
    ]

    # DC fabric links — (a_device, a_intf, b_device, b_intf, prefix)
    dc_a_links = [
        ("CE1", "GigabitEthernet3", "DCA-Spine01", "Ethernet1", "10.1.1.0/31"),
        ("CE1", "GigabitEthernet4", "DCA-Spine02", "Ethernet1", "10.1.1.2/31"),
        ("DCA-Spine01", "Ethernet2", "DCA-Leaf01", "Ethernet1", "10.1.1.4/31"),
        ("DCA-Spine01", "Ethernet3", "DCA-Leaf02", "Ethernet1", "10.1.1.6/31"),
        ("DCA-Spine01", "Ethernet4", "DCA-Leaf03", "Ethernet1", "10.1.1.8/31"),
        ("DCA-Spine02", "Ethernet2", "DCA-Leaf01", "Ethernet2", "10.1.1.10/31"),
        ("DCA-Spine02", "Ethernet3", "DCA-Leaf02", "Ethernet2", "10.1.1.12/31"),
        ("DCA-Spine02", "Ethernet4", "DCA-Leaf03", "Ethernet2", "10.1.1.14/31"),
    ]

    dc_b_links = [
        ("CE2", "GigabitEthernet3", "DCB-Spine01", "Ethernet1", "10.1.2.0/31"),
        ("CE2", "GigabitEthernet4", "DCB-Spine02", "Ethernet1", "10.1.2.2/31"),
        ("DCB-Spine01", "Ethernet2", "DCB-Leaf01", "Ethernet1", "10.1.2.4/31"),
        ("DCB-Spine01", "Ethernet3", "DCB-Leaf02", "Ethernet1", "10.1.2.6/31"),
        ("DCB-Spine01", "Ethernet4", "DCB-Leaf03", "Ethernet1", "10.1.2.8/31"),
        ("DCB-Spine02", "Ethernet2", "DCB-Leaf01", "Ethernet2", "10.1.2.10/31"),
        ("DCB-Spine02", "Ethernet3", "DCB-Leaf02", "Ethernet2", "10.1.2.12/31"),
        ("DCB-Spine02", "Ethernet4", "DCB-Leaf03", "Ethernet2", "10.1.2.14/31"),
    ]

    dc_c_links = [
        ("CE3", "GigabitEthernet3", "DCC-Spine01", "Ethernet1", "10.1.3.0/31"),
        ("CE3", "GigabitEthernet4", "DCC-Spine02", "Ethernet1", "10.1.3.2/31"),
        ("DCC-Spine01", "Ethernet2", "DCC-Leaf01", "Ethernet1", "10.1.3.4/31"),
        ("DCC-Spine01", "Ethernet3", "DCC-Leaf02", "Ethernet1", "10.1.3.6/31"),
        ("DCC-Spine01", "Ethernet4", "DCC-Leaf03", "Ethernet1", "10.1.3.8/31"),
        ("DCC-Spine02", "Ethernet2", "DCC-Leaf01", "Ethernet2", "10.1.3.10/31"),
        ("DCC-Spine02", "Ethernet3", "DCC-Leaf02", "Ethernet2", "10.1.3.12/31"),
        ("DCC-Spine02", "Ethernet4", "DCC-Leaf03", "Ethernet2", "10.1.3.14/31"),
    ]

    # VRFs
    vrfs = [
        {"name": "MGMT-VRF", "rd": "65000:999"},
        {"name": "CUST-A", "rd": "65000:1"},
        {"name": "CUST-B", "rd": "65000:2"},
        {"name": "CUST-C", "rd": "65000:3"},
    ]
