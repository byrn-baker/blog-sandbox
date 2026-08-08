#!/usr/bin/env python3
"""
Setup script for Golden Config settings in Nautobot.

Run inside the Nautobot container:
    nautobot-server shell --command "exec(open('/path/to/setup_golden_config.py').read())"

Or via docker:
    docker exec nautobot-1 nautobot-server shell --command "exec(open('/tmp/setup_golden_config.py').read())"

Prerequisites:
    - Git repository already synced in Nautobot (name: "blog-sandbox")
    - GITHUB_TOKEN environment variable set in creds.env
"""

from nautobot.extras.models import GitRepository, GraphQLQuery, Secret, SecretsGroup, SecretsGroupAssociation
from nautobot_golden_config.models import GoldenConfigSetting
from nautobot.extras.choices import SecretsGroupAccessTypeChoices, SecretsGroupSecretTypeChoices

# --- Configuration ---
REPO_NAME = "blog-sandbox"
REPO_URL = "https://github.com/byrn-baker/blog-sandbox.git"
REPO_BRANCH = "main"
SECRET_NAME = "GITHUB_TOKEN"
SECRETS_GROUP_NAME = "GitHub"

GRAPHQL_QUERY_NAME = "sp_demo_lab_golden_config"
GRAPHQL_QUERY_FILE = "/opt/nautobot/golden-config/templates/graphql_query.graphql"

BACKUP_PATH = "golden-config/backup-configs/{{obj.location.name|slugify}}/{{obj.name}}.cfg"
INTENDED_PATH = "golden-config/intended-configs/{{obj.location.name|slugify}}/{{obj.name}}.cfg"
JINJA_PATH = "golden-config/templates/{{obj.platform.network_driver}}.j2"

# --- Step 1: Secret ---
secret, created = Secret.objects.get_or_create(
    name=SECRET_NAME,
    defaults={
        "provider": "environment-variable",
        "parameters": {"variable": "GITHUB_TOKEN"},
    }
)
print(f"Secret '{SECRET_NAME}': {'created' if created else 'exists'}")

# --- Step 2: Secrets Group ---
sg, created = SecretsGroup.objects.get_or_create(name=SECRETS_GROUP_NAME)
print(f"SecretsGroup '{SECRETS_GROUP_NAME}': {'created' if created else 'exists'}")

# Associate secret with group
SecretsGroupAssociation.objects.get_or_create(
    secrets_group=sg,
    access_type=SecretsGroupAccessTypeChoices.TYPE_HTTP,
    secret_type=SecretsGroupSecretTypeChoices.TYPE_TOKEN,
    defaults={"secret": secret},
)

# --- Step 3: Git Repository ---
repo, created = GitRepository.objects.get_or_create(
    name=REPO_NAME,
    defaults={
        "remote_url": REPO_URL,
        "branch": REPO_BRANCH,
        "secrets_group": sg,
    }
)
if not created:
    repo.remote_url = REPO_URL
    repo.branch = REPO_BRANCH
    repo.secrets_group = sg
    repo.save()

# Set provides
from nautobot.extras.choices import GitRepositoryProvidedTypeChoices
repo.provided_contents.set([
    "extras.configcontext",
    "extras.job",
    "nautobot_golden_config.backupconfigs",
    "nautobot_golden_config.intendedconfigs",
    "nautobot_golden_config.jinjatemplate",
])
repo.save()
print(f"GitRepository '{REPO_NAME}': {'created' if created else 'updated'}")

# --- Step 4: GraphQL Query ---
try:
    query_text = open(GRAPHQL_QUERY_FILE).read()
except FileNotFoundError:
    # Fallback: try relative to /tmp (for docker cp usage)
    query_text = open("/tmp/graphql_query.graphql").read()

gql, created = GraphQLQuery.objects.get_or_create(
    name=GRAPHQL_QUERY_NAME,
    defaults={"query": query_text}
)
if not created:
    gql.query = query_text
    gql.save()
print(f"GraphQLQuery '{GRAPHQL_QUERY_NAME}': {'created' if created else 'updated'}")

# --- Step 5: Golden Config Settings ---
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
gc_settings.save()
print(f"GoldenConfigSetting: configured")

# --- Summary ---
print(f"\n{'='*50}")
print(f"Golden Config setup complete!")
print(f"  Repository:     {REPO_NAME} ({REPO_URL})")
print(f"  Branch:         {REPO_BRANCH}")
print(f"  Backup path:    {BACKUP_PATH}")
print(f"  Intended path:  {INTENDED_PATH}")
print(f"  Template path:  {JINJA_PATH}")
print(f"  GraphQL query:  {GRAPHQL_QUERY_NAME}")
print(f"{'='*50}")
print(f"\nNext steps:")
print(f"  1. Sync the Git repository (Extensibility → Git Repos → Sync)")
print(f"  2. Enable Golden Config jobs (Jobs → enable all GC jobs)")
print(f"  3. Run 'Generate Intended Configurations'")
