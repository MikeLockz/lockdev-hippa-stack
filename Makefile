# HIPAA-Compliant Infrastructure Stack Makefile
# Installs all prerequisite technology and libraries locally

.PHONY: help install install-prerequisites install-python install-poetry install-pulumi install-aws-cli install-docker install-deps setup verify clean

# Default target
help: ## Show this help message
	@echo "HIPAA-Compliant Infrastructure Stack Setup"
	@echo "=========================================="
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Quick start:"
	@echo "  make install    # Install all prerequisites and dependencies"
	@echo "  make setup      # Setup project environments"
	@echo "  make verify     # Verify all installations"

# Main installation target
install: install-prerequisites install-deps setup ## Install all prerequisites and dependencies

# Install system prerequisites
install-prerequisites: install-python install-poetry install-pulumi install-aws-cli install-docker ## Install all system prerequisites

# Detect OS for platform-specific installations
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

install-python: ## Install Python 3.11+ (if not present)
	@echo "Checking Python installation..."
	@if ! command -v python3 >/dev/null 2>&1; then \
		echo "Python not found. Installing Python..."; \
		if [ "$(UNAME_S)" = "Darwin" ]; then \
			if command -v brew >/dev/null 2>&1; then \
				brew install python@3.11; \
			else \
				echo "Homebrew not found. Please install Python 3.11+ manually from https://python.org"; \
				exit 1; \
			fi; \
		elif [ "$(UNAME_S)" = "Linux" ]; then \
			if command -v apt-get >/dev/null 2>&1; then \
				sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv; \
			elif command -v yum >/dev/null 2>&1; then \
				sudo yum install -y python3 python3-pip; \
			else \
				echo "Package manager not found. Please install Python 3.11+ manually"; \
				exit 1; \
			fi; \
		else \
			echo "Unsupported OS. Please install Python 3.11+ manually"; \
			exit 1; \
		fi; \
	else \
		echo "Python found: $$(python3 --version)"; \
	fi

install-poetry: install-python ## Install Poetry package manager
	@echo "Checking Poetry installation..."
	@if ! command -v poetry >/dev/null 2>&1; then \
		echo "Installing Poetry..."; \
		curl -sSL https://install.python-poetry.org | python3 -; \
		echo 'export PATH="$$HOME/.local/bin:$$PATH"' >> ~/.bashrc; \
		echo 'export PATH="$$HOME/.local/bin:$$PATH"' >> ~/.zshrc; \
		export PATH="$$HOME/.local/bin:$$PATH"; \
	else \
		echo "Poetry found: $$(poetry --version)"; \
	fi

install-pulumi: ## Install Pulumi CLI
	@echo "Checking Pulumi installation..."
	@if ! command -v pulumi >/dev/null 2>&1; then \
		echo "Installing Pulumi..."; \
		curl -fsSL https://get.pulumi.com | sh; \
		echo 'export PATH="$$HOME/.pulumi/bin:$$PATH"' >> ~/.bashrc; \
		echo 'export PATH="$$HOME/.pulumi/bin:$$PATH"' >> ~/.zshrc; \
		export PATH="$$HOME/.pulumi/bin:$$PATH"; \
	else \
		echo "Pulumi found: $$(pulumi version)"; \
	fi

install-aws-cli: install-python ## Install AWS CLI
	@echo "Checking AWS CLI installation..."
	@if ! command -v aws >/dev/null 2>&1; then \
		echo "Installing AWS CLI..."; \
		if [ "$(UNAME_S)" = "Darwin" ]; then \
			if [ "$(UNAME_M)" = "arm64" ]; then \
				curl "https://awscli.amazonaws.com/AWSCLIV2-arm64.pkg" -o "AWSCLIV2.pkg"; \
				sudo installer -pkg AWSCLIV2.pkg -target /; \
				rm AWSCLIV2.pkg; \
			else \
				curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"; \
				sudo installer -pkg AWSCLIV2.pkg -target /; \
				rm AWSCLIV2.pkg; \
			fi; \
		elif [ "$(UNAME_S)" = "Linux" ]; then \
			if [ "$(UNAME_M)" = "x86_64" ]; then \
				curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"; \
			else \
				curl "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "awscliv2.zip"; \
			fi; \
			unzip awscliv2.zip; \
			sudo ./aws/install; \
			rm -rf aws awscliv2.zip; \
		else \
			pip3 install awscli; \
		fi; \
	else \
		echo "AWS CLI found: $$(aws --version)"; \
	fi

install-docker: ## Install Docker
	@echo "Checking Docker installation..."
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "Installing Docker..."; \
		if [ "$(UNAME_S)" = "Darwin" ]; then \
			echo "Please install Docker Desktop for Mac from https://docs.docker.com/desktop/install/mac-install/"; \
			echo "After installation, start Docker Desktop and try again."; \
			exit 1; \
		elif [ "$(UNAME_S)" = "Linux" ]; then \
			curl -fsSL https://get.docker.com -o get-docker.sh; \
			sudo sh get-docker.sh; \
			sudo usermod -aG docker $$USER; \
			rm get-docker.sh; \
			echo "Please log out and log back in for Docker permissions to take effect."; \
		else \
			echo "Please install Docker manually for your platform"; \
			exit 1; \
		fi; \
	else \
		echo "Docker found: $$(docker --version)"; \
	fi

# Install project dependencies
install-deps: install-iac-deps install-app-deps ## Install all project dependencies

install-iac-deps: ## Install infrastructure dependencies
	@echo "Installing infrastructure dependencies..."
	@cd lockdev-hippa-iac && \
		if [ -f "pyproject.toml" ]; then \
			poetry install; \
		else \
			echo "pyproject.toml not found in lockdev-hippa-iac/"; \
		fi

install-app-deps: ## Install application dependencies
	@echo "Installing application dependencies..."
	@cd lockdev-hippa-app && \
		if [ -f "pyproject.toml" ]; then \
			poetry install; \
		else \
			echo "pyproject.toml not found in lockdev-hippa-app/"; \
		fi

# Project setup
setup: setup-git-hooks setup-env-files ## Setup project environments

setup-git-hooks: ## Setup pre-commit hooks
	@echo "Setting up git hooks..."
	@if [ -d "lockdev-hippa-iac" ]; then \
		cd lockdev-hippa-iac && poetry run pre-commit install; \
	fi
	@if [ -d "lockdev-hippa-app" ]; then \
		cd lockdev-hippa-app && poetry run pre-commit install; \
	fi

setup-env-files: ## Create environment file templates
	@echo "Creating environment file templates..."
	@if [ ! -f ".env.example" ]; then \
		echo "# HIPAA Infrastructure Stack Environment Variables" > .env.example; \
		echo "# AWS Configuration" >> .env.example; \
		echo "AWS_ACCESS_KEY_ID=your-access-key" >> .env.example; \
		echo "AWS_SECRET_ACCESS_KEY=your-secret-key" >> .env.example; \
		echo "AWS_DEFAULT_REGION=us-east-1" >> .env.example; \
		echo "" >> .env.example; \
		echo "# Pulumi Configuration" >> .env.example; \
		echo "PULUMI_ACCESS_TOKEN=your-pulumi-token" >> .env.example; \
		echo "" >> .env.example; \
		echo "# Application Configuration" >> .env.example; \
		echo "DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db" >> .env.example; \
		echo "JWT_SECRET=your-jwt-secret" >> .env.example; \
		echo "ENVIRONMENT=development" >> .env.example; \
	fi
	@echo "Environment template created at .env.example"
	@echo "Copy to .env and configure with your actual values"

# Verification targets
verify: verify-tools verify-deps verify-config ## Verify all installations and configurations

verify-tools: ## Verify all required tools are installed
	@echo "Verifying tool installations..."
	@echo -n "Python: "; python3 --version || echo "❌ MISSING"
	@echo -n "Poetry: "; poetry --version || echo "❌ MISSING"
	@echo -n "Pulumi: "; pulumi version || echo "❌ MISSING"
	@echo -n "AWS CLI: "; aws --version || echo "❌ MISSING"
	@echo -n "Docker: "; docker --version || echo "❌ MISSING"
	@echo -n "Git: "; git --version || echo "❌ MISSING"

verify-deps: ## Verify project dependencies are installed
	@echo "Verifying project dependencies..."
	@if [ -d "lockdev-hippa-iac" ]; then \
		echo "Infrastructure dependencies:"; \
		cd lockdev-hippa-iac && poetry check && poetry show --tree || echo "❌ IAC deps missing"; \
	fi
	@if [ -d "lockdev-hippa-app" ]; then \
		echo "Application dependencies:"; \
		cd lockdev-hippa-app && poetry check && poetry show --tree || echo "❌ App deps missing"; \
	fi

verify-config: ## Verify configuration files
	@echo "Verifying configuration..."
	@if [ ! -f ".env" ]; then \
		echo "⚠️  .env file not found. Copy .env.example to .env and configure"; \
	else \
		echo "✅ .env file found"; \
	fi
	@if command -v aws >/dev/null 2>&1; then \
		if aws sts get-caller-identity >/dev/null 2>&1; then \
			echo "✅ AWS credentials configured"; \
		else \
			echo "⚠️  AWS credentials not configured. Run 'aws configure'"; \
		fi; \
	fi

# Development targets
dev-iac: ## Start infrastructure development environment
	@echo "Starting infrastructure development..."
	@cd lockdev-hippa-iac && poetry shell

dev-app: ## Start application development environment  
	@echo "Starting application development..."
	@cd lockdev-hippa-app && poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Testing targets
test: test-iac test-app ## Run all tests

test-iac: ## Run infrastructure tests
	@echo "Running infrastructure tests..."
	@cd lockdev-hippa-iac && poetry run pytest tests/ -v

test-app: ## Run application tests
	@echo "Running application tests..."
	@cd lockdev-hippa-app && ENVIRONMENT=testing poetry run pytest tests/ -v

# Code quality targets
lint: lint-iac lint-app ## Run linting on all code

lint-iac: ## Lint infrastructure code
	@cd lockdev-hippa-iac && poetry run black --check . && poetry run flake8 . && poetry run mypy . && poetry run bandit -r src/

lint-app: ## Lint application code
	@cd lockdev-hippa-app && poetry run black --check . && poetry run flake8 . && poetry run mypy . && poetry run bandit -r src/

format: format-iac format-app ## Format all code

format-iac: ## Format infrastructure code
	@cd lockdev-hippa-iac && poetry run black .

format-app: ## Format application code
	@cd lockdev-hippa-app && poetry run black .

# Deployment targets
deploy-preview: ## Preview infrastructure deployment
	@cd lockdev-hippa-iac && poetry run pulumi preview

deploy: ## Deploy infrastructure
	@cd lockdev-hippa-iac && poetry run pulumi up

# Cleanup targets
clean: clean-deps clean-cache ## Clean all generated files and caches

clean-deps: ## Clean dependency files
	@echo "Cleaning dependency files..."
	@find . -name "poetry.lock" -delete
	@find . -name "__pycache__" -type d -exec rm -rf {} +
	@find . -name "*.pyc" -delete
	@find . -name ".pytest_cache" -type d -exec rm -rf {} +
	@find . -name ".mypy_cache" -type d -exec rm -rf {} +

clean-cache: ## Clean build caches
	@echo "Cleaning build caches..."
	@find . -name ".coverage" -delete
	@find . -name "htmlcov" -type d -exec rm -rf {} +
	@find . -name "dist" -type d -exec rm -rf {} +
	@find . -name "build" -type d -exec rm -rf {} +

# CI/CD targets
ci-setup: ## Setup GitHub Actions secrets and environment
	@echo "Setting up GitHub Actions CI/CD..."
	@echo ""
	@echo "Required GitHub Secrets:"
	@echo "========================"
	@echo "Repository Secrets (Settings > Secrets and variables > Actions):"
	@echo "  - PULUMI_ACCESS_TOKEN: Your Pulumi Cloud access token"
	@echo "  - AWS_ACCOUNT_ID: Your AWS account ID"
	@echo "  - AWS_ADMIN_ACCESS_KEY_ID: Admin user for IAM bootstrap"
	@echo "  - AWS_ADMIN_SECRET_ACCESS_KEY: Admin user secret"
	@echo "  - PULUMI_AWS_ACCESS_KEY_ID: Limited IAM user for deployments"
	@echo "  - PULUMI_AWS_SECRET_ACCESS_KEY: Limited IAM user secret"
	@echo ""
	@echo "Environment Protection Rules:"
	@echo "  - Create environments: dev, staging, prod, dev-bootstrap, staging-bootstrap, prod-bootstrap"
	@echo "  - Add required reviewers for prod environments"
	@echo ""
	@echo "To get your AWS Account ID:"
	@echo "  aws sts get-caller-identity --query 'Account' --output text"
	@echo ""
	@echo "To get your Pulumi token:"
	@echo "  https://app.pulumi.com/account/tokens"

ci-validate: ## Validate CI/CD configuration locally
	@echo "Validating CI/CD configuration..."
	@echo ""
	@echo "Checking GitHub Actions workflows..."
	@if [ -f "lockdev-hippa-iac/.github/workflows/infrastructure.yml" ]; then \
		echo "✅ Infrastructure workflow found"; \
	else \
		echo "❌ Infrastructure workflow missing"; \
	fi
	@if [ -f "lockdev-hippa-app/.github/workflows/ci-cd.yml" ]; then \
		echo "✅ Application workflow found"; \
	else \
		echo "❌ Application workflow missing"; \
	fi
	@echo ""
	@echo "Checking required tools..."
	@command -v gh >/dev/null 2>&1 && echo "✅ GitHub CLI found" || echo "⚠️  GitHub CLI not found (install: brew install gh)"
	@command -v jq >/dev/null 2>&1 && echo "✅ jq found" || echo "⚠️  jq not found (install: brew install jq)"

ci-deploy-dev: ## Trigger dev deployment via GitHub Actions
	@echo "Triggering development deployment..."
	@if command -v gh >/dev/null 2>&1; then \
		gh workflow run infrastructure.yml -f environment=dev -f action=deploy; \
		echo "Development deployment triggered. Check: https://github.com/$(gh repo view --json owner,name -q '.owner.login + "/" + .name')/actions"; \
	else \
		echo "GitHub CLI not found. Install with: brew install gh"; \
		echo "Or manually trigger at: https://github.com/your-repo/actions/workflows/infrastructure.yml"; \
	fi

ci-deploy-staging: ## Trigger staging deployment via GitHub Actions
	@echo "Triggering staging deployment..."
	@if command -v gh >/dev/null 2>&1; then \
		gh workflow run infrastructure.yml -f environment=staging -f action=deploy; \
		echo "Staging deployment triggered. Check: https://github.com/$(gh repo view --json owner,name -q '.owner.login + "/" + .name')/actions"; \
	else \
		echo "GitHub CLI not found. Install with: brew install gh"; \
		echo "Or manually trigger at: https://github.com/your-repo/actions/workflows/infrastructure.yml"; \
	fi

ci-preview-prod: ## Preview production deployment via GitHub Actions
	@echo "Triggering production preview..."
	@if command -v gh >/dev/null 2>&1; then \
		gh workflow run infrastructure.yml -f environment=prod -f action=preview; \
		echo "Production preview triggered. Check: https://github.com/$(gh repo view --json owner,name -q '.owner.login + "/" + .name')/actions"; \
	else \
		echo "GitHub CLI not found. Install with: brew install gh"; \
		echo "Or manually trigger at: https://github.com/your-repo/actions/workflows/infrastructure.yml"; \
	fi

ci-status: ## Check CI/CD pipeline status
	@echo "Checking CI/CD pipeline status..."
	@if command -v gh >/dev/null 2>&1; then \
		echo "Recent workflow runs:"; \
		gh run list --limit 5; \
		echo ""; \
		echo "Workflow status:"; \
		gh workflow list; \
	else \
		echo "GitHub CLI not found. Install with: brew install gh"; \
		echo "Or check manually at: https://github.com/your-repo/actions"; \
	fi

# Documentation targets
docs: ## Show project documentation
	@echo "Opening project documentation..."
	@if command -v open >/dev/null 2>&1; then \
		open CLAUDE.md; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open CLAUDE.md; \
	else \
		echo "Please open CLAUDE.md manually"; \
	fi

# Environment targets
env-template: ## Create environment file template
	@make setup-env-files

# Quick development commands
quick-start: install verify ## Quick start - install everything and verify
	@echo ""
	@echo "🎉 Quick start complete!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Copy .env.example to .env and configure your credentials"
	@echo "2. Run 'aws configure' to set up AWS CLI"
	@echo "3. Run 'make deploy-preview' to preview infrastructure"
	@echo "4. Run 'make deploy' to deploy infrastructure"
	@echo "5. Run 'make dev-app' to start the application"

# Status check
status: verify-tools verify-config ## Show current installation status
	@echo ""
	@echo "📊 Installation Status Summary"
	@echo "============================="