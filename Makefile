# Golden Config Template CI
# Run locally with `make lint` or `make test` or `make ci` for both.
# Run `make validate` for Batfish deep validation (requires running container).

.PHONY: lint test validate ci ci-full help

TEMPLATE_DIR := golden-config/templates

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

lint: ## Run j2lint on all Jinja2 templates
	j2lint $(TEMPLATE_DIR) --extensions j2 -i jinja-statements-indentation single-statement-per-line

test: ## Render templates against mock contexts and validate output
	pytest tests/test_template_render.py tests/test_config_structure.py -v

validate: ## Validate rendered configs with Batfish (requires container)
	pytest tests/test_batfish_validate.py tests/test_intended_configs.py -v

ci: lint test ## Run fast CI pipeline (lint + render tests)

ci-full: lint test validate ## Run full CI pipeline including Batfish validation
