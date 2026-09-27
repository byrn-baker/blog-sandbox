# Comparison-only compliance normalization

Sync this Git repository before adding `nautobot_config_fragment.py` at the end of the Nautobot configuration. The fragment embeds the comparison callback because Git checkouts are worker-local, not shared with the web container. It is generated from `netclaw_compliance.py`; keep them identical. Activate on web and worker processes together; do not run jobs during the restart. Run Compliance Rules Setup after activation, then compliance.

The callback strips only IOS interface `no shutdown` and VTY `length 0` from temporary comparison copies. Raw backup/intended fields stay unchanged. Explicit `shutdown`, absent interfaces, ACL order and VTY security lines remain significant. Device admin-state validation is still required before remediation.

Rollback: restore these three rules to custom_compliance=False, remove the fragment, restart processes and rerun compliance. No device configuration changes are needed. The server_bonds_non_dns feature excludes DNS Ethernet7 and Port-Channel7. Never use the whole interfaces feature to deploy DNS-excluded changes.

Batfish grammar limitation: exact `neighbor EVPN-OVERLAY-PEERS transport pmtud` is accepted by EOS and was observed live on DCA-Spine02, DCB-Spine01/02 and DCC-Spine01/02 on 2026-09-26. Both mock and intended warning suites allow this exact EOS line only; Batfish cannot validate its runtime transport behavior. Hostname-map negative tests prevent rendering it on other devices.

Interface, IS-IS and BGP attribute blocks are compared without requiring serialization order. ACL and route-policy rules retain ordered comparison. IOS SNMP is rendered before NAT so the two named ACL blocks follow IOS alphabetical serialization without ignoring the ordering of ACL entries.
