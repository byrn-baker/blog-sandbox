# Git-owned comparison-only normalization. Load after PLUGINS_CONFIG definition.
import sys

sys.path.insert(0, "/opt/nautobot/git/blog_sandbox")
PLUGINS_CONFIG["nautobot_golden_config"]["get_custom_compliance"] = "netclaw_compliance.compliance"
