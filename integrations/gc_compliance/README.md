# Comparison-only compliance normalization

Sync this Git repository before adding `nautobot_config_fragment.py` at the end of the Nautobot configuration. The path is the verified local repository object path in this lab. Activate on web and worker processes together; do not run jobs during the restart. Run Compliance Rules Setup after activation, then compliance.

The callback strips only IOS interface `no shutdown` and VTY `length 0` from temporary comparison copies. Raw backup/intended fields stay unchanged. Explicit `shutdown`, absent interfaces, ACL order and VTY security lines remain significant. Device admin-state validation is still required before remediation.

Rollback: restore these three rules to custom_compliance=False, remove the fragment, restart processes and rerun compliance. No device configuration changes are needed. The server_bonds_non_dns feature excludes DNS Ethernet7 and Port-Channel7. Never use the whole interfaces feature to deploy DNS-excluded changes.
