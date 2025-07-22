# HIPAA Infrastructure Multi-Account Deployment Makefile
# Manages dependencies, setup, and deployment across multiple AWS accounts

.PHONY: help install-deps setup-env check-deps test-accounts deploy-dev deploy-staging deploy-prod clean preview

# Default target
help: ## Show this help message
	@echo "HIPAA Multi-Account Infrastructure Deployment"
	@echo "============================================="
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Quick Start:"
	@echo "  make install-deps    # Install all dependencies"
	@echo "  make setup-env       # Setup AWS accounts and environment"
	@echo "  make deploy-dev      # Deploy to development account"
	@echo ""

# Dependency Management
install-deps: ## Install all required dependencies
	@echo "🔧 Installing dependencies..."
	@if ! command -v brew &> /dev/null; then \
		echo "❌ Homebrew not found. Please install: /bin/bash -c \"\$$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""; \
		exit 1; \
	fi
	@echo "📦 Installing system dependencies..."
	arch -arm64 brew install yq jq
	@if ! command -v pulumi &> /dev/null; then \
		echo "📦 Installing Pulumi..."; \
		curl -fsSL https://get.pulumi.com | sh; \
		echo "⚠️  Add to PATH: export PATH=\"\$$HOME/.pulumi/bin:\$$PATH\""; \
	fi
	@if ! command -v poetry &> /dev/null; then \
		echo "📦 Installing Poetry..."; \
		curl -sSL https://install.python-poetry.org | python3 -; \
		echo "⚠️  Add to PATH: export PATH=\"\$$HOME/.local/bin:\$$PATH\""; \
	fi
	@if ! command -v aws &> /dev/null; then \
		echo "📦 Installing AWS CLI..."; \
		arch -arm64 brew install awscli; \
	fi
	@echo "📦 Installing Python dependencies..."
	poetry install
	@echo "✅ All dependencies installed!"

check-deps: ## Check if all dependencies are installed
	@echo "🔍 Checking dependencies..."
	@for tool in pulumi aws poetry yq jq; do \
		if command -v $$tool &> /dev/null; then \
			echo "✅ $$tool: $$(which $$tool)"; \
		else \
			echo "❌ $$tool: not found"; \
			exit 1; \
		fi \
	done
	@echo "✅ All dependencies found!"

# Environment Setup
setup-env: check-deps ## Setup AWS accounts and environment
	@echo "🔧 Setting up AWS accounts and environment..."
	@chmod +x scripts/*.sh
	@echo "📋 Setting up AWS account profiles..."
	./scripts/setup-accounts.sh
	@echo "✅ Environment setup complete!"

test-accounts: ## Test access to all configured AWS accounts
	@echo "🔍 Testing AWS account access..."
	./scripts/setup-accounts.sh --test

list-profiles: ## List configured AWS profiles
	@echo "📋 AWS Profiles:"
	./scripts/setup-accounts.sh --list

# Deployment Targets
preview: ## Preview infrastructure changes for all accounts
	@echo "👁️  Previewing infrastructure changes..."
	./scripts/multi-account-deploy.sh --preview

preview-dev: ## Preview infrastructure changes for dev account
	@echo "👁️  Previewing dev account changes..."
	./scripts/multi-account-deploy.sh --preview --force dev

deploy-dev: check-deps ## Deploy to development account
	@echo "🚀 Deploying to development account..."
	./scripts/multi-account-deploy.sh --force dev

deploy-staging: check-deps ## Deploy to staging account  
	@echo "🚀 Deploying to staging account..."
	./scripts/multi-account-deploy.sh staging

deploy-prod: check-deps ## Deploy to production accounts
	@echo "🚀 Deploying to production accounts..."
	./scripts/multi-account-deploy.sh prod-us prod-eu

deploy-all: check-deps ## Deploy to all configured accounts
	@echo "🚀 Deploying to all accounts..."
	./scripts/multi-account-deploy.sh

# Specific account deployments
deploy-to: check-deps ## Deploy to specific account (usage: make deploy-to ACCOUNT=dev)
	@if [ -z "$(ACCOUNT)" ]; then \
		echo "❌ Please specify account: make deploy-to ACCOUNT=dev"; \
		exit 1; \
	fi
	@echo "🚀 Deploying to $(ACCOUNT) account..."
	./scripts/multi-account-deploy.sh $(ACCOUNT)

# Cleanup Targets
clean-dev: ## Safely destroy development infrastructure
	@echo "💥 Destroying development infrastructure..."
	./scripts/cleanup-accounts.sh dev

clean-staging: ## Safely destroy staging infrastructure
	@echo "💥 Destroying staging infrastructure..."
	./scripts/cleanup-accounts.sh staging

clean-all: ## Safely destroy all infrastructure (DANGEROUS)
	@echo "💥 Destroying ALL infrastructure..."
	@echo "⚠️  This will destroy infrastructure in ALL accounts!"
	@read -p "Are you sure? Type 'destroy-all' to confirm: " confirm; \
	if [ "$$confirm" = "destroy-all" ]; then \
		./scripts/cleanup-accounts.sh; \
	else \
		echo "Cancelled."; \
	fi

preview-cleanup: ## Preview what would be destroyed (dry-run)
	@echo "👁️  Previewing infrastructure cleanup..."
	./scripts/cleanup-accounts.sh --dry-run

# Utility Targets
show-outputs: ## Show deployment outputs for all accounts
	@echo "📊 Deployment Outputs:"
	@for file in outputs/*-outputs.json; do \
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
	poetry run pulumi stack ls

login-pulumi: ## Login to Pulumi (required before deployment)
	@echo "🔑 Logging into Pulumi..."
	poetry run pulumi login
	@echo "✅ Pulumi login complete!"

# Development Targets
format: ## Format and lint all code
	@echo "🎨 Formatting code..."
	poetry run black src/
	poetry run flake8 src/

test: ## Run infrastructure tests
	@echo "🧪 Running tests..."
	poetry run pytest tests/ -v

security-scan: ## Run security scans
	@echo "🔒 Running security scans..."
	poetry run bandit -r src/
	poetry run safety check

# Configuration Management
edit-config: ## Edit accounts configuration
	@if command -v code &> /dev/null; then \
		code configs/accounts.yaml; \
	elif command -v vim &> /dev/null; then \
		vim configs/accounts.yaml; \
	else \
		echo "📝 Edit configs/accounts.yaml with your preferred editor"; \
	fi

validate-config: ## Validate accounts configuration
	@echo "🔍 Validating configuration..."
	yq eval '.accounts' configs/accounts.yaml > /dev/null
	@echo "✅ Configuration is valid!"

# Documentation
docs: ## Open documentation
	@echo "📚 Opening documentation..."
	@if command -v open &> /dev/null; then \
		open README-multi-account.md; \
	else \
		echo "📖 Read README-multi-account.md for detailed documentation"; \
	fi

# Emergency Targets
emergency-cleanup: ## Emergency cleanup with minimal prompts
	@echo "🚨 EMERGENCY CLEANUP MODE"
	@echo "This will destroy infrastructure with minimal safety checks!"
	@read -p "Enter 'EMERGENCY' to continue: " confirm; \
	if [ "$$confirm" = "EMERGENCY" ]; then \
		./scripts/cleanup-accounts.sh --force --confirm "emergency"; \
	else \
		echo "Cancelled."; \
	fi

rotate-keys: ## Guide for rotating AWS access keys
	@echo "🔄 AWS Access Key Rotation Guide:"
	./scripts/setup-accounts.sh --rotate

# Version and Info
version: ## Show versions of all tools
	@echo "🔍 Tool Versions:"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Pulumi:  $$(pulumi version 2>/dev/null || echo 'not installed')"
	@echo "AWS CLI: $$(aws --version 2>/dev/null || echo 'not installed')"
	@echo "Poetry:  $$(poetry --version 2>/dev/null || echo 'not installed')"
	@echo "yq:      $$(yq --version 2>/dev/null || echo 'not installed')"
	@echo "jq:      $$(jq --version 2>/dev/null || echo 'not installed')"
	@echo "Python:  $$(python3 --version 2>/dev/null || echo 'not installed')"

info: ## Show project information
	@echo "📋 HIPAA Multi-Account Infrastructure"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Project: HIPAA-compliant infrastructure across multiple AWS accounts"
	@echo "Config:  configs/accounts.yaml"
	@echo "Outputs: outputs/"
	@echo "Scripts: scripts/"
	@echo ""
	@if [ -f configs/accounts.yaml ]; then \
		echo "Configured accounts:"; \
		yq eval '.accounts | keys | .[]' configs/accounts.yaml | sed 's/^/  - /'; \
	else \
		echo "⚠️  No accounts configured yet. Run 'make setup-env'"; \
	fi

# Quick Setup for New Users
quick-start: ## Complete setup and deploy to dev (new users)
	@echo "🚀 Quick Start Setup"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	make install-deps
	make login-pulumi
	make setup-env
	make test-accounts
	@echo ""
	@echo "🎉 Setup complete! Ready to deploy."
	@echo "💡 Next step: make deploy-dev"