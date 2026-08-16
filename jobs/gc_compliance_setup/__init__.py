"""Golden Config Compliance Setup — Nautobot Job for compliance features and rules.

Creates a production-grade set of compliance features and rules covering the full
intended configuration for both Cisco IOS-XE (SP core) and Arista EOS (DC fabric).

One feature per configurable section — granular visibility into exactly which
feature is drifting on which device:

  Both platforms: hostname, vrfs, interfaces, bgp, aaa, acl, ntp, snmp, logging,
                  prefix_lists, route_maps, static_routes
  Cisco only:     isis, mpls, vty
  Arista only:    routing_global, platform, vlans, vxlan, bfd

Trade-off: Compliance rules are platform-scoped (not role-scoped), so devices
get checked against features that may not apply to them (e.g., CE routers checked
for isis/mpls, spines checked for vxlan/vlans). When both intended and backup are
empty for a feature, it shows as "compliant" — harmless noise, and the granular
visibility into actual drift is worth it.

Idempotent — safe to re-run as templates evolve.
"""

from nautobot.apps.jobs import register_jobs, Job
from nautobot.dcim.models import Platform

from nautobot_golden_config.models import ComplianceFeature, ComplianceRule


# ─── Feature Definitions ───────────────────────────────────────────────────────
# Each feature = one independently-audited config section

# ComplianceFeature is ordered by slug. These prefixes also control the order
# used when Generate Config Plans joins multiple selected features.
FEATURES = [
    {"name": "hostname", "slug": "010-hostname", "description": "Device hostname configuration"},
    {"name": "platform", "slug": "020-platform", "description": "Platform-level settings (STP mode, service model, VLAN ranges)"},
    {"name": "aaa", "slug": "030-aaa", "description": "AAA and TACACS+ authentication configuration"},
    {"name": "vrfs", "slug": "040-vrfs", "description": "VRF definitions (IOS-XE) and VRF instances (EOS)"},
    {"name": "vlans", "slug": "050-vlans", "description": "VLAN definitions"},
    {"name": "interfaces", "slug": "060-interfaces", "description": "Interface configuration (IPs, descriptions, shutdown state)"},
    {"name": "routing_global", "slug": "070-routing-global", "description": "Global routing enables (ip routing, ipv6 unicast-routing)"},
    {"name": "isis", "slug": "080-isis", "description": "IS-IS routing protocol (SP core IGP)"},
    {"name": "mpls", "slug": "090-mpls", "description": "MPLS LDP configuration (label distribution)"},
    {"name": "prefix_lists", "slug": "100-prefix-lists", "description": "IP prefix-list definitions for route filtering"},
    {"name": "route_maps", "slug": "110-route-maps", "description": "Route-map definitions for BGP policy"},
    {"name": "bfd", "slug": "120-bfd", "description": "Bidirectional Forwarding Detection timers"},
    {"name": "bgp", "slug": "130-bgp", "description": "BGP routing protocol"},
    {"name": "static_routes", "slug": "140-static-routes", "description": "Static and default route configuration"},
    {"name": "vxlan", "slug": "150-vxlan", "description": "VXLAN VTEP interface, VNI-to-VLAN/VRF mappings"},
    {"name": "acl", "slug": "160-acl", "description": "Access control lists"},
    {"name": "ntp", "slug": "170-ntp", "description": "NTP time synchronization"},
    {"name": "snmp", "slug": "180-snmp", "description": "SNMP monitoring configuration"},
    {"name": "logging", "slug": "190-logging", "description": "Syslog and logging configuration"},
    {"name": "vty", "slug": "200-vty", "description": "VTY line configuration (SSH access, exec timeout, transport)"},
]

# ─── Rule Definitions ──────────────────────────────────────────────────────────
# Each rule = feature + platform + match_config pattern
#
# match_config: newline-separated patterns matching top-level config parents
# config_ordered: True = line order matters for compliance
#
# Every configurable feature gets its own rule per platform. This gives granular
# visibility into which exact feature is drifting. Features that don't apply to
# a device role (e.g., isis on a CE) will show "compliant" (empty both sides).

RULES = [
    # ═══ Cisco IOS-XE (platform name: cisco_iosxe) ═══
    {"feature": "hostname", "platform": "cisco_iosxe", "match_config": "hostname", "ordered": False},
    {"feature": "vrfs", "platform": "cisco_iosxe", "match_config": "vrf definition", "ordered": False},
    {"feature": "interfaces", "platform": "cisco_iosxe", "match_config": "interface ", "ordered": True},
    {"feature": "isis", "platform": "cisco_iosxe", "match_config": "router isis", "ordered": True},
    {"feature": "mpls", "platform": "cisco_iosxe", "match_config": "mpls ldp", "ordered": False},
    {"feature": "bgp", "platform": "cisco_iosxe", "match_config": "router bgp", "ordered": True},
    {"feature": "aaa", "platform": "cisco_iosxe", "match_config": "aaa \ntacacs-server\ntacacs server", "ordered": True},
    {"feature": "vty", "platform": "cisco_iosxe", "match_config": "line vty", "ordered": True},
    {"feature": "acl", "platform": "cisco_iosxe", "match_config": "ip access-list\naccess-list", "ordered": True},
    {"feature": "ntp", "platform": "cisco_iosxe", "match_config": "ntp", "ordered": False},
    {"feature": "snmp", "platform": "cisco_iosxe", "match_config": "snmp-server", "ordered": False},
    {"feature": "logging", "platform": "cisco_iosxe", "match_config": "logging", "ordered": False},
    {"feature": "prefix_lists", "platform": "cisco_iosxe", "match_config": "ip prefix-list", "ordered": True},
    {"feature": "route_maps", "platform": "cisco_iosxe", "match_config": "route-map", "ordered": True},
    {"feature": "static_routes", "platform": "cisco_iosxe", "match_config": "ip route", "ordered": False},
    # IPv4 routing is default-on and hidden in IOS-XE running-config, so only
    # the IPv6 enable is audited here.
    {"feature": "routing_global", "platform": "cisco_iosxe", "match_config": "ipv6 unicast-routing", "ordered": False},
    # ═══ Arista EOS (platform name: arista_eos) ═══
    {"feature": "hostname", "platform": "arista_eos", "match_config": "hostname", "ordered": False},
    {"feature": "vrfs", "platform": "arista_eos", "match_config": "vrf instance", "ordered": False},
    {"feature": "interfaces", "platform": "arista_eos", "match_config": "interface ", "ordered": True},
    {"feature": "bgp", "platform": "arista_eos", "match_config": "router bgp", "ordered": True},
    {"feature": "routing_global", "platform": "arista_eos", "match_config": "ip routing\nipv6 unicast-routing", "ordered": False},
    {"feature": "platform", "platform": "arista_eos", "match_config": "service routing protocols model\nspanning-tree\nvlan internal order", "ordered": False},
    {"feature": "vlans", "platform": "arista_eos", "match_config": "vlan ", "ordered": False},
    {"feature": "vxlan", "platform": "arista_eos", "match_config": "interface Vxlan\nip virtual-router", "ordered": False},
    {"feature": "bfd", "platform": "arista_eos", "match_config": "router bfd", "ordered": False},
    {"feature": "aaa", "platform": "arista_eos", "match_config": "aaa \ntacacs-server", "ordered": True},
    {"feature": "acl", "platform": "arista_eos", "match_config": "ip access-list", "ordered": True},
    {"feature": "ntp", "platform": "arista_eos", "match_config": "ntp", "ordered": False},
    {"feature": "snmp", "platform": "arista_eos", "match_config": "snmp-server", "ordered": False},
    {"feature": "logging", "platform": "arista_eos", "match_config": "logging", "ordered": False},
    {"feature": "prefix_lists", "platform": "arista_eos", "match_config": "ip prefix-list", "ordered": True},
    {"feature": "route_maps", "platform": "arista_eos", "match_config": "route-map", "ordered": True},
    {"feature": "static_routes", "platform": "arista_eos", "match_config": "ip route", "ordered": False},
]


class GCComplianceSetup(Job):
    """Bootstrap Golden Config compliance features and rules for SP core + DC fabric.

    Idempotent: creates features/rules if missing, updates match_config if changed.
    Covers the full intended config for both Cisco IOS-XE and Arista EOS platforms.
    """

    class Meta:
        name = "Golden Config - Compliance Rules Setup"
        description = (
            "Creates compliance features and rules covering the full intended "
            "configuration for Cisco IOS-XE (SP core) and Arista EOS (DC fabric). "
            "Idempotent — safe to re-run as templates evolve."
        )
        has_sensitive_variables = False

    def run(self, *args, **kwargs):
        """Create or update all compliance features and rules."""
        # ── Step 1: Features ──
        features_created = 0
        features_updated = 0

        for feat_def in FEATURES:
            feature, created = ComplianceFeature.objects.get_or_create(
                name=feat_def["name"],
                defaults={
                    "description": feat_def["description"],
                    "slug": feat_def["slug"],
                },
            )
            if created:
                features_created += 1
                self.logger.info(f"Created compliance feature: {feat_def['name']}")
            else:
                changed = False
                if feature.description != feat_def["description"]:
                    feature.description = feat_def["description"]
                    changed = True
                if feature.slug != feat_def["slug"]:
                    feature.slug = feat_def["slug"]
                    changed = True
                if changed:
                    feature.validated_save()
                    features_updated += 1
                    self.logger.info(f"Updated compliance feature: {feat_def['name']}")

        self.logger.info(
            f"Features: {features_created} created, {features_updated} updated, "
            f"{len(FEATURES) - features_created - features_updated} unchanged"
        )

        # ── Step 2: Rules ──
        rules_created = 0
        rules_updated = 0
        errors = []

        for rule_def in RULES:
            try:
                feature = ComplianceFeature.objects.get(name=rule_def["feature"])
                platform = Platform.objects.get(name=rule_def["platform"])
            except ComplianceFeature.DoesNotExist:
                errors.append(f"Feature not found: {rule_def['feature']}")
                continue
            except Platform.DoesNotExist:
                errors.append(f"Platform not found: {rule_def['platform']}")
                continue

            rule, created = ComplianceRule.objects.get_or_create(
                feature=feature,
                platform=platform,
                defaults={
                    "match_config": rule_def["match_config"],
                    "config_ordered": rule_def["ordered"],
                    "config_type": "cli",
                },
            )

            if created:
                rules_created += 1
                self.logger.info(
                    f"Created rule: {rule_def['platform']} - {rule_def['feature']}"
                )
            else:
                changed = False
                if rule.match_config != rule_def["match_config"]:
                    rule.match_config = rule_def["match_config"]
                    changed = True
                if rule.config_ordered != rule_def["ordered"]:
                    rule.config_ordered = rule_def["ordered"]
                    changed = True
                if changed:
                    rule.validated_save()
                    rules_updated += 1
                    self.logger.info(
                        f"Updated rule: {rule_def['platform']} - {rule_def['feature']}"
                    )

        self.logger.info(
            f"Rules: {rules_created} created, {rules_updated} updated, "
            f"{len(RULES) - rules_created - rules_updated} unchanged"
        )

        if errors:
            for err in errors:
                self.logger.error(err)

        self.logger.info(
            f"Compliance setup complete: {len(FEATURES)} features, {len(RULES)} rules"
        )


name = "Golden Config Compliance"
register_jobs(GCComplianceSetup)
