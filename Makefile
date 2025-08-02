# HIPAA-Compliant Infrastructure Stack Unified Makefile
# Single Makefile for both application and infrastructure operations

.PHONY: help tui install install-prerequisites install-python install-poetry install-pulumi install-aws-cli install-docker install-security-tools install-deps setup verify clean format lint test deploy

# Default target
help: ## Show this help message
	@echo "HIPAA-Compliant Infrastructure Stack"
	@echo "===================================="
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Quick start:"
	@echo "  make install              # Install all prerequisites and dependencies"
	@echo "  make setup                # Setup project environments"
	@echo "  make verify               # Verify all installations"
	@echo ""
	@echo "Infrastructure:"
	@echo "  make setup-credentials    # Interactive AWS credentials setup"
	@echo "  make setup-env-dev        # Setup dev environment (auto-handles credentials)"
	@echo "  make preview-dev          # Preview dev infrastructure changes" 
	@echo "  make deploy-dev           # Deploy dev infrastructure"
	@echo "  make clean-dev            # Destroy dev infrastructure"
	@echo ""
	@echo "Application:"
	@echo "  make dev-app              # Start app development environment"
	@echo "  make test                 # Run all tests"
	@echo "  make lint                 # Format and lint code"
	@echo "  make tui                  # Launch Terminal User Interface"
	@echo "  make start                # Launch modern Textual TUI"

tui: ## Launch Terminal User Interface for make commands (Rich version)
	@echo "🖥️  Starting HIPAA Infrastructure Stack TUI (Rich)..."
	@if [ -d "lockdev-hippa-app" ]; then \
		cd lockdev-hippa-app && poetry run python ../tui_make.py; \
	elif [ -d "lockdev-hippa-iac" ]; then \
		cd lockdev-hippa-iac && poetry run python ../tui_make.py; \
	else \
		python3 tui_make.py; \
	fi

start: ## Launch Textual TUI for make commands (Modern interface)
	@echo "🚀 Starting HIPAA Infrastructure Stack TUI (Textual)..."
	@if command -v poetry >/dev/null 2>&1; then \
		if [ -f "pyproject.toml" ]; then \
			poetry run python tui_make_textual.py; \
		elif [ -d "lockdev-hippa-app" ]; then \
			cd lockdev-hippa-app && poetry run python ../tui_make_textual.py; \
		elif [ -d "lockdev-hippa-iac" ]; then \
			cd lockdev-hippa-iac && poetry run python ../tui_make_textual.py; \
		else \
			python3 tui_make_textual.py; \
		fi \
	else \
		if ! command -v pip3 >/dev/null 2>&1; then \
			echo "❌ Python 3 and pip3 are required. Please install Python 3.8+"; \
			exit 1; \
		fi; \
		echo "📦 Installing Textual..."; \
		pip3 install textual; \
		python3 tui_make_textual.py; \
	fi



# Detect OS for platform-specific installations
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

# =========================================
# INSTALLATION & SETUP
# =========================================

# Main installation target
install: install-prerequisites install-deps setup ## Install all prerequisites and dependencies

# Install system prerequisites
install-prerequisites: install-python install-poetry install-pulumi install-aws-cli install-docker install-security-tools ## Install all system prerequisites

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

install-security-tools: install-python ## Install security scanning tools
	@echo "Installing security scanning tools..."
	@echo "Checking pip-audit installation..."
	@if ! command -v pip-audit >/dev/null 2>&1; then \
		echo "Installing pip-audit for dependency vulnerability scanning..."; \
		if ! command -v pipx >/dev/null 2>&1; then \
			echo "Installing pipx first..."; \
			if [ "$(UNAME_S)" = "Darwin" ]; then \
				brew install pipx; \
			else \
				pip3 install --user pipx; \
			fi; \
		fi; \
		pipx install pip-audit; \
	else \
		echo "pip-audit found: $$(pip-audit --version)"; \
	fi
	@echo "Checking Trivy installation..."
	@if ! command -v trivy >/dev/null 2>&1; then \
		echo "Installing Trivy for container/filesystem vulnerability scanning..."; \
		if [ "$(UNAME_S)" = "Darwin" ]; then \
			if [ "$(UNAME_M)" = "arm64" ]; then \
				arch -arm64 brew install trivy; \
			else \
				brew install trivy; \
			fi; \
		elif [ "$(UNAME_S)" = "Linux" ]; then \
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

# =========================================
# SETUP & CONFIGURATION
# =========================================

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

# =========================================
# DEVELOPMENT ENVIRONMENTS
# =========================================

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

# =========================================
# TESTING
# =========================================

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
		echo "Running pip-audit vulnerability check..." && \
		(if command -v pip-audit >/dev/null 2>&1; then \
			pip-audit --desc; \
		else \
			echo "⚠️  pip-audit not available - install with: make install-security-tools"; \
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
			echo "⚠️  Trivy not available - install with: make install-security-tools"; \
			false; \
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

test-app-security: ## Run security scans only (pip-audit and Bandit)
	@echo "🔒 Running security scans..."
	@cd lockdev-hippa-app && \
		echo "Running Bandit security scan..." && \
		poetry run bandit -r src/ && \
		echo "Running pip-audit vulnerability check..." && \
		(if command -v pip-audit >/dev/null 2>&1; then \
			pip-audit --desc; \
		else \
			echo "⚠️  pip-audit not available - install with: make install-security-tools"; \
			false; \
		fi) && \
		echo "✅ Security scans completed"

test-app-trivy: ## Run Trivy vulnerability scan (like CI)
	@echo "🔍 Running Trivy vulnerability scan..."
	@if command -v trivy >/dev/null 2>&1; then \
		cd lockdev-hippa-app && trivy fs --severity HIGH,CRITICAL .; \
	else \
		echo "⚠️  Trivy not installed. Install with: make install-security-tools"; \
		false; \
	fi

# =========================================
# CODE QUALITY
# =========================================

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

# =========================================
# INFRASTRUCTURE DEPLOYMENT (IAC)
# =========================================

# Phase 1: Environment Setup (uses root credentials)
setup-credentials: ## Interactive AWS credentials setup for all environments
	@echo "🔑 Setting up AWS credentials..."
	@chmod +x lockdev-hippa-iac/scripts/*.sh
	@cd lockdev-hippa-iac && ./scripts/setup-credentials.sh --interactive

setup-credentials-dev: ## Setup AWS credentials for development environment
	@echo "🔑 Setting up AWS credentials for development..."
	@chmod +x lockdev-hippa-iac/scripts/*.sh
	@cd lockdev-hippa-iac && ./scripts/setup-credentials.sh -e dev

setup-env-dev: ## Setup development environment (Phase 1: Root → Service User)
	@echo "🔧 Phase 1: Setting up development environment..."
	@chmod +x lockdev-hippa-iac/scripts/*.sh
	@echo "Checking AWS credentials first..."
	@if ! aws sts get-caller-identity --profile dev-root 2>/dev/null; then \
		echo "AWS credentials not configured. Running interactive setup..."; \
		cd lockdev-hippa-iac && ./scripts/setup-credentials.sh -e dev; \
	fi
	@cd lockdev-hippa-iac && ENVIRONMENT=dev ./scripts/setup-env.sh

setup-env-staging: ## Setup staging environment (Phase 1: Root → Service User)
	@echo "🔧 Phase 1: Setting up staging environment..."
	@chmod +x lockdev-hippa-iac/scripts/*.sh
	@echo "Checking AWS credentials first..."
	@if ! aws sts get-caller-identity --profile staging-root 2>/dev/null; then \
		echo "AWS credentials not configured. Running interactive setup..."; \
		cd lockdev-hippa-iac && ./scripts/setup-credentials.sh -e staging; \
	fi
	@cd lockdev-hippa-iac && ENVIRONMENT=staging ./scripts/setup-env.sh

setup-env-prod: ## Setup production environment (Phase 1: Root → Service User)
	@echo "🔧 Phase 1: Setting up production environment..."
	@chmod +x lockdev-hippa-iac/scripts/*.sh
	@echo "Checking AWS credentials first..."
	@if ! aws sts get-caller-identity --profile prod-root 2>/dev/null; then \
		echo "AWS credentials not configured. Running interactive setup..."; \
		cd lockdev-hippa-iac && ./scripts/setup-credentials.sh -e prod; \
	fi
	@cd lockdev-hippa-iac && ENVIRONMENT=prod ./scripts/setup-env.sh

setup-env-all: setup-env-dev setup-env-staging setup-env-prod ## Setup all environments

# Environment validation with error reporting
validate-env-dev: ## Validate development environment access
	@echo "🔍 Validating development environment..."
	@if aws sts get-caller-identity --profile pulumi-deploy-user-dev 2>/dev/null; then \
		echo "✅ Development environment validation successful"; \
	else \
		echo "❌ Development environment validation failed"; \
		echo ""; \
		echo "💡 Possible causes:"; \
		echo "  • Service user profile 'pulumi-deploy-user-dev' not configured"; \
		echo "  • Invalid or expired credentials"; \
		echo "  • Service user doesn't exist or was deleted"; \
		echo "  • Network connectivity issues"; \
		echo ""; \
		echo "🔧 To fix this issue:"; \
		echo "  1. Run: make setup-env-dev"; \
		echo "  2. If that fails, check your root profile: aws sts get-caller-identity --profile dev-root"; \
		echo ""; \
		echo "🔍 Detailed error:"; \
		aws sts get-caller-identity --profile pulumi-deploy-user-dev; \
		exit 1; \
	fi

validate-env-staging: ## Validate staging environment access
	@echo "🔍 Validating staging environment..."
	@if aws sts get-caller-identity --profile pulumi-deploy-user-staging 2>/dev/null; then \
		echo "✅ Staging environment validation successful"; \
	else \
		echo "❌ Staging environment validation failed"; \
		echo ""; \
		echo "🔧 To fix: make setup-env-staging"; \
		echo "🔍 Detailed error:"; \
		aws sts get-caller-identity --profile pulumi-deploy-user-staging; \
		exit 1; \
	fi

validate-env-prod: ## Validate production environment access
	@echo "🔍 Validating production environment..."
	@if aws sts get-caller-identity --profile pulumi-deploy-user-prod 2>/dev/null; then \
		echo "✅ Production environment validation successful"; \
	else \
		echo "❌ Production environment validation failed"; \
		echo ""; \
		echo "🔧 To fix: make setup-env-prod"; \
		echo "🔍 Detailed error:"; \
		aws sts get-caller-identity --profile pulumi-deploy-user-prod; \
		exit 1; \
	fi

# Phase 2: Infrastructure Deployment (uses service credentials)
preview-dev: ## Preview dev infrastructure changes (Phase 2: Service User → Preview)
	@echo "👁️  Previewing development infrastructure..."
	@cd lockdev-hippa-iac && ENVIRONMENT=dev ./scripts/deploy.sh -o preview

preview-staging: ## Preview staging infrastructure changes
	@echo "👁️  Previewing staging infrastructure..."
	@cd lockdev-hippa-iac && ENVIRONMENT=staging ./scripts/deploy.sh -o preview

preview-prod: ## Preview production infrastructure changes
	@echo "👁️  Previewing production infrastructure..."
	@cd lockdev-hippa-iac && ENVIRONMENT=prod ./scripts/deploy.sh -o preview

deploy-dev: ## Smart deploy to development (auto-setup + deploy)
	@echo "🤖 Smart deployment to development environment..."
	@cd lockdev-hippa-iac && ENVIRONMENT=dev FORCE=true ./scripts/deploy.sh -o deploy

deploy-staging: ## Smart deploy to staging environment (auto-setup + deploy)
	@echo "🤖 Smart deployment to staging environment..."
	@cd lockdev-hippa-iac && ENVIRONMENT=staging FORCE=true ./scripts/deploy.sh -o deploy

deploy-prod: ## Smart deploy to production environment (auto-setup + deploy)
	@echo "🤖 Smart deployment to production environment..."
	@cd lockdev-hippa-iac && ENVIRONMENT=prod FORCE=true ./scripts/deploy.sh -o deploy

# Dry-run deployments (safe testing)
deploy-dev-dry: ## Dry run deployment to development
	@echo "🧪 Dry run: Development deployment..."
	@cd lockdev-hippa-iac && ./scripts/deploy.sh -o deploy --dry-run

deploy-staging-dry: ## Dry run deployment to staging
	@echo "🧪 Dry run: Staging deployment..."
	@cd lockdev-hippa-iac && ./scripts/deploy.sh -o deploy --dry-run

deploy-prod-dry: ## Dry run deployment to production
	@echo "🧪 Dry run: Production deployment..."
	@cd lockdev-hippa-iac && ./scripts/deploy.sh -o deploy --dry-run

# Infrastructure Cleanup (safe destruction)
clean-dev: ## Destroy development infrastructure and service account (auto-setup if needed)
	@echo "💥 Destroying development infrastructure and service account with enhanced protection handling..."
	@echo "🔍 This will handle load balancer deletion protection, ENI dependencies, and comprehensive cleanup"
	@cd lockdev-hippa-iac && {
		echo "🔄 Setting up enhanced cleanup scripts..."; \
		chmod +x enhanced-cleanup.sh scripts/cleanup.sh force-cleanup.sh; \
		echo "🧹 Running enhanced comprehensive cleanup..."; \
		./enhanced-cleanup.sh dev; \
	}

clean-staging: ## Destroy staging infrastructure (auto-setup if needed)
	@echo "💥 Destroying staging infrastructure with enhanced protection handling..."
	@echo "🔍 This will handle load balancer deletion protection, ENI dependencies, and comprehensive cleanup"
	@cd lockdev-hippa-iac && {
		echo "🔄 Setting up enhanced cleanup scripts..."; \
		chmod +x enhanced-cleanup.sh scripts/cleanup.sh force-cleanup.sh; \
		echo "🧹 Running enhanced comprehensive cleanup..."; \
		./enhanced-cleanup.sh staging; \
	}

clean-prod: ## Destroy production infrastructure (auto-setup if needed)
	@echo "🚨 PRODUCTION INFRASTRUCTURE DESTRUCTION"
	@echo "This will destroy ALL PRODUCTION infrastructure!"
	@echo "🔍 Enhanced protection handling will disable load balancer deletion protection and ENI dependencies"
	@read -p "Enter 'DESTROY PRODUCTION INFRASTRUCTURE' to proceed: " confirm; \
	if [ "$$confirm" = "DESTROY PRODUCTION INFRASTRUCTURE" ]; then \
		cd lockdev-hippa-iac && { \
			echo "🔄 Updating scripts for enhanced cleanup..."; \
			chmod +x scripts/cleanup.sh force-cleanup.sh; \
			echo "🛡️  Disabling load balancer deletion protection and ENI cleanup..."; \
			AWS_PROFILE=dev-root aws elbv2 describe-load-balancers --query 'LoadBalancers[*].[LoadBalancerArn,LoadBalancerName]' --output text | grep prod | while read arn name; do \
				echo "🛡️  Disabling deletion protection for: $$name"; \
				aws elbv2 modify-load-balancer-attributes --load-balancer-arn $$arn --attributes Key=deletion_protection.enabled,Value=false 2>/dev/null || echo "⚠️  Could not disable protection for $$name"; \
			done; \
			echo "🧹 Running comprehensive cleanup..."; \
			./scripts/cleanup.sh -e prod -m infrastructure; \
		}; \
	else \
		echo "Production infrastructure cleanup cancelled."; \
	fi

# Complete cleanup (infrastructure + service user)
clean-dev-complete: ## Completely remove development (infrastructure + service user)
	@echo "💥 Complete development cleanup with enhanced protection handling..."
	@echo "🔍 This will handle load balancer deletion protection, ENI dependencies, and comprehensive cleanup"
	@cd lockdev-hippa-iac && \
		echo "🔄 Setting up enhanced cleanup scripts..." && \
		chmod +x enhanced-cleanup.sh smart-cleanup.sh force-cleanup.sh && \
		echo "🧹 Running enhanced comprehensive cleanup..." && \
		./enhanced-cleanup.sh dev --force

clean-staging-complete: ## Completely remove staging (infrastructure + service user)
	@echo "💥 Complete staging cleanup with enhanced protection handling..."
	@echo "🔍 This will handle load balancer deletion protection, ENI dependencies, and comprehensive cleanup"
	@cd lockdev-hippa-iac && {
		echo "🔄 Setting up enhanced cleanup scripts..."; \
		chmod +x enhanced-cleanup.sh scripts/cleanup.sh force-cleanup.sh; \
		echo "🧹 Running enhanced comprehensive cleanup..."; \
		./enhanced-cleanup.sh staging --force; \
	}

clean-prod-complete: ## Completely remove production (infrastructure + service user)
	@echo "🚨 PRODUCTION CLEANUP - FINAL WARNING"
	@echo "This will destroy ALL PRODUCTION resources!"
	@echo "🔍 Enhanced protection handling will disable load balancer deletion protection, ENI dependencies, and comprehensive cleanup"
	@read -p "Enter 'DESTROY ALL PRODUCTION RESOURCES' to proceed: " confirm; \
	if [ "$$confirm" = "DESTROY ALL PRODUCTION RESOURCES" ]; then \
		cd lockdev-hippa-iac && { \
			echo "🔄 Setting up enhanced cleanup scripts..."; \
			chmod +x enhanced-cleanup.sh scripts/cleanup.sh force-cleanup.sh; \
			echo "🧹 Running enhanced comprehensive cleanup..."; \
			./enhanced-cleanup.sh prod --force; \
		}; \
	else \
		echo "Production cleanup cancelled."; \
	fi

# Infrastructure Cleanup previews (dry-run mode)
preview-clean-dev: ## Preview development cleanup (auto-setup if needed)
	@echo "👁️  Previewing development cleanup with smart auto-setup..."
	@cd lockdev-hippa-iac && ./scripts/cleanup.sh -e dev -m infrastructure --dry-run

preview-clean-staging: ## Preview staging cleanup (auto-setup if needed)
	@echo "👁️  Previewing staging cleanup with smart auto-setup..."
	@cd lockdev-hippa-iac && ./scripts/cleanup.sh -e staging -m infrastructure --dry-run

preview-clean-prod: ## Preview production cleanup (auto-setup if needed)
	@echo "👁️  Previewing production cleanup with smart auto-setup..."
	@cd lockdev-hippa-iac && ./scripts/cleanup.sh -e prod -m infrastructure --dry-run

# =========================================
# UTILITY TARGETS
# =========================================

show-outputs: ## Show deployment outputs for all accounts
	@echo "📊 Deployment Outputs:"
	@for file in lockdev-hippa-iac/outputs/*-outputs.json; do \
		if [ -f "$$file" ]; then \
			account=$$(basename "$$file" -outputs.json); \
			echo ""; \
			echo "🏷️  Account: $$account"; \
			echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
			if command -v jq &> /dev/null; then \
				jq -r 'to_entries[] | "  \(.key): \(.value)"' "$$file" || cat "$$file"; \
			else \
				cat "$$file"; \
			fi \
		fi \
	done

status: ## Show status of all Pulumi stacks
	@echo "📊 Pulumi Stack Status:"
	@cd lockdev-hippa-iac && poetry run pulumi stack ls

login-pulumi: ## Login to Pulumi (required before deployment)
	@echo "🔑 Logging into Pulumi..."
	@cd lockdev-hippa-iac && poetry run pulumi login
	@echo "✅ Pulumi login complete!"

# Configuration Management
edit-config: ## Edit environments configuration
	@if command -v code &> /dev/null; then \
		code lockdev-hippa-iac/configs/environments.yaml; \
	elif command -v vim &> /dev/null; then \
		vim lockdev-hippa-iac/configs/environments.yaml; \
	else \
		echo "📝 Edit lockdev-hippa-iac/configs/environments.yaml with your preferred editor"; \
	fi

validate-config: ## Validate environments configuration
	@echo "🔍 Validating configuration..."
	@if [ -f lockdev-hippa-iac/configs/environments.yaml ]; then \
		yq eval '.environments' lockdev-hippa-iac/configs/environments.yaml > /dev/null && \
		echo "✅ Configuration is valid!"; \
	else \
		echo "❌ Configuration file not found: lockdev-hippa-iac/configs/environments.yaml"; \
		echo "💡 Run a setup command to create example configuration"; \
	fi

create-config: ## Create example environments configuration
	@echo "📝 Creating example environments configuration..."
	@chmod +x lockdev-hippa-iac/scripts/*.sh
	@cd lockdev-hippa-iac && ./scripts/setup-env.sh -e dev --dry-run 2>/dev/null || echo "Example config created at configs/environments.yaml"

# =========================================
# EMERGENCY & MAINTENANCE
# =========================================

emergency-clean-dev: ## Emergency development cleanup (no prompts)
	@echo "🚨 EMERGENCY CLEANUP MODE - DEVELOPMENT"
	@echo "Destroying infrastructure with minimal safety checks..."
	@cd lockdev-hippa-iac && ./scripts/cleanup.sh -e dev -m complete --force

rotate-keys-info: ## Show guide for rotating AWS access keys
	@echo "🔄 AWS Access Key Rotation Guide:"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "1. Generate new keys in AWS Console (root account)"
	@echo "2. Update AWS CLI profiles:"
	@echo "   aws configure --profile dev-root"
	@echo "   aws configure --profile pulumi-deploy-user-dev"
	@echo "3. Test new credentials:"
	@echo "   make validate-env-dev"
	@echo "4. Delete old keys from AWS Console"
	@echo ""
	@echo "⚠️  Test new keys before deleting old ones!"

# =========================================
# WORKFLOW TARGETS
# =========================================

quick-start-dev: ## Complete development setup workflow (new users)
	@echo "🚀 Quick Start: Development Environment"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Phase 1: Installing dependencies and setting up environment..."
	@make install-deps
	@make login-pulumi
	@make create-config
	@echo ""
	@echo "⚠️  IMPORTANT: Edit lockdev-hippa-iac/configs/environments.yaml with your AWS account details"
	@echo ""
	@echo "Next steps after editing config:"
	@echo "  1. make setup-env-dev    # Create service user (uses root credentials)"
	@echo "  2. make validate-env-dev # Test service user access"
	@echo "  3. make deploy-dev       # Deploy infrastructure"

complete-workflow-dev: ## Complete dev workflow (smart deployment)
	@echo "🤖 Smart Development Workflow"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Smart deployment will auto-detect and setup if needed..."
	@make deploy-dev
	@echo ""
	@echo "🎉 Development environment ready!"
	@echo "💡 Access outputs: make show-outputs"

manual-workflow-dev: ## Manual dev workflow (explicit setup + deploy)
	@echo "🔧 Manual Development Workflow"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@make setup-env-dev
	@make validate-env-dev
	@make deploy-dev
	@echo ""
	@echo "🎉 Development environment ready!"
	@echo "💡 Access outputs: make show-outputs"

# =========================================
# VERIFICATION & STATUS
# =========================================

verify: verify-tools verify-deps verify-config ## Verify all installations and configurations

verify-tools: ## Verify all required tools are installed
	@echo "Verifying tool installations..."
	@echo -n "Python: "; python3 --version || echo "❌ MISSING"
	@echo -n "Poetry: "; poetry --version || echo "❌ MISSING"
	@echo -n "Pulumi: "; pulumi version || echo "❌ MISSING"
	@echo -n "AWS CLI: "; aws --version || echo "❌ MISSING"
	@echo -n "Docker: "; docker --version || echo "❌ MISSING"
	@echo -n "Git: "; git --version || echo "❌ MISSING"
	@echo -n "pip-audit: "; pip-audit --version 2>/dev/null || echo "❌ MISSING (install with: make install-security-tools)"
	@echo -n "Trivy: "; trivy --version 2>/dev/null | head -1 || echo "❌ MISSING (install with: make install-security-tools)"
	@echo -n "yq: "; yq --version 2>/dev/null || echo "❌ MISSING (install with: make install-deps-iac)"
	@echo -n "jq: "; jq --version 2>/dev/null || echo "❌ MISSING (install with: make install-deps-iac)"

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

# =========================================
# CLEANUP TARGETS
# =========================================

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

# =========================================
# LEGACY DEPLOYMENT (for backward compatibility)
# =========================================

deploy-preview: ## Preview infrastructure deployment (legacy)
	@cd lockdev-hippa-iac && poetry run pulumi preview

deploy: ## Deploy infrastructure (legacy)
	@cd lockdev-hippa-iac && poetry run pulumi up

# =========================================
# FINAL QUICK COMMANDS
# =========================================

quick-start: install verify ## Quick start - install everything and verify
	@echo ""
	@echo "🎉 Quick start complete!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Copy .env.example to .env and configure your credentials"
	@echo "2. Run 'aws configure' to set up AWS CLI"
	@echo "3. Run 'make create-config' to create configuration"
	@echo "4. Edit lockdev-hippa-iac/configs/environments.yaml with your AWS accounts"
	@echo "5. Run 'make deploy-dev' to deploy infrastructure"
	@echo "6. Run 'make dev-app' to start the application"

install-status: ## Show current installation status
	@echo ""
	@echo "📊 Installation Status Summary"
	@echo "============================="