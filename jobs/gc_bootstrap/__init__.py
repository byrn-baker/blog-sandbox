"""Set up the Git repository, secrets, and Golden Config settings.

The saved GraphQL query is owned by
``graphql_queries/sp_demo_lab_golden_config.gql`` and imported by repository
sync. This job resolves that imported object by name and links it to Golden
Config settings. It never creates or overwrites the query.

On a fresh Nautobot install, register ``blog-sandbox`` once under
Extensibility > Git Repositories with both Jobs and GraphQL Queries selected,
then sync it before running this job. After bootstrap, Git remains the only
source for jobs, the query, contexts, schemas, templates, and Golden Config
plugin properties.

Prerequisites:
  - GITHUB_TOKEN is set in the Nautobot worker environment.
  - The blog-sandbox repository is accessible from the worker.
  - Repository sync has imported ``sp_demo_lab_golden_config``.
"""

from nautobot.apps.jobs import Job, register_jobs
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


class GCBootstrap(Job):
    """Normalize the repository, secrets, and Golden Config settings."""

    class Meta:
        name = "Golden Config - Bootstrap Setup"
        description = (
            "Creates repository credentials, normalizes repository content types, "
            "and links the Git-managed GraphQL query and repositories to Golden Config."
        )
        has_sensitive_variables = False

    def run(self, *args, **kwargs):
        """Set up Golden Config prerequisites without rewriting Git-owned data."""
        secret, created = Secret.objects.get_or_create(
            name=SECRET_NAME,
            defaults={
                "provider": "environment-variable",
                "parameters": {"variable": "GITHUB_TOKEN"},
            },
        )
        self.logger.info(f"Secret '{SECRET_NAME}': {'created' if created else 'exists'}")

        secrets_group, created = SecretsGroup.objects.get_or_create(
            name=SECRETS_GROUP_NAME
        )
        self.logger.info(
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
            repo.validated_save()

        repo.provided_contents = PROVIDED_CONTENTS
        repo.validated_save()
        self.logger.info(
            f"GitRepository '{REPO_NAME}': {'created' if created else 'updated'}"
        )

        graphql_query = GraphQLQuery.objects.filter(name=GRAPHQL_QUERY_NAME).first()
        if graphql_query is None:
            raise RuntimeError(
                f"Git-managed GraphQL query '{GRAPHQL_QUERY_NAME}' was not found. "
                "Enable the GraphQL Queries content type on blog-sandbox, sync the "
                "repository, and rerun this job."
            )
        self.logger.info(f"GraphQLQuery '{GRAPHQL_QUERY_NAME}': found (Git-managed)")

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
        self.logger.info("GoldenConfigSetting: configured")
        self.logger.info(
            f"Bootstrap complete. Repo: {REPO_NAME}, Query: {GRAPHQL_QUERY_NAME}"
        )


name = "Golden Config Bootstrap"
register_jobs(GCBootstrap)
