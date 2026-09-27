# Generated from netclaw_compliance.py; callback must be available in web and workers.
"""Comparison-only IOS normalization; never modifies intent or backup evidence."""
from types import SimpleNamespace


def normalize(text, feature, platform):
    """Ignore only known hidden defaults/pagination, retaining explicit shutdown."""
    if platform != "cisco_ios":
        return text
    parent = ""
    lines = []
    for line in text.splitlines():
        if line and not line[0].isspace() and line != "!":
            parent = line
        if feature in {"interfaces", "loopback_prerequisite"} and parent.startswith("interface ") and line.strip() == "no shutdown":
            continue
        if feature == "vty" and parent.startswith("line vty ") and line.strip() == "length 0":
            continue
        lines.append(line)
    return "\n".join(lines)


def compliance(obj):
    """Golden Config get_custom_compliance callback; raw fields stay untouched."""
    from nautobot_golden_config.models import _get_cli_compliance
    platform = obj.device.platform.network_driver_mappings.get("netutils_parser")
    feature = obj.rule.feature.name
    view = SimpleNamespace(
        actual=normalize(obj.actual, feature, platform),
        intended=normalize(obj.intended, feature, platform),
        rule=obj.rule, device=obj.device,
    )
    return _get_cli_compliance(view)

PLUGINS_CONFIG["nautobot_golden_config"]["get_custom_compliance"] = "nautobot_config.compliance"
