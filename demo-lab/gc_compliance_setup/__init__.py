"""Golden Config Compliance Setup — Nautobot Job for compliance features and rules.

Creates a production-grade set of compliance features and rules covering the full
intended configuration for both Cisco IOS-XE (SP core) and Arista EOS (DC fabric).

Features (5 total, consolidated to reduce noise):
  Both platforms: hostname, vrfs, interfaces, routing
  Arista only:    fabric_services

Design decisions:
  - Cisco "routing" combines IS-IS + MPLS LDP + BGP. CEs that only run BGP get
    one routing check instead of three (two of which would be empty noise).
  - Arista "routing" combines ip routing + ipv6 unicast-routing + BGP.
  - Arista "fabric_services" combines platform settings, VLANs, VXLAN, BFD,
    prefix-lists, and route-maps. Spines that don't run VXLAN get one record
    instead of six empty ones.
  - Rules are platform-scoped (Golden Config limitation), not role-scoped.
    Consolidating features is the documented workaround for reducing noise.

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
    {"name": "routing", "description": "All routing protocols — IS-IS, MPLS LDP, and BGP (Cisco); ip routing + BGP (Arista)"},
    {"name": "fabric_services", "description": "DC fabric overlay — platform settings, VLANs, VXLAN, BFD, prefix-lists, route-maps"},
]

# ─── Rule Definitions ──────────────────────────────────────────────────────────
# Each rule = feature + platform + match_config pattern
#
# match_config: newline-separated patterns matching top-level config parents
# config_ordered: True = line order matters for compliance (BGP, interfaces)
#
# Design decision: Compliance rules are platform-scoped, not role-scoped. Every
# device on a platform gets checked against every rule for that platform.
# To avoid noise (empty "compliant" records for features a device doesn't use),
# we consolidate related features into broader groups:
#   - Cisco: "routing" covers ISIS + MPLS + BGP together
#   - Arista: "routing" covers ip routing + BGP; "fabric_services" covers all
#     overlay features (VXLAN, BFD, VLANs, etc.) as a single check

RULES = [
    # ═══ Cisco IOS-XE (platform name: cisco_iosxe) ═══
    {"feature": "hostname", "platform": "cisco_iosxe", "match_config": "hostname", "ordered": False},
    {"feature": "vrfs", "platform": "cisco_iosxe", "match_config": "vrf definition", "ordered": False},
    {"feature": "interfaces", "platform": "cisco_iosxe", "match_config": "interface ", "ordered": True},
    {"feature": "routing", "platform": "cisco_iosxe", "match_config": "router isis\nrouter bgp\nmpls ldp", "ordered": True},
    # ═══ Arista EOS (platform name: arista_eos) ═══
    {"feature": "hostname", "platform": "arista_eos", "match_config": "hostname", "ordered": False},
    {"feature": "vrfs", "platform": "arista_eos", "match_config": "vrf instance", "ordered": False},
    {"feature": "interfaces", "platform": "arista_eos", "match_config": "interface ", "ordered": True},
    {"feature": "routing", "platform": "arista_eos", "match_config": "ip routing\nipv6 unicast-routing\nrouter bgp", "ordered": True},
    {"feature": "fabric_services", "platform": "arista_eos", "match_config": "service routing protocols model\nspanning-tree\nvlan internal order\nvlan \ninterface Vxlan\nip virtual-router\nrouter bfd\nip prefix-list\nroute-map", "ordered": False},
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
