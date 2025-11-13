# Makefile for Mochi Donut Development and Deployment
# Provides convenient commands for common development and production tasks

.PHONY: help install dev test lint format build deploy clean validate backup migrate

# Default target
help: ## Show this help message
	@echo "Mochi Donut - Development and Deployment Commands"
	@echo "================================================="
	@echo
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo
	@echo "Environment Variables:"
	@echo "  ENVIRONMENT=development|production"
	@echo "  APP_NAME=mochi-donut"

# Development Commands
install: ## Install dependencies with uv
	uv sync

dev: ## Start development server with auto-reload
	uv run uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000

dev-full: ## Start full development stack with docker-compose
	docker-compose up --build

dev-services: ## Start only development services (Redis, Postgres, Chroma)
	docker-compose up redis postgres chroma

# Testing Commands
test: ## Run all tests
	uv run pytest

test-unit: ## Run unit tests only
	uv run pytest tests/unit/

test-integration: ## Run integration tests only
	uv run pytest tests/integration/

test-coverage: ## Run tests with coverage report
	uv run pytest --cov=src --cov-report=html --cov-report=term-missing

test-performance: ## Run performance benchmarks
	uv run pytest tests/performance/ --benchmark-only

# Code Quality Commands
lint: ## Run linting with ruff
	uv run ruff check .

lint-fix: ## Fix linting issues automatically
	uv run ruff check --fix .

format: ## Format code with ruff
	uv run ruff format .

format-check: ## Check code formatting
	uv run ruff format --check .

type-check: ## Run type checking with mypy
	uv run mypy src/

security-scan: ## Run security scan with bandit
	uv run bandit -r src/

quality: lint format-check type-check security-scan ## Run all code quality checks

# Database Commands
db-upgrade: ## Run database migrations
	uv run alembic upgrade head

db-downgrade: ## Rollback one migration
	uv run alembic downgrade -1

db-migration: ## Create new migration (usage: make db-migration MESSAGE="Add new table")
	uv run alembic revision --autogenerate -m "$(MESSAGE)"

db-reset: ## Reset database (development only)
	rm -f mochi_donut.db
	uv run alembic upgrade head

# Build Commands
build: ## Build Docker image
	docker build -t mochi-donut:latest .

build-test: ## Build and test Docker image
	docker build -t mochi-donut:test .
	docker run --rm -d --name test-container -p 8080:8080 \
		-e ENVIRONMENT=testing \
		-e SECRET_KEY=test-secret \
		-e DATABASE_URL=sqlite+aiosqlite:///./test.db \
		mochi-donut:test
	sleep 30
	curl -f http://localhost:8080/health || (docker stop test-container && exit 1)
	docker stop test-container
	docker rmi mochi-donut:test

# Production Commands
validate: ## Validate deployment configuration
	./scripts/production/validate.sh

deploy: ## Deploy to production (full process)
	./scripts/production/deploy.sh

deploy-check: ## Run pre-deployment checks only
	./scripts/production/deploy.sh check

deploy-health: ## Check production health
	./scripts/production/deploy.sh health

# Database Production Commands
migrate: ## Run production migrations
	./scripts/production/migrate.sh migrate

migrate-status: ## Check migration status in production
	./scripts/production/migrate.sh status

migrate-rollback: ## Rollback production migration (usage: make migrate-rollback REVISION=-1)
	./scripts/production/migrate.sh rollback $(REVISION)

backup: ## Create production database backup
	./scripts/production/backup.sh backup

backup-list: ## List available backups
	./scripts/production/backup.sh list

backup-restore: ## Restore from backup (usage: make backup-restore BACKUP=file.gz)
	./scripts/production/backup.sh restore $(BACKUP)

# Monitoring Commands
logs: ## View production logs
	flyctl logs --app mochi-donut

logs-follow: ## Follow production logs in real-time
	flyctl logs --app mochi-donut --follow

status: ## Check production app status
	flyctl status --app mochi-donut

metrics: ## View production metrics
	curl -s https://mochi-donut.fly.dev/metrics | jq .

health: ## Check production health
	curl -s https://mochi-donut.fly.dev/health/detailed | jq .

# Fly.io Commands
fly-shell: ## Open shell in production container
	flyctl ssh console --app mochi-donut

fly-scale-up: ## Scale up production app
	flyctl scale count 2 --app mochi-donut

fly-scale-down: ## Scale down production app
	flyctl scale count 1 --app mochi-donut

fly-restart: ## Restart production app
	flyctl machine restart --app mochi-donut

# Utility Commands
clean: ## Clean up temporary files and caches
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage coverage.xml
	docker system prune -f 2>/dev/null || true

env-setup: ## Set up environment files from templates
	cp .env.sample .env
	cp env.production.sample .env.production
	@echo "Environment files created. Please edit with your values."

secrets-setup: ## Interactive setup of production secrets
	@echo "Setting up production secrets..."
	@read -p "Enter SECRET_KEY: " secret_key && \
	flyctl secrets set SECRET_KEY="$$secret_key" --app mochi-donut
	@read -p "Enter OPENAI_API_KEY: " openai_key && \
	flyctl secrets set OPENAI_API_KEY="$$openai_key" --app mochi-donut
	@read -p "Enter MOCHI_API_KEY: " mochi_key && \
	flyctl secrets set MOCHI_API_KEY="$$mochi_key" --app mochi-donut
	@echo "Required secrets set. Use 'make secrets-optional' for optional secrets."

secrets-optional: ## Set up optional production secrets
	@echo "Setting up optional secrets..."
	@read -p "Enter JINA_API_KEY (optional): " jina_key && \
	[ -n "$$jina_key" ] && flyctl secrets set JINA_API_KEY="$$jina_key" --app mochi-donut
	@read -p "Enter CHROMA_API_KEY (optional): " chroma_key && \
	[ -n "$$chroma_key" ] && flyctl secrets set CHROMA_API_KEY="$$chroma_key" --app mochi-donut
	@echo "Optional secrets configured."

# CI/CD Commands
ci-test: ## Run CI test suite locally
	uv run pytest --cov=src --cov-report=xml -v

ci-build: ## Build for CI
	docker build --tag mochi-donut:ci .

ci-validate: ## Validate CI configuration
	@echo "Validating GitHub Actions workflows..."
	@if [ -f .github/workflows/deploy.yml ] && [ -f .github/workflows/test.yml ]; then \
		echo "✓ GitHub Actions workflows found"; \
	else \
		echo "✗ GitHub Actions workflows missing"; \
		exit 1; \
	fi

# Documentation Commands
docs-serve: ## Serve documentation locally
	@echo "API documentation available at:"
	@echo "  http://localhost:8000/docs (Swagger UI)"
	@echo "  http://localhost:8000/redoc (ReDoc)"
	$(MAKE) dev

# Quick start commands
setup: install env-setup ## Quick project setup
	@echo "Project setup complete!"
	@echo "1. Edit .env with your configuration"
	@echo "2. Run 'make dev' to start development server"
	@echo "3. Visit http://localhost:8000/docs for API documentation"

production-setup: ## Set up production deployment
	@echo "Production setup checklist:"
	@echo "1. Install flyctl: curl -L https://fly.io/install.sh | sh"
	@echo "2. Authenticate: flyctl auth login"
	@echo "3. Create app: flyctl apps create mochi-donut"
	@echo "4. Create volume: flyctl volumes create mochi_donut_data --region iad --size 10"
	@echo "5. Set secrets: make secrets-setup"
	@echo "6. Validate: make validate"
	@echo "7. Deploy: make deploy"

# Development workflows
quick-test: format lint test-unit ## Quick development test cycle

full-test: format lint type-check security-scan test ## Full test cycle

pre-commit: quality test ## Pre-commit validation

pre-deploy: validate test migrate-status ## Pre-deployment validation

# Default environment
ifndef ENVIRONMENT
ENVIRONMENT = development
endif

# Default app name
ifndef APP_NAME
APP_NAME = mochi-donut
endif