"""
Render golden config templates against mock SoT contexts and validate the output.

This catches:
- Undefined variables (StrictUndefined blows up if template uses a var not in context)
- Unrendered Jinja syntax leaking into output ({{ or {%)
- Templates that produce empty output (usually a logic error)
- Whitespace-only renders (template runs but produces nothing useful)

Run with: pytest tests/test_template_render.py -v
"""

from pathlib import Path

import jinja2
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "golden-config" / "templates"
MOCK_DIR = Path(__file__).resolve().parent / "mock_contexts"

# Map platform network_driver to the top-level entry template.
PLATFORM_TEMPLATES = {
    "cisco_ios": "cisco_ios.j2",
    "arista_eos": "arista_eos.j2",
}

# Each tuple: (mock context filename, platform network_driver)
DEVICE_SCENARIOS = [
    ("cisco_ios_route_reflector.yaml", "cisco_ios"),
    ("cisco_ios_pe_router.yaml", "cisco_ios"),
    ("cisco_ios_ce_router.yaml", "cisco_ios"),
    ("cisco_ios_p_router.yaml", "cisco_ios"),
    ("cisco_ios_border_router.yaml", "cisco_ios"),
    ("arista_eos_leaf.yaml", "arista_eos"),
    ("arista_eos_spine.yaml", "arista_eos"),
    ("arista_eos_gro.yaml", "arista_eos"),
]


def load_context(filename: str) -> dict:
    """Load a mock context YAML file and return the top-level dict."""
    path = MOCK_DIR / filename
    with open(path) as f:
        return yaml.safe_load(f)


def build_jinja_env() -> jinja2.Environment:
    """
    Build a Jinja2 environment that mirrors what Nautobot golden config uses.

    Key settings:
    - StrictUndefined: fail on any variable the template references but the
      context doesn't provide. This is the main thing we're testing.
    - The loader uses the repo root so that {% include %} paths resolve the
      same way they do inside Nautobot (relative to the git repo root).
    """
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(REPO_ROOT)),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )


@pytest.mark.parametrize("context_file,platform", DEVICE_SCENARIOS)
def test_template_renders_without_error(context_file: str, platform: str):
    """Each template must render without raising on undefined variables."""
    env = build_jinja_env()
    template_path = f"golden-config/templates/{PLATFORM_TEMPLATES[platform]}"
    template = env.get_template(template_path)

    context = load_context(context_file)
    rendered = template.render(**context)

    # The output must contain actual config lines
    assert len(rendered.strip()) > 50, (
        f"Rendered output for {context_file} is suspiciously short "
        f"({len(rendered.strip())} chars). Template may not be producing config."
    )


@pytest.mark.parametrize("context_file,platform", DEVICE_SCENARIOS)
def test_no_unrendered_jinja_syntax(context_file: str, platform: str):
    """No raw {{ or {% should leak into rendered output."""
    env = build_jinja_env()
    template_path = f"golden-config/templates/{PLATFORM_TEMPLATES[platform]}"
    template = env.get_template(template_path)

    context = load_context(context_file)
    rendered = template.render(**context)

    # Filter out the {{ '\n' }} pattern which is intentional in the main templates.
    # We only care about actual unrendered variable/block tags in the output.
    assert "{{" not in rendered, (
        f"Unrendered variable tag found in output for {context_file}"
    )
    assert "{%" not in rendered, (
        f"Unrendered block tag found in output for {context_file}"
    )


@pytest.mark.parametrize("context_file,platform", DEVICE_SCENARIOS)
def test_no_python_none_in_output(context_file: str, platform: str):
    """Python 'None' should never appear in rendered network config."""
    env = build_jinja_env()
    template_path = f"golden-config/templates/{PLATFORM_TEMPLATES[platform]}"
    template = env.get_template(template_path)

    context = load_context(context_file)
    rendered = template.render(**context)

    # "None" as a standalone word in config is almost always a Jinja rendering
    # bug where a null/None value wasn't handled with a | default() filter.
    for i, line in enumerate(rendered.splitlines(), 1):
        # Skip comments and descriptions that might legitimately contain "None"
        stripped = line.strip()
        if stripped.startswith("!") or stripped.startswith("#"):
            continue
        if "description" in stripped.lower():
            continue
        assert " None" not in line and line.strip() != "None", (
            f"Python 'None' found on line {i} of rendered output for "
            f"{context_file}: {line!r}"
        )


@pytest.mark.parametrize("context_file,platform", DEVICE_SCENARIOS)
def test_hostname_present(context_file: str, platform: str):
    """Every rendered config must start with a hostname statement."""
    env = build_jinja_env()
    template_path = f"golden-config/templates/{PLATFORM_TEMPLATES[platform]}"
    template = env.get_template(template_path)

    context = load_context(context_file)
    rendered = template.render(**context)

    first_meaningful_line = ""
    for line in rendered.splitlines():
        if line.strip():
            first_meaningful_line = line.strip()
            break

    expected_hostname = context["hostname"]
    assert first_meaningful_line == f"hostname {expected_hostname}", (
        f"Expected 'hostname {expected_hostname}' as first config line, "
        f"got: {first_meaningful_line!r}"
    )


@pytest.mark.parametrize("key,value", [
    ("device", "DCB-Leaf01"), ("gro", "off; reboot"),
    ("interfaces", []), ("interfaces", [True]), ("interfaces", [0]),
    ("interfaces", [65]), ("interfaces", ["1; reboot"]),
    ("interfaces", [64]),
])
def test_gro_rejects_unsafe_or_unmodeled_scope(key, value):
    context = load_context("arista_eos_gro.yaml")
    context["config_context"]["lab_gro_workaround"][key] = value
    with pytest.raises(jinja2.UndefinedError):
        build_jinja_env().get_template("golden-config/templates/arista_eos.j2").render(**context)


def test_gro_only_adds_handlers_and_can_restore_on():
    import re
    context = load_context("arista_eos_gro.yaml")
    template = build_jinja_env().get_template("golden-config/templates/arista_eos.j2")
    rendered = template.render(**context)
    assert rendered.count("event-handler lab-gro-off-vmnicet") == 2
    assert "ethtool -K vmnicet1 gro off" in rendered
    context["config_context"]["lab_gro_workaround"]["gro"] = "on"
    assert "ethtool -K vmnicet1 gro on" in template.render(**context)
    del context["config_context"]["lab_gro_workaround"]
    assert re.sub(r"event-handler lab-gro-off-vmnicet\d+\n(?:   .*\n)+!\n", "", rendered) == template.render(**context)


@pytest.mark.parametrize("context_file,expected_vrf", [
    ("arista_eos_leaf.yaml", "MGMT-VRF"),
    ("arista_eos_spine.yaml", "MGMT-VRF"),
    ("arista_eos_gro.yaml", "MGMT-VRF"),
])
def test_eos_snmp_binds_agent_to_management_vrf(context_file: str, expected_vrf: str):
    """SNMP polling reaches the device over the Management interface's VRF.

    Without `snmp-server vrf <name>`, the agent only listens in the default
    VRF and never sees requests arriving via Management1/MGMT-VRF.
    """
    context = load_context(context_file)
    template = build_jinja_env().get_template("golden-config/templates/arista_eos.j2")
    rendered = template.render(**context)

    assert f"snmp-server vrf {expected_vrf}" in rendered
    # Community line must still be present and unaffected by the VRF line.
    ro_community = context["config_context"]["snmp"]["ro_community"]
    assert f"snmp-server community {ro_community} ro ACL-SNMP-RO" in rendered
    # Exactly one binding, not one per Management interface or per render pass.
    assert rendered.count(f"snmp-server vrf {expected_vrf}") == 1


def test_eos_snmp_vrf_line_is_deduplicated_across_management_interfaces():
    """Two Management interfaces sharing a VRF emit one `snmp-server vrf` line."""
    context = load_context("arista_eos_leaf.yaml")
    management1 = next(i for i in context["interfaces"] if i["name"] == "Management1")
    context["interfaces"].append({**management1, "name": "Management2"})
    template = build_jinja_env().get_template("golden-config/templates/arista_eos.j2")
    rendered = template.render(**context)
    assert rendered.count("snmp-server vrf MGMT-VRF") == 1


def test_eos_snmp_omits_vrf_line_when_management_has_no_vrf():
    """A Management interface modeled without a VRF must not render a bare `snmp-server vrf`."""
    context = load_context("arista_eos_leaf.yaml")
    for interface in context["interfaces"]:
        if interface["name"] == "Management1":
            interface["vrf"] = None
    template = build_jinja_env().get_template("golden-config/templates/arista_eos.j2")
    rendered = template.render(**context)
    assert "snmp-server vrf" not in rendered


def test_ios_snmp_template_has_no_vrf_line():
    """IOS SNMP stays scoped to community/ACL/location/contact - no VRF binding added."""
    context = load_context("cisco_ios_ce_router.yaml")
    template = build_jinja_env().get_template("golden-config/templates/cisco_ios.j2")
    rendered = template.render(**context)
    assert "snmp-server vrf" not in rendered
