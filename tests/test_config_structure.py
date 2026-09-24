"""
Structural validation of rendered configs against vendor CLI rules.

These tests catch issues that are syntactically valid Jinja output but
operationally invalid on the target device. Examples:
- Duplicate address-family blocks (IOS-XE treats re-entry as no-op)
- ip address virtual before ip virtual-router mac-address (EOS rejects)
- send-community on peer-group members instead of the group (IOS-XE rejects)
- Policy commands outside address-family context (IOS-XE rejects)

Run with: pytest tests/test_config_structure.py -v
"""

import ast
import re
from pathlib import Path

import jinja2
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MOCK_DIR = Path(__file__).resolve().parent / "mock_contexts"

PLATFORM_TEMPLATES = {
    "cisco_ios": "golden-config/templates/cisco_ios.j2",
    "arista_eos": "golden-config/templates/arista_eos.j2",
}

IOS_SCENARIOS = [
    ("cisco_ios_route_reflector.yaml", "cisco_ios"),
    ("cisco_ios_pe_router.yaml", "cisco_ios"),
    ("cisco_ios_ce_router.yaml", "cisco_ios"),
    ("cisco_ios_p_router.yaml", "cisco_ios"),
    ("cisco_ios_border_router.yaml", "cisco_ios"),
]

EOS_SCENARIOS = [
    ("arista_eos_leaf.yaml", "arista_eos"),
    ("arista_eos_spine.yaml", "arista_eos"),
]

ALL_SCENARIOS = IOS_SCENARIOS + EOS_SCENARIOS


def render(context_file: str, platform: str) -> str:
    """Render a template with a mock context and return the output."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(REPO_ROOT)),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )
    with open(MOCK_DIR / context_file) as f:
        context = yaml.safe_load(f)
    template = env.get_template(PLATFORM_TEMPLATES[platform])
    return template.render(**context)


# ---------------------------------------------------------------------------
# IOS-XE structural rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("context_file,platform", IOS_SCENARIOS)
def test_ios_no_duplicate_address_family_ipv4(context_file, platform):
    """IOS-XE: address-family ipv4 must appear at most once per router bgp."""
    rendered = render(context_file, platform)

    # Extract each router bgp block
    bgp_blocks = re.findall(
        r"^router bgp \d+\n((?:[ !].*\n)*)", rendered, re.MULTILINE
    )
    for block in bgp_blocks:
        # Count non-VRF address-family ipv4 entries (exclude "address-family ipv4 vrf")
        af_ipv4_count = len(
            re.findall(r"^ address-family ipv4\s*$", block, re.MULTILINE)
        )
        assert af_ipv4_count <= 1, (
            f"{context_file}: Found {af_ipv4_count} 'address-family ipv4' blocks "
            f"in router bgp. IOS-XE requires a single block with all neighbors."
        )


@pytest.mark.parametrize("context_file,platform", IOS_SCENARIOS)
def test_ios_no_per_neighbor_policy_for_peergroup_members(context_file, platform):
    """IOS-XE: peer-group members must not get per-neighbor send-community."""
    rendered = render(context_file, platform)

    # Find all peer-group member assignments
    pg_members = set()
    for match in re.finditer(
        r"^ neighbor ([\d.]+) peer-group (\S+)", rendered, re.MULTILINE
    ):
        pg_members.add(match.group(1))

    # Check that no peer-group member gets per-neighbor send-community
    for match in re.finditer(
        r"^ +neighbor ([\d.]+) send-community", rendered, re.MULTILINE
    ):
        neighbor_ip = match.group(1)
        assert neighbor_ip not in pg_members, (
            f"{context_file}: neighbor {neighbor_ip} is a peer-group member "
            f"but has per-neighbor 'send-community'. Must be set on the group."
        )


@pytest.mark.parametrize("context_file,platform", IOS_SCENARIOS)
def test_ios_no_per_neighbor_rr_client_for_peergroup_members(context_file, platform):
    """IOS-XE: peer-group members must not get per-neighbor route-reflector-client."""
    rendered = render(context_file, platform)

    pg_members = set()
    for match in re.finditer(
        r"^ neighbor ([\d.]+) peer-group (\S+)", rendered, re.MULTILINE
    ):
        pg_members.add(match.group(1))

    for match in re.finditer(
        r"^ +neighbor ([\d.]+) route-reflector-client", rendered, re.MULTILINE
    ):
        neighbor_ip = match.group(1)
        assert neighbor_ip not in pg_members, (
            f"{context_file}: neighbor {neighbor_ip} is a peer-group member "
            f"but has per-neighbor 'route-reflector-client'. Must be set on the group."
        )


@pytest.mark.parametrize("context_file,platform", IOS_SCENARIOS)
def test_ios_send_community_inside_address_family(context_file, platform):
    """IOS-XE: send-community for vpnv4/vpnv6 peer-groups must be inside AF."""
    rendered = render(context_file, platform)
    lines = rendered.splitlines()

    in_af = False
    in_router_bgp = False

    for line in lines:
        if line.startswith("router bgp"):
            in_router_bgp = True
            continue
        if in_router_bgp and not line.startswith(" ") and not line.startswith("!"):
            in_router_bgp = False
            continue
        if not in_router_bgp:
            continue

        if "address-family" in line:
            in_af = True
            continue
        if "exit-address-family" in line:
            in_af = False
            continue

        # send-community on a peer-group (not IP) outside AF is invalid for vpn AFs
        match = re.match(r"^ neighbor ([A-Z][\w-]*) send-community", line)
        if match and not in_af:
            pytest.fail(
                f"{context_file}: 'neighbor {match.group(1)} send-community' "
                f"found outside address-family context. IOS-XE rejects this for "
                f"vpnv4/vpnv6 peer-groups."
            )


# ---------------------------------------------------------------------------
# Arista EOS structural rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("context_file,platform", EOS_SCENARIOS)
def test_eos_virtual_router_mac_before_virtual_ip(context_file, platform):
    """EOS: ip virtual-router mac-address must precede ip address virtual."""
    rendered = render(context_file, platform)
    lines = rendered.splitlines()

    mac_line = None
    first_virtual_ip_line = None

    for i, line in enumerate(lines):
        if "ip virtual-router mac-address" in line and mac_line is None:
            mac_line = i
        if "ip address virtual" in line and first_virtual_ip_line is None:
            first_virtual_ip_line = i

    if first_virtual_ip_line is not None:
        assert mac_line is not None, (
            f"{context_file}: 'ip address virtual' found but no "
            f"'ip virtual-router mac-address' anywhere in config."
        )
        assert mac_line < first_virtual_ip_line, (
            f"{context_file}: 'ip virtual-router mac-address' (line {mac_line}) "
            f"must come before 'ip address virtual' (line {first_virtual_ip_line}). "
            f"EOS rejects virtual IPs without the MAC configured first."
        )


@pytest.mark.parametrize("context_file,platform", EOS_SCENARIOS)
def test_eos_no_duplicate_interface_vxlan1(context_file, platform):
    """EOS: interface Vxlan1 should only appear once in the config."""
    rendered = render(context_file, platform)
    vxlan_count = len(re.findall(r"^interface Vxlan1\s*$", rendered, re.MULTILINE))
    # Leafs have Vxlan1, spines don't. But never more than one.
    assert vxlan_count <= 1, (
        f"{context_file}: 'interface Vxlan1' appears {vxlan_count} times. "
        f"Should be at most once."
    )


@pytest.mark.parametrize("context_file,platform", IOS_SCENARIOS)
def test_ios_peergroup_activate_requires_members(context_file, platform):
    """IOS-XE: activating a peer-group in an AF requires at least one member."""
    rendered = render(context_file, platform)

    # Find all peer-group member assignments (neighbor <ip> peer-group <name>)
    pg_with_members = set()
    for match in re.finditer(
        r"^ neighbor [\d.]+ peer-group (\S+)", rendered, re.MULTILINE
    ):
        pg_with_members.add(match.group(1))

    # Find all peer-group activations inside address-families
    # Pattern: "neighbor <PG-NAME> activate" where PG-NAME starts with a letter
    for match in re.finditer(
        r"^ +neighbor ([A-Z][\w-]*) activate", rendered, re.MULTILINE
    ):
        pg_name = match.group(1)
        assert pg_name in pg_with_members, (
            f"{context_file}: 'neighbor {pg_name} activate' in address-family "
            f"but no peers assigned to this group with "
            f"'neighbor <ip> peer-group {pg_name}'. IOS-XE rejects activating "
            f"a peer-group with no members."
        )


@pytest.mark.parametrize("context_file,platform", IOS_SCENARIOS)
def test_ios_restores_enabled_ports_and_scopes_jumbo_mtu(context_file, platform):
    """A wiped router needs enabled ports brought up without changing management MTU."""
    context = yaml.safe_load((MOCK_DIR / context_file).read_text())
    rendered = render(context_file, platform)
    blocks = {m.group(1): m.group(2) for m in re.finditer(
        r"^interface (\S+)\n(.*?)(?=^!|\Z)", rendered, re.M | re.S
    )}
    for interface in context["interfaces"]:
        block = blocks.get(interface["name"])
        if block is None:
            continue
        assert ("\n no shutdown\n" in "\n" + block) == interface["enabled"]
        if interface["name"].startswith("GigabitEthernet"):
            management = interface.get("mgmt_only") or (interface.get("vrf") or {}).get("name") == "MGMT-VRF"
            outside = (interface.get("role") or {}).get("name") == "NAT Outside"
            assert (" mtu 9216\n" in block) == (not management and not outside)



def test_config_plan_declares_routing_before_interfaces():
    """Plan feature order must preserve IOS routing prerequisites after a wipe."""
    tree = ast.parse((REPO_ROOT / "jobs/gc_compliance_setup/__init__.py").read_text())
    features = next(ast.literal_eval(node.value) for node in tree.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "FEATURES"
                            for target in node.targets))
    order = [feature["name"] for feature in sorted(features, key=lambda f: f["slug"])]
    assert order.index("routing_global") < order.index("loopback_prerequisite") < order.index("isis") < order.index("interfaces")
    for context_file, platform in IOS_SCENARIOS:
        output = render(context_file, platform)
        assert output.index("ipv6 unicast-routing") < output.index("\ninterface GigabitEthernet")
        if "router isis SP-ISIS" in output:
            assert output.index("ipv6 unicast-routing") < output.index("interface Loopback0")
            assert output.index("interface Loopback0") < output.index("router isis SP-ISIS") < output.index("\ninterface GigabitEthernet")
            assert len(re.findall(r"^interface Loopback0$", output, re.M)) == 1


def test_ios_deployment_detects_isis_prerequisite_failure():
    context = yaml.safe_load((REPO_ROOT / "config_contexts/platform_cisco_iosxe.yaml").read_text())
    pattern = context["netmiko_kwargs"]["error_pattern"]
    assert re.search(pattern, "%ISIS: IPv6 unicast routing not enabled", re.M)
    assert re.search(pattern, "% Invalid input detected at '^' marker.", re.M)
    assert not re.search(pattern, "%ISIS-5-ADJCHANGE: Adjacency changed", re.M)


def test_loopback_prerequisite_is_in_config_plans():
    """The live SPE1 rejection requires a plan feature, not just render order."""
    tree = ast.parse((REPO_ROOT / "jobs/gc_compliance_setup/__init__.py").read_text())
    rules = next(ast.literal_eval(node.value) for node in tree.body
                 if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "RULES"
                         for target in node.targets))
    rule = next(rule for rule in rules if rule["feature"] == "loopback_prerequisite")
    assert rule["platform"] == "cisco_iosxe"
    assert rule["match_config"] == "interface Loopback0"


@pytest.mark.parametrize("context_file,platform", EOS_SCENARIOS)
def test_standard_eos_mtu_scopes(context_file, platform):
    """Transport and service packets have distinct budgets; management is excluded."""
    config = render(context_file, platform)
    context = yaml.safe_load((MOCK_DIR / context_file).read_text())
    for interface in context["interfaces"]:
        name = interface["name"]
        match = re.search(r"^interface " + re.escape(name) + r"\n(.*?)(?=^interface |\Z)", config, re.M | re.S)
        if not match:
            continue
        block = match.group(1).split("\n!", 1)[0]
        if name.startswith("Ethernet") and interface["ip_addresses"]:
            assert "   mtu 9214\n" in block + "\n"
        elif name.startswith("Vlan") and interface["ip_addresses"]:
            assert "   mtu 9000\n" in block + "\n"
        else:
            assert not re.search(r"^ +mtu ", block, re.M)


def test_standard_mtu_budget_and_exclusions():
    """Check the carrying budget and migration exclusions without importing Nautobot."""
    tree = ast.parse((REPO_ROOT / "jobs/sp_demo_lab/context/__init__.py").read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    values = {}
    for node in cls.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in {"mtu_policy", "service_vlans"}:
                values[node.targets[0].id] = ast.literal_eval(node.value)
    from types import SimpleNamespace
    context = SimpleNamespace(**values)
    job = ast.parse((REPO_ROOT / "jobs/lab_mtu/__init__.py").read_text())
    function = next(node for node in job.body if isinstance(node, ast.FunctionDef) and node.name == "target_mtu")
    scope = {"SPDemoLabContext": context}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "mtu-policy", "exec"), scope)
    target = scope["target_mtu"]
    assert target("cisco_iosxe", "GigabitEthernet1") is None
    assert target("cisco_iosxe", "GigabitEthernet4", role="NAT Outside") is None
    assert target("cisco_iosxe", "GigabitEthernet2", vrf="MGMT-VRF") is None
    assert target("arista_eos", "Management1") is None
    assert target("arista_eos", "Ethernet1", mgmt_only=True) is None
    assert target("arista_eos", "Vlan4097") is None
    assert target("cisco_iosxe", "GigabitEthernet2") == 9216
    assert target("arista_eos", "Ethernet10") == 9214
    assert target("arista_eos", "Vlan100") == 9000
    assert target("linux", "bond0", server=True) == 9000
    assert target("linux", "eth0", server=True) is None
    policy = values["mtu_policy"]
    assert policy["server"] + 50 <= policy["fabric"]
    assert policy["server"] + 50 + 8 <= policy["router"]
    assert policy["virtual_transport"] >= policy["router"]
    assert yaml.safe_load((REPO_ROOT / "ansible/group_vars/all.yml").read_text())["bond_mtu"] == policy["server"]
    eos = yaml.safe_load((REPO_ROOT / "config_contexts/platform_arista_eos.yaml").read_text())
    assert eos["fabric_transport_mtu"] == policy["fabric"]
    assert eos["server_mtu"] == policy["server"]


def test_standard_mtu_design_renders_all_devices():
    """A rebuild must preserve the MTU migration, including CE handoffs and hosts."""
    tree = ast.parse((REPO_ROOT / "jobs/sp_demo_lab/context/__init__.py").read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    values = {}
    for node in cls.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                values[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(REPO_ROOT), undefined=jinja2.StrictUndefined, trim_blocks=True, lstrip_blocks=True)
    rendered = env.get_template("jobs/sp_demo_lab/designs/0002_devices.yaml.j2").render(**values)
    devices = yaml.safe_load(rendered)["devices"]
    assert len(devices) == 38
    for device in devices:
        platform = device.get("platform__name", "")
        for interface in device["interfaces"]:
            name = interface["!create_or_update:name"]
            if platform == "arista_eos" and name.startswith("Ethernet"):
                assert interface["mtu"] == 9214
            elif platform == "arista_eos" and name.startswith("Vlan"):
                assert interface["mtu"] == 9000
            elif name in {"bond0", "ens19", "ens20"}:
                assert interface["mtu"] == 9000
            elif platform == "cisco_iosxe" and name.startswith("GigabitEthernet") and name != "GigabitEthernet1" and interface.get("role__name") != "NAT Outside":
                assert interface["mtu"] == 9216
            else:
                assert "mtu" not in interface
