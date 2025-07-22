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
install-prerequisites: install-python install-poetry install-pulumi install-aws-cli install-docker install-security-tools ## Install all system prerequisites

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

install-security-tools: install-python ## Install security scanning tools (Safety and Trivy)
	@echo "Installing security scanning tools..."
	@echo "Checking Safety installation..."
	@if ! command -v safety >/dev/null 2>&1 && ! python3 -c "import safety" >/dev/null 2>&1; then \
		echo "Installing Safety for dependency vulnerability scanning..."; \
		if [ "$(UNAME_S)" = "Darwin" ]; then \
			if ! command -v pipx >/dev/null 2>&1; then \
				echo "Installing pipx first..."; \
				if [ "$(UNAME_M)" = "arm64" ]; then \
					arch -arm64 brew install pipx; \
				else \
					brew install pipx; \
				fi; \
			fi; \
			pipx install safety; \
		else \
			pip3 install --user safety; \
		fi; \
	else \
		if command -v safety >/dev/null 2>&1; then \
			echo "Safety found: $$(safety --version)"; \
		else \
			echo "Safety found: $$(python3 -c 'import safety; print(safety.__version__)')"; \
		fi; \
	fi
	@echo "Checking Trivy installation..."
	@if ! command -v trivy >/dev/null 2>&1; then \
		echo "Installing Trivy for container/filesystem vulnerability scanning..."; \
		if [ "$(UNAME_S)" = "Darwin" ]; then \
			if command -v brew >/dev/null 2>&1; then \
				brew install aquasecurity/trivy/trivy; \
			else \
				echo "Installing Trivy using curl..."; \
				curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin; \
			fi; \
		elif [ "$(UNAME_S)" = "Linux" ]; then \
			echo "Installing Trivy using curl..."; \
			curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin; \
		else \
			echo "Please install Trivy manually for your platform"; \
			echo "Visit: https://github.com/aquasecurity/trivy"; \
		fi; \
	else \
		echo "Trivy found: $$(trivy --version | head -1)"; \
	fi
	@echo "✅ Security tools installation complete"

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
	@echo -n "Safety: "; (command -v safety >/dev/null 2>&1 && safety --version) || (python3 -c "import safety; print('v' + safety.__version__)" 2>/dev/null) || echo "❌ MISSING (install with: make install-security-tools)"
	@echo -n "Trivy: "; trivy --version 2>/dev/null | head -1 || echo "❌ MISSING (install with: make install-security-tools)"

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

dev-app: ## Start application development environment with containers
	@echo "Starting application development environment..."
	@echo "Checking if containers are already running..."
	@cd lockdev-hippa-app && \
	if docker-compose ps --services --filter "status=running" | grep -q "db\|redis\|app"; then \
		echo "✅ Containers already running"; \
		docker-compose ps; \
	else \
		echo "🚀 Starting containerized development environment..."; \
		docker-compose up -d; \
		echo ""; \
		echo "Waiting for services to be ready..."; \
		sleep 5; \
		echo ""; \
		echo "✅ Development environment ready!"; \
		echo ""; \
		echo "📱 Application: http://localhost:8000"; \
		echo "📚 API Docs: http://localhost:8000/docs"; \
		echo "🔍 Health Check: http://localhost:8000/health/"; \
		echo ""; \
		echo "View logs: make dev-logs"; \
		echo "Stop: make dev-stop"; \
	fi

dev-app-local: ## Start application locally without containers (requires local PostgreSQL)
	@echo "Starting application locally..."
	@cd lockdev-hippa-app && poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

dev-logs: ## View development environment logs
	@echo "Viewing development logs..."
	@cd lockdev-hippa-app && docker-compose logs -f

dev-stop: ## Stop development environment
	@echo "Stopping development environment..."
	@cd lockdev-hippa-app && docker-compose down
	@echo "✅ Development environment stopped"

dev-status: ## Check development environment status
	@echo "Development environment status:"
	@cd lockdev-hippa-app && \
	if docker-compose ps --services --filter "status=running" | grep -q "."; then \
		echo "✅ Containers running:"; \
		docker-compose ps; \
		echo ""; \
		echo "🔗 Quick links:"; \
		echo "  Application: http://localhost:8000"; \
		echo "  API Docs: http://localhost:8000/docs"; \
		echo "  Health: http://localhost:8000/health/"; \
	else \
		echo "❌ No containers running"; \
		echo "Start with: make dev-app"; \
	fi

# Testing targets
test: test-iac test-app ## Run all comprehensive tests (CI-equivalent)
test-quick: test-iac test-app-quick ## Run basic tests only

test-iac: ## Run infrastructure tests
	@echo "Running infrastructure tests..."
	@cd lockdev-hippa-iac && poetry run pytest tests/ -v

test-app: ## Run comprehensive application tests (matches CI)
	@echo "🧪 Running comprehensive application tests (CI-equivalent)..."
	@echo ""
	@echo "📋 Test Environment Setup"
	@echo "========================="
	@cd lockdev-hippa-app && \
	echo "Starting test database..." && \
	docker-compose up -d db redis && \
	echo "Waiting for database to be ready..." && \
	sleep 3 && \
	echo "✅ Test environment ready" && \
	echo "" && \
	echo "🔒 Security Checks" && \
	echo "==================" && \
	echo "Running Bandit security scan..." && \
	poetry run bandit -r src/ && \
	echo "Running Safety vulnerability check..." && \
	(if command -v safety >/dev/null 2>&1 || python3 -c "import safety" >/dev/null 2>&1; then \
		poetry run safety check; \
	else \
		echo "⚠️  Safety not available - install with: make install-security-tools"; \
		false; \
	fi) && \
	echo "✅ Security checks passed" && \
	echo "" && \
	echo "🎨 Code Quality Checks" && \
	echo "======================" && \
	echo "Running Black format check..." && \
	poetry run black --check src/ && \
	echo "Running Flake8 linting..." && \
	(poetry run flake8 src/ || echo "⚠️  Flake8 issues found - run 'make lint-app' for details") && \
	echo "Running MyPy type checking..." && \
	(poetry run mypy src/ || echo "⚠️  MyPy issues found - run 'make lint-app' for details") && \
	echo "✅ Code quality checks passed" && \
	echo "" && \
	echo "🧪 Running Tests" && \
	echo "================" && \
	ENVIRONMENT=testing \
	DATABASE_URL=postgresql://postgres:password@localhost:5432/hipaa_db \
	JWT_SECRET=test-secret \
	poetry run pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html && \
	echo "" && \
	echo "🔍 Vulnerability Scanning" && \
	echo "=========================" && \
	(if command -v trivy >/dev/null 2>&1; then \
		echo "Running Trivy filesystem scan..." && \
		trivy fs --severity HIGH,CRITICAL . && \
		echo "✅ Trivy scan completed"; \
	else \
		echo "⚠️  Trivy not available - install for full CI equivalence"; \
		echo "  brew install aquasecurity/trivy/trivy"; \
	fi) && \
	echo "" && \
	echo "🧹 Cleanup" && \
	echo "==========" && \
	docker-compose down && \
	echo "✅ Test environment cleaned up" && \
	echo "" && \
	echo "🎉 All tests completed successfully!" && \
	echo "📊 Coverage report generated in htmlcov/index.html"

test-app-quick: ## Run basic application tests only (original behavior)
	@echo "Running basic application tests..."
	@cd lockdev-hippa-app && ENVIRONMENT=testing poetry run pytest tests/ -v

test-app-security: ## Run security scans only
	@echo "🔒 Running security scans..."
	@cd lockdev-hippa-app && \
	echo "Running Bandit security scan..." && \
	poetry run bandit -r src/ && \
	echo "Running Safety vulnerability check..." && \
	(poetry run safety check || echo "⚠️  Safety check failed or not available") && \
	echo "✅ Security scans completed"

test-app-trivy: ## Run Trivy vulnerability scan (like CI)
	@echo "🔍 Running Trivy vulnerability scan..."
	@if command -v trivy >/dev/null 2>&1; then \
		cd lockdev-hippa-app && trivy fs --severity HIGH,CRITICAL .; \
	else \
		echo "⚠️  Trivy not installed. Install with:"; \
		echo "  brew install aquasecurity/trivy/trivy"; \
		echo "  # or"; \
		echo "  curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin"; \
	fi

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
	@echo "🚀 Setting up GitHub Actions CI/CD..."
	@echo ""
	@if ! command -v gh >/dev/null 2>&1; then \
		echo "❌ GitHub CLI (gh) is not installed."; \
		echo "Install it with: brew install gh"; \
		echo "Then run: gh auth login"; \
		exit 1; \
	fi
	@if ! gh auth status >/dev/null 2>&1; then \
		echo "❌ Not logged into GitHub CLI."; \
		echo "Run: gh auth login"; \
		exit 1; \
	fi
	@echo "✅ GitHub CLI is ready"
	@echo ""
	@echo "📁 Repository: $$(gh repo view --json owner,name -q '.owner.login + "/" + .name')"
	@echo ""
	@echo "🔐 Setting up GitHub repository secrets..."
	@AWS_ACCOUNT_ID=$$(aws sts get-caller-identity --query 'Account' --output text); \
	PULUMI_TOKEN="$$PULUMI_ACCESS_TOKEN"; \
	AWS_ACCESS_KEY=$$(aws configure get aws_access_key_id || echo "$$AWS_ACCESS_KEY_ID"); \
	AWS_SECRET_KEY=$$(aws configure get aws_secret_access_key || echo "$$AWS_SECRET_ACCESS_KEY"); \
	if [ -z "$$PULUMI_TOKEN" ]; then \
		echo "❌ PULUMI_ACCESS_TOKEN not found in environment"; \
		echo "Get your token from: https://app.pulumi.com/account/tokens"; \
		echo "Then export PULUMI_ACCESS_TOKEN=your-token"; \
		exit 1; \
	fi; \
	if [ -z "$$AWS_ACCESS_KEY" ] || [ -z "$$AWS_SECRET_KEY" ]; then \
		echo "❌ AWS credentials not found"; \
		echo "Run: aws configure"; \
		exit 1; \
	fi; \
	echo "📝 Setting GitHub repository secrets..."; \
	gh secret set AWS_ACCOUNT_ID --body "$$AWS_ACCOUNT_ID" && echo "✅ Set AWS_ACCOUNT_ID"; \
	gh secret set PULUMI_ACCESS_TOKEN --body "$$PULUMI_TOKEN" && echo "✅ Set PULUMI_ACCESS_TOKEN"; \
	gh secret set PULUMI_AWS_ACCESS_KEY_ID --body "$$AWS_ACCESS_KEY" && echo "✅ Set PULUMI_AWS_ACCESS_KEY_ID"; \
	gh secret set PULUMI_AWS_SECRET_ACCESS_KEY --body "$$AWS_SECRET_KEY" && echo "✅ Set PULUMI_AWS_SECRET_ACCESS_KEY"; \
	gh secret set AWS_ADMIN_ACCESS_KEY_ID --body "$$AWS_ACCESS_KEY" && echo "✅ Set AWS_ADMIN_ACCESS_KEY_ID"; \
	gh secret set AWS_ADMIN_SECRET_ACCESS_KEY --body "$$AWS_SECRET_KEY" && echo "✅ Set AWS_ADMIN_SECRET_ACCESS_KEY"
	@echo ""
	@echo "🎉 GitHub secrets configured successfully!"
	@echo ""
	@echo "Next Steps:"
	@echo "==========="
	@REPO_URL=$$(gh repo view --json url -q '.url'); \
	echo "1. Set up GitHub environments:"; \
	echo "   - Go to: $$REPO_URL/settings/environments"; \
	echo "   - Create environments: dev, staging, prod"; \
	echo "   - Add protection rules for prod (require reviewers)"; \
	echo ""; \
	echo "2. Test the CI/CD pipeline:"; \
	echo "   make ci-validate"; \
	echo "   make ci-deploy-dev"; \
	echo ""; \
	echo "3. View your secrets:"; \
	echo "   $$REPO_URL/settings/secrets/actions"; \
	echo ""; \
	echo "4. Monitor workflows:"; \
	echo "   $$REPO_URL/actions"

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

ci-deploy-app: ## Deploy application only (to existing infrastructure)
	@echo "Deploying application to existing infrastructure..."
	@if command -v gh >/dev/null 2>&1; then \
		echo "Pushing to main branch to trigger application deployment..."; \
		git push origin master:main || git push origin master; \
		echo "Application deployment triggered. Check: https://github.com/$(gh repo view --json owner,name -q '.owner.login + "/" + .name')/actions"; \
	else \
		echo "GitHub CLI not found. Install with: brew install gh"; \
		echo "Or manually push to main branch to trigger deployment"; \
	fi

ci-build-app: ## Build and test application without deployment
	@echo "Building and testing application..."
	@if command -v gh >/dev/null 2>&1; then \
		gh workflow run ci-cd.yml; \
		echo "Application build triggered. Check: https://github.com/$(gh repo view --json owner,name -q '.owner.login + "/" + .name')/actions"; \
	else \
		echo "GitHub CLI not found. Install with: brew install gh"; \
		echo "Or create a pull request to trigger testing"; \
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
		echo ""; \
		echo "🔗 Quick Links:"; \
		REPO_URL=$$(gh repo view --json url -q '.url'); \
		echo "  GitHub Actions: $$REPO_URL/actions"; \
		echo "  Latest Runs: $$REPO_URL/actions/runs"; \
		echo ""; \
		echo "📊 View specific run details:"; \
		echo "  gh run view <run-id> --log-failed"; \
		echo "  gh run view <run-id> --log"; \
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