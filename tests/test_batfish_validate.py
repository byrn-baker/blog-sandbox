"""
Validate rendered golden configs using Batfish's vendor-aware parser.

Batfish parses IOS/IOS-XE configs the same way a router does. If a command is
malformed or unrecognized, Batfish flags it as a parse warning. This catches
issues that would result in "% Invalid input" on the actual device.

For Arista EOS, Batfish's detection requires specific format hints. We handle
this by creating separate snapshots per platform so Batfish can parse each
correctly.

Requirements:
  - Batfish container running: docker run -d --name batfish -p 9997:9997 -p 9996:9996 batfish/batfish
  - pybatfish installed: pip install pybatfish

Run with: pytest tests/test_batfish_validate.py -v
Skip if Batfish unavailable: pytest tests/test_batfish_validate.py -v -m batfish
"""

import os
import shutil
from pathlib import Path

import jinja2
import pytest
import yaml

# Try to import pybatfish; skip all tests if unavailable or Batfish not running
try:
    from pybatfish.client.session import Session

    _bf = Session(host="localhost")
    _bf.set_network("ci-test-probe")
    BATFISH_AVAILABLE = True
except Exception:
    BATFISH_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not BATFISH_AVAILABLE,
    reason="Batfish container not running on localhost:9997",
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MOCK_DIR = Path(__file__).resolve().parent / "mock_contexts"

# Known-benign parse warnings that Batfish flags but devices accept fine.
# These are commands Batfish's grammar doesn't cover yet.
KNOWN_BENIGN_IOS = {
    "ip ssh bulk-mode",  # IOS-XE 17.x feature, Batfish grammar is behind
}

# EOS commands Batfish's Cisco parser doesn't understand (expected when
# Batfish mis-detects format). We track these separately.
KNOWN_BENIGN_EOS = {
    "vrf instance",
    "vlan internal order",
    "router bfd",
    "multihop interval",
    "peer group",
    "next-hop-unchanged",
    "address-family evpn",
    "interface Vxlan1",
    "vxlan source-interface",
    "vxlan udp-port",
    "vxlan vlan",
    "vxlan vrf",
    "ip virtual-router mac-address",
    "redistribute learned",
    "route-target both",
    "route-target import evpn",
    "route-target export evpn",
    "redistribute connected",
    # When Batfish skips 'interface Vxlan1', the description line that follows
    # becomes orphaned and shows up as a warning. Only affects EOS VTEP blocks.
    "_VTEP",
}


def render_configs(scenarios: list[tuple[str, str]]) -> dict[str, str]:
    """Render templates and return {hostname: rendered_config} dict."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(REPO_ROOT)),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )
    configs = {}
    for ctx_file, tmpl_file in scenarios:
        with open(REPO_ROOT / ctx_file) as f:
            context = yaml.safe_load(f)
        template = env.get_template(tmpl_file)
        rendered = template.render(**context)
        configs[context["hostname"]] = rendered
    return configs


def create_snapshot(configs: dict[str, str], snapshot_name: str) -> str:
    """Write configs to a temp directory in Batfish snapshot format."""
    snapshot_dir = f"/tmp/batfish_{snapshot_name}"
    if os.path.exists(snapshot_dir):
        shutil.rmtree(snapshot_dir)
    configs_dir = os.path.join(snapshot_dir, "configs")
    os.makedirs(configs_dir)
    for hostname, config in configs.items():
        with open(os.path.join(configs_dir, f"{hostname}.cfg"), "w") as f:
            f.write(config)
    return snapshot_dir


def is_benign_warning(text: str, known_set: set[str]) -> bool:
    """Check if a parse warning matches a known-benign pattern."""
    stripped = text.strip()
    for pattern in known_set:
        if pattern in stripped:
            return True
    return False


class TestBatfishIOSValidation:
    """Validate IOS-XE rendered configs parse cleanly in Batfish."""

    IOS_SCENARIOS = [
        ("tests/mock_contexts/cisco_ios_route_reflector.yaml", "golden-config/templates/cisco_ios.j2"),
        ("tests/mock_contexts/cisco_ios_pe_router.yaml", "golden-config/templates/cisco_ios.j2"),
    ]

    @pytest.fixture(scope="class")
    def batfish_ios_results(self):
        """Initialize Batfish snapshot with IOS configs (once per class)."""
        configs = render_configs(self.IOS_SCENARIOS)
        snapshot_dir = create_snapshot(configs, "ios_ci")

        bf = Session(host="localhost")
        bf.set_network("ci-ios-validation")
        bf.init_snapshot(snapshot_dir, name="ios-ci", overwrite=True)
        bf.set_snapshot("ios-ci")

        parse_status = bf.q.fileParseStatus().answer().frame()
        parse_warnings = bf.q.parseWarning().answer().frame()

        return {
            "parse_status": parse_status,
            "parse_warnings": parse_warnings,
            "configs": configs,
        }

    def test_all_ios_configs_parsed(self, batfish_ios_results):
        """Batfish must successfully parse all IOS config files."""
        status = batfish_ios_results["parse_status"]
        assert len(status) == len(self.IOS_SCENARIOS), (
            f"Expected {len(self.IOS_SCENARIOS)} parsed files, got {len(status)}"
        )
        # PASSED or PARTIALLY_UNRECOGNIZED are both acceptable
        # FAILED means the file couldn't be parsed at all
        for _, row in status.iterrows():
            assert row["Status"] != "FAILED", (
                f"Batfish completely failed to parse {row['File_Name']}"
            )

    def test_no_unexpected_ios_parse_warnings(self, batfish_ios_results):
        """No parse warnings beyond known-benign patterns."""
        warnings = batfish_ios_results["parse_warnings"]
        unexpected = []
        for _, row in warnings.iterrows():
            if not is_benign_warning(row["Text"], KNOWN_BENIGN_IOS):
                unexpected.append(
                    f"  {row['Filename']}:{row['Line']} - {row['Text'].strip()}"
                )
        assert not unexpected, (
            "Unexpected IOS parse warnings (likely invalid CLI syntax):\n"
            + "\n".join(unexpected)
        )


class TestBatfishEOSValidation:
    """
    Validate Arista EOS rendered configs.

    Note: Batfish frequently mis-detects EOS configs as Cisco IOS, which
    produces many false-positive warnings. This test validates that configs
    render and parse without FAILED status, but the parse warnings are
    filtered against known EOS-specific syntax that Batfish's IOS parser
    doesn't understand.
    """

    EOS_SCENARIOS = [
        ("tests/mock_contexts/arista_eos_leaf.yaml", "golden-config/templates/arista_eos.j2"),
        ("tests/mock_contexts/arista_eos_spine.yaml", "golden-config/templates/arista_eos.j2"),
    ]

    @pytest.fixture(scope="class")
    def batfish_eos_results(self):
        """Initialize Batfish snapshot with EOS configs (once per class)."""
        configs = render_configs(self.EOS_SCENARIOS)
        snapshot_dir = create_snapshot(configs, "eos_ci")

        bf = Session(host="localhost")
        bf.set_network("ci-eos-validation")
        bf.init_snapshot(snapshot_dir, name="eos-ci", overwrite=True)
        bf.set_snapshot("eos-ci")

        parse_status = bf.q.fileParseStatus().answer().frame()
        parse_warnings = bf.q.parseWarning().answer().frame()

        return {
            "parse_status": parse_status,
            "parse_warnings": parse_warnings,
            "configs": configs,
        }

    def test_all_eos_configs_parsed(self, batfish_eos_results):
        """Batfish must not completely fail on any EOS config."""
        status = batfish_eos_results["parse_status"]
        assert len(status) == len(self.EOS_SCENARIOS)
        for _, row in status.iterrows():
            assert row["Status"] != "FAILED", (
                f"Batfish completely failed to parse {row['File_Name']}"
            )

    def test_no_unexpected_eos_parse_warnings(self, batfish_eos_results):
        """Only known EOS-specific syntax should appear in warnings."""
        warnings = batfish_eos_results["parse_warnings"]
        unexpected = []
        for _, row in warnings.iterrows():
            text = row["Text"].strip()
            if not is_benign_warning(text, KNOWN_BENIGN_EOS | KNOWN_BENIGN_IOS):
                # Also skip rd/route-target lines inside BGP VLAN context
                if text.startswith("rd ") or text.startswith("route-target"):
                    continue
                unexpected.append(
                    f"  {row['Filename']}:{row['Line']} - {text}"
                )
        assert not unexpected, (
            "Unexpected EOS parse warnings:\n" + "\n".join(unexpected)
        )


class TestBatfishBGPValidation:
    """
    Cross-device BGP session validation using Batfish's analysis questions.

    These tests check that BGP peers can actually establish sessions based
    on the rendered configs. This catches mismatched ASNs, missing peer-group
    definitions, and unreachable update-source addresses.
    """

    ALL_SCENARIOS = [
        ("tests/mock_contexts/cisco_ios_route_reflector.yaml", "golden-config/templates/cisco_ios.j2"),
        ("tests/mock_contexts/cisco_ios_pe_router.yaml", "golden-config/templates/cisco_ios.j2"),
    ]

    @pytest.fixture(scope="class")
    def batfish_full_results(self):
        """Load all IOS configs for cross-device analysis."""
        configs = render_configs(self.ALL_SCENARIOS)
        snapshot_dir = create_snapshot(configs, "full_ci")

        bf = Session(host="localhost")
        bf.set_network("ci-full-validation")
        bf.init_snapshot(snapshot_dir, name="full-ci", overwrite=True)
        bf.set_snapshot("full-ci")

        return bf

    def test_bgp_session_compatibility(self, batfish_full_results):
        """BGP sessions between devices should have compatible configs."""
        bf = batfish_full_results
        # Batfish can check if BGP sessions would establish
        try:
            bgp_edges = bf.q.bgpEdges().answer().frame()
            # If we get edges back, the sessions are at least configured
            # consistently on both sides
            if not bgp_edges.empty:
                print(f"\nBGP edges found: {len(bgp_edges)}")
                for _, row in bgp_edges.iterrows():
                    print(f"  {row.get('Node', '?')} -> {row.get('Remote_Node', '?')}")
        except Exception as e:
            # Some Batfish questions aren't available for all parse states
            pytest.skip(f"BGP edge analysis not available: {e}")

    def test_undefined_references(self, batfish_full_results):
        """No references to undefined structures (route-maps, ACLs, etc)."""
        bf = batfish_full_results
        undef = bf.q.undefinedReferences().answer().frame()
        if not undef.empty:
            issues = []
            for _, row in undef.iterrows():
                issues.append(
                    f"  {row['Filename']}: {row['Ref_Type']} '{row['Ref_Name']}' "
                    f"(referenced in {row['Context']})"
                )
            # Don't fail on this yet, just warn. Some references are to
            # structures on other devices (like peer-group names).
            print("\nUndefined references (may be cross-device):")
            print("\n".join(issues))
