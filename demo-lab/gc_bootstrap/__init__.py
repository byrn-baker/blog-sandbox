"""Golden Config Bootstrap — sets up git repo, secrets, and golden config settings.

This job handles the initial Nautobot setup required before golden config can
operate. It creates:

  1. A secret (environment variable for GITHUB_TOKEN)
  2. A secrets group associating the token for HTTP access
  3. The git repository pointing to blog-sandbox
  4. The GraphQL SoT aggregation query
  5. Golden Config settings linking repos, paths, and query

Run this once after a fresh Nautobot install, before running the topology
design job or any golden config operations.

Prerequisites:
  - GITHUB_TOKEN environment variable must be set in the Nautobot worker
  - The blog-sandbox repo must be accessible from the worker
"""

from nautobot.apps.jobs import register_jobs, Job
from nautobot.extras.models import (
    GitRepository,
    GraphQLQuery,
    Secret,
    SecretsGroup,
    SecretsGroupAssociation,
)
from nautobot.extras.choices import (
    SecretsGroupAccessTypeChoices,
    SecretsGroupSecretTypeChoices,
)

from nautobot_golden_config.models import GoldenConfigSetting


# ─── Configuration ─────────────────────────────────────────────────────────────

REPO_NAME = "blog-sandbox"
REPO_URL = "https://github.com/byrn-baker/blog-sandbox.git"
REPO_BRANCH = "main"

SECRET_NAME = "GITHUB_TOKEN"
SECRETS_GROUP_NAME = "GitHub"

GRAPHQL_QUERY_NAME = "sp_demo_lab_golden_config"
GRAPHQL_QUERY = """query ($device_id: ID!) {
  device(id: $device_id) {
    hostname: name
    config_context
    role {
      name
    }
    platform {
      name
      network_driver
      manufacturer {
        name
      }
    }
    location {
      name
      parent {
        name
      }
    }
    interfaces {
      name
      description
      enabled
      type
      mac_address
      mode
      mgmt_only
      vrf {
        name
        rd
      }
      ip_addresses {
        address
        ip_version
      }
      connected_interface {
        name
        device {
          name
        }
      }
      tags {
        name
      }
    }
    bgp_routing_instances {
      autonomous_system {
        asn
      }
      router_id {
        address
      }
      extra_attributes
      address_families {
        afi_safi
      }
      peer_groups {
        name
        autonomous_system {
          asn
        }
        extra_attributes
        address_families {
          afi_safi
          import_policy
          export_policy
        }
      }
      endpoints {
        enabled
        description
        peer_group {
          name
        }
        source_ip {
          address
        }
        source_interface {
          name
        }
        autonomous_system {
          asn
        }
        address_families {
          afi_safi
          import_policy
          export_policy
        }
        peer {
          source_ip {
            address
          }
          autonomous_system {
            asn
          }
          routing_instance {
            device {
              name
            }
            autonomous_system {
              asn
            }
          }
          address_families {
            afi_safi
          }
        }
      }
    }
    igp_routing_instances {
      name
      protocol
      router_id {
        address
      }
      isis_area
      isisconfiguration_set {
        name
        system_id
        default_metric
        interface_configurations {
          interface {
            name
          }
          circuit_type
          network_type
          metric
        }
      }
    }
  }
}"""

BACKUP_PATH = "golden-config/backup-configs/{{obj.location.name|slugify}}/{{obj.name}}.cfg"
INTENDED_PATH = "golden-config/intended-configs/{{obj.location.name|slugify}}/{{obj.name}}.cfg"
JINJA_PATH = "golden-config/templates/{{obj.platform.network_driver}}.j2"

PROVIDED_CONTENTS = [
    "extras.configcontext",
    "extras.configcontextschema",
    "nautobot_golden_config.backupconfigs",
    "nautobot_golden_config.intendedconfigs",
    "nautobot_golden_config.jinjatemplate",
]


class GCBootstrap(Job):
    """Bootstrap Golden Config: secrets, git repo, GraphQL query, and settings.

    Idempotent. Safe to re-run after config changes.
    """

    class Meta:
        name = "Golden Config - Bootstrap Setup"
        description = (
            "Creates the secret, secrets group, git repository, GraphQL query, "
            "and golden config settings needed for config management. Run once "
            "after a fresh Nautobot install."
        )
        has_sensitive_variables = False

    def run(self, *args, **kwargs):
        """Set up all golden config prerequisites."""
        # ── Step 1: Secret ──
        secret, created = Secret.objects.get_or_create(
            name=SECRET_NAME,
            defaults={
                "provider": "environment-variable",
                "parameters": {"variable": "GITHUB_TOKEN"},
            },
        )
        self.logger.info(f"Secret '{SECRET_NAME}': {'created' if created else 'exists'}")

        # ── Step 2: Secrets Group ──
        sg, created = SecretsGroup.objects.get_or_create(name=SECRETS_GROUP_NAME)
        self.logger.info(f"SecretsGroup '{SECRETS_GROUP_NAME}': {'created' if created else 'exists'}")

        SecretsGroupAssociation.objects.get_or_create(
            secrets_group=sg,
            access_type=SecretsGroupAccessTypeChoices.TYPE_HTTP,
            secret_type=SecretsGroupSecretTypeChoices.TYPE_TOKEN,
            defaults={"secret": secret},
        )

        # ── Step 3: Git Repository ──
        repo, created = GitRepository.objects.get_or_create(
            name=REPO_NAME,
            defaults={
                "remote_url": REPO_URL,
                "branch": REPO_BRANCH,
                "secrets_group": sg,
            },
        )
        if not created:
            repo.remote_url = REPO_URL
            repo.branch = REPO_BRANCH
            repo.secrets_group = sg
            repo.validated_save()

        # Set provided contents
        repo.provided_contents = PROVIDED_CONTENTS
        repo.validated_save()
        self.logger.info(f"GitRepository '{REPO_NAME}': {'created' if created else 'updated'}")

        # ── Step 4: GraphQL Query ──
        gql, created = GraphQLQuery.objects.get_or_create(
            name=GRAPHQL_QUERY_NAME,
            defaults={"query": GRAPHQL_QUERY},
        )
        if not created:
            gql.query = GRAPHQL_QUERY
            gql.validated_save()
        self.logger.info(f"GraphQLQuery '{GRAPHQL_QUERY_NAME}': {'created' if created else 'updated'}")

        # ── Step 5: Golden Config Settings ──
        gc_settings = GoldenConfigSetting.objects.filter(name="default").first()
        if not gc_settings:
            gc_settings = GoldenConfigSetting.objects.first()
        if not gc_settings:
            gc_settings = GoldenConfigSetting(name="default", slug="default")

        gc_settings.backup_repository = repo
        gc_settings.backup_path_template = BACKUP_PATH
        gc_settings.intended_repository = repo
        gc_settings.intended_path_template = INTENDED_PATH
        gc_settings.jinja_repository = repo
        gc_settings.jinja_path_template = JINJA_PATH
        gc_settings.sot_agg_query = gql
        gc_settings.validated_save()
        self.logger.info("GoldenConfigSetting: configured")

        self.logger.info(
            f"Bootstrap complete. Repo: {REPO_NAME}, Query: {GRAPHQL_QUERY_NAME}"
        )


name = "Golden Config Bootstrap"
register_jobs(GCBootstrap)
