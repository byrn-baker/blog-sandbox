#!/usr/bin/env python3
"""Set up Golden Config settings from Git-managed Nautobot content.

Run inside the Nautobot container:
    nautobot-server shell --command \
        "exec(open('/path/to/setup_golden_config.py').read())"

Prerequisites:
    - The blog-sandbox repository is registered with the content types below.
    - Repository sync imported the sp_demo_lab_golden_config GraphQL query.
    - GITHUB_TOKEN is set in the Nautobot worker environment.
"""

from nautobot.extras.choices import (
    SecretsGroupAccessTypeChoices,
    SecretsGroupSecretTypeChoices,
)
from nautobot.extras.models import (
    GitRepository,
    GraphQLQuery,
    Secret,
    SecretsGroup,
    SecretsGroupAssociation,
)
from nautobot_golden_config.models import GoldenConfigSetting

REPO_NAME = "blog-sandbox"
REPO_URL = "https://github.com/byrn-baker/blog-sandbox.git"
REPO_BRANCH = "main"
SECRET_NAME = "GITHUB_TOKEN"
SECRETS_GROUP_NAME = "GitHub"
GRAPHQL_QUERY_NAME = "sp_demo_lab_golden_config"

BACKUP_PATH = "golden-config/backup-configs/{{obj.location.name|slugify}}/{{obj.name}}.cfg"
INTENDED_PATH = "golden-config/intended-configs/{{obj.location.name|slugify}}/{{obj.name}}.cfg"
JINJA_PATH = "golden-config/templates/{{obj.platform.network_driver}}.j2"

PROVIDED_CONTENTS = [
    "extras.configcontext",
    "extras.configcontextschema",
    "extras.graphqlquery",
    "extras.job",
    "nautobot_golden_config.backupconfigs",
    "nautobot_golden_config.intendedconfigs",
    "nautobot_golden_config.jinjatemplate",
    "nautobot_golden_config.pluginproperties",
]

secret, created = Secret.objects.get_or_create(
    name=SECRET_NAME,
    defaults={
        "provider": "environment-variable",
        "parameters": {"variable": "GITHUB_TOKEN"},
    },
)
print(f"Secret '{SECRET_NAME}': {'created' if created else 'exists'}")

secrets_group, created = SecretsGroup.objects.get_or_create(name=SECRETS_GROUP_NAME)
print(
    f"SecretsGroup '{SECRETS_GROUP_NAME}': "
    f"{'created' if created else 'exists'}"
)

SecretsGroupAssociation.objects.get_or_create(
    secrets_group=secrets_group,
    access_type=SecretsGroupAccessTypeChoices.TYPE_HTTP,
    secret_type=SecretsGroupSecretTypeChoices.TYPE_TOKEN,
    defaults={"secret": secret},
)

repo, created = GitRepository.objects.get_or_create(
    name=REPO_NAME,
    defaults={
        "remote_url": REPO_URL,
        "branch": REPO_BRANCH,
        "secrets_group": secrets_group,
    },
)
if not created:
    repo.remote_url = REPO_URL
    repo.branch = REPO_BRANCH
    repo.secrets_group = secrets_group

repo.provided_contents = PROVIDED_CONTENTS
repo.validated_save()
print(f"GitRepository '{REPO_NAME}': {'created' if created else 'updated'}")

graphql_query = GraphQLQuery.objects.filter(name=GRAPHQL_QUERY_NAME).first()
if graphql_query is None:
    raise RuntimeError(
        f"Git-managed GraphQL query '{GRAPHQL_QUERY_NAME}' was not found. "
        "Sync blog-sandbox with GraphQL Queries enabled, then rerun this script."
    )
print(f"GraphQLQuery '{GRAPHQL_QUERY_NAME}': found (Git-managed)")

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
gc_settings.sot_agg_query = graphql_query
gc_settings.validated_save()
print("GoldenConfigSetting: configured")

print(f"\n{'=' * 50}")
print("Golden Config setup complete")
print(f"  Repository:     {REPO_NAME} ({REPO_URL})")
print(f"  Branch:         {REPO_BRANCH}")
print(f"  Backup path:    {BACKUP_PATH}")
print(f"  Intended path:  {INTENDED_PATH}")
print(f"  Template path:  {JINJA_PATH}")
print(f"  GraphQL query:  {GRAPHQL_QUERY_NAME} (Git-managed)")
print("=" * 50)
