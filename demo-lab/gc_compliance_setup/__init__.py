"""Golden Config Compliance Setup — Nautobot Job for compliance features and rules.

Creates a production-grade set of compliance features and rules covering the full
intended configuration for both Cisco IOS-XE (SP core) and Arista EOS (DC fabric).

Features map 1:1 to golden config template sections:
  Cisco IOS-XE: hostname, vrfs, interfaces, isis, mpls, bgp
  Arista EOS:   hostname, platform, vrfs, vlans, interfaces, routing_global,
                prefix_lists, route_maps, bfd, bgp, vxlan

Idempotent — safe to re-run as templates evolve.
"""

from nautobot.apps.jobs import register_jobs, Job
from nautobot.dcim.models import Platform

from nautobot_golden_config.models import ComplianceFeature, ComplianceRule


# ─── Feature Definitions ───────────────────────────────────────────────────────
# Each feature = one independently-audited config section

FEATURES = [
    {"name": "hostname", "description": "Device hostname configuration"},
    {"name": "vrfs", "description": "VRF definitions (IOS-XE) and VRF instances (EOS)"},
    {"name": "interfaces", "description": "Interface configuration (IPs, descriptions, shutdown state)"},
    {"name": "isis", "description": "IS-IS routing protocol (SP core IGP)"},
    {"name": "mpls", "description": "MPLS LDP configuration (label distribution)"},
    {"name": "bgp", "description": "BGP routing (iBGP VPNv4/v6, eBGP PE-CE, DC underlay/EVPN)"},
    {"name": "platform", "description": "Platform-level settings (STP mode, service model, VLAN ranges)"},
    {"name": "routing_global", "description": "Global routing enables (ip routing, ipv6 unicast-routing)"},
    {"name": "prefix_lists", "description": "IP prefix-list definitions for route filtering"},
    {"name": "route_maps", "description": "Route-map definitions for BGP policy"},
    {"name": "bfd", "description": "Bidirectional Forwarding Detection timers"},
    {"name": "vxlan", "description": "VXLAN VTEP interface, VNI-to-VLAN/VRF mappings"},
    {"name": "vlans", "description": "VLAN definitions (EOS leaf switches)"},
]

# ─── Rule Definitions ──────────────────────────────────────────────────────────
# Each rule = feature + platform + match_config pattern
#
# match_config: newline-separated patterns matching top-level config parents
# config_ordered: True = line order matters for compliance (BGP, interfaces)

RULES = [
    # ═══ Cisco IOS-XE (platform name: cisco_iosxe) ═══
    {"feature": "hostname", "platform": "cisco_iosxe", "match_config": "hostname", "ordered": False},
    {"feature": "vrfs", "platform": "cisco_iosxe", "match_config": "vrf definition", "ordered": False},
    {"feature": "interfaces", "platform": "cisco_iosxe", "match_config": "interface ", "ordered": True},
    {"feature": "isis", "platform": "cisco_iosxe", "match_config": "router isis", "ordered": True},
    {"feature": "mpls", "platform": "cisco_iosxe", "match_config": "mpls ldp", "ordered": False},
    {"feature": "bgp", "platform": "cisco_iosxe", "match_config": "router bgp", "ordered": True},
    # ═══ Arista EOS (platform name: arista_eos) ═══
    {"feature": "hostname", "platform": "arista_eos", "match_config": "hostname", "ordered": False},
    {"feature": "platform", "platform": "arista_eos", "match_config": "service routing protocols model\nspanning-tree\nvlan internal order", "ordered": False},
    {"feature": "vrfs", "platform": "arista_eos", "match_config": "vrf instance", "ordered": False},
    {"feature": "vlans", "platform": "arista_eos", "match_config": "vlan ", "ordered": False},
    {"feature": "interfaces", "platform": "arista_eos", "match_config": "interface ", "ordered": True},
    {"feature": "routing_global", "platform": "arista_eos", "match_config": "ip routing\nipv6 unicast-routing", "ordered": False},
    {"feature": "prefix_lists", "platform": "arista_eos", "match_config": "ip prefix-list", "ordered": True},
    {"feature": "route_maps", "platform": "arista_eos", "match_config": "route-map", "ordered": True},
    {"feature": "bfd", "platform": "arista_eos", "match_config": "router bfd", "ordered": False},
    {"feature": "bgp", "platform": "arista_eos", "match_config": "router bgp", "ordered": True},
    {"feature": "vxlan", "platform": "arista_eos", "match_config": "interface Vxlan\nip virtual-router", "ordered": False},
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
                defaults={"description": feat_def["description"]},
            )
            if created:
                features_created += 1
                self.logger.info(f"Created compliance feature: {feat_def['name']}")
            else:
                if feature.description != feat_def["description"]:
                    feature.description = feat_def["description"]
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
