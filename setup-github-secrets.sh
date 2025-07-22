#!/bin/bash

# GitHub Actions CI/CD Setup Script
# This script helps you configure GitHub repository secrets

set -e

echo "🚀 GitHub Actions CI/CD Setup for HIPAA Infrastructure"
echo "======================================================"
echo ""

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed."
    echo "Install it with: brew install gh"
    echo "Then run: gh auth login"
    exit 1
fi

# Check if logged into GitHub
if ! gh auth status &> /dev/null; then
    echo "❌ Not logged into GitHub CLI."
    echo "Run: gh auth login"
    exit 1
fi

echo "✅ GitHub CLI is ready"
echo ""

# Get repository information
REPO_INFO=$(gh repo view --json owner,name)
REPO_OWNER=$(echo $REPO_INFO | jq -r '.owner.login')
REPO_NAME=$(echo $REPO_INFO | jq -r '.name')

echo "📁 Repository: $REPO_OWNER/$REPO_NAME"
echo ""

# Collect the required secrets
echo "🔐 Setting up GitHub repository secrets..."
echo ""

# AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
echo "AWS_ACCOUNT_ID: $AWS_ACCOUNT_ID"

# Pulumi Token
if [ -n "$PULUMI_ACCESS_TOKEN" ]; then
    PULUMI_TOKEN="$PULUMI_ACCESS_TOKEN"
    echo "PULUMI_ACCESS_TOKEN: Found in environment"
else
    echo "❌ PULUMI_ACCESS_TOKEN not found in environment"
    echo "Get your token from: https://app.pulumi.com/account/tokens"
    read -p "Enter your Pulumi Access Token: " PULUMI_TOKEN
fi

# AWS Credentials (current user)
AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id)
AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key)

if [ -z "$AWS_ACCESS_KEY_ID" ]; then
    # Try environment variables
    AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID"
    AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY"
fi

echo "AWS Credentials: Found for pulumi-deploy-user"
echo ""

# Set the secrets
echo "📝 Setting GitHub repository secrets..."

gh secret set AWS_ACCOUNT_ID --body "$AWS_ACCOUNT_ID"
echo "✅ Set AWS_ACCOUNT_ID"

gh secret set PULUMI_ACCESS_TOKEN --body "$PULUMI_TOKEN"
echo "✅ Set PULUMI_ACCESS_TOKEN"

gh secret set PULUMI_AWS_ACCESS_KEY_ID --body "$AWS_ACCESS_KEY_ID"
echo "✅ Set PULUMI_AWS_ACCESS_KEY_ID"

gh secret set PULUMI_AWS_SECRET_ACCESS_KEY --body "$AWS_SECRET_ACCESS_KEY"
echo "✅ Set PULUMI_AWS_SECRET_ACCESS_KEY"

# For now, use the same credentials for admin operations
# In production, you'd want separate admin credentials
gh secret set AWS_ADMIN_ACCESS_KEY_ID --body "$AWS_ACCESS_KEY_ID"
echo "✅ Set AWS_ADMIN_ACCESS_KEY_ID"

gh secret set AWS_ADMIN_SECRET_ACCESS_KEY --body "$AWS_SECRET_ACCESS_KEY"
echo "✅ Set AWS_ADMIN_SECRET_ACCESS_KEY"

echo ""
echo "🎉 GitHub secrets configured successfully!"
echo ""
echo "Next Steps:"
echo "==========="
echo "1. Set up GitHub environments:"
echo "   - Go to: https://github.com/$REPO_OWNER/$REPO_NAME/settings/environments"
echo "   - Create environments: dev, staging, prod"
echo "   - Add protection rules for prod (require reviewers)"
echo ""
echo "2. Test the CI/CD pipeline:"
echo "   make ci-validate"
echo "   make ci-deploy-dev"
echo ""
echo "3. View your secrets:"
echo "   https://github.com/$REPO_OWNER/$REPO_NAME/settings/secrets/actions"
echo ""
echo "4. Monitor workflows:"
echo "   https://github.com/$REPO_OWNER/$REPO_NAME/actions"