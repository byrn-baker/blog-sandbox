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
