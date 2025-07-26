#!/bin/bash

# HIPAA Infrastructure IAM Separation Setup
# This script creates separate IAM users for IAM management and infrastructure deployment

set -e

echo "🔐 Setting up IAM separation for HIPAA infrastructure..."

# Create IAM management user
echo "📝 Creating IAM management user..."
aws iam create-user --user-name pulumi-iam-manager || echo "User already exists"

# Create IAM management policy
echo "📝 Creating IAM management policy..."
aws iam create-policy \
    --policy-name PulumiIAMManagerPolicy \
    --policy-document file://policies/iam-manager-policy.json \
    --description "Minimal IAM permissions for Pulumi IAM resource management" || echo "Policy already exists"

# Attach IAM policy to IAM user
echo "📝 Attaching IAM policy to IAM management user..."
aws iam attach-user-policy \
    --user-name pulumi-iam-manager \
    --policy-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/PulumiIAMManagerPolicy"

# Create infrastructure policy
echo "📝 Creating infrastructure policy..."
aws iam create-policy \
    --policy-name PulumiInfrastructurePolicy \
    --policy-document file://policies/infrastructure-policy.json \
    --description "Infrastructure permissions for Pulumi (no IAM)" || echo "Policy already exists"

# Attach infrastructure policy to existing user
echo "📝 Updating existing pulumi-deploy-user with infrastructure-only permissions..."
aws iam attach-user-policy \
    --user-name pulumi-deploy-user \
    --policy-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/PulumiInfrastructurePolicy"

# Create access keys for IAM user
echo "📝 Creating access keys for IAM management user..."
aws iam create-access-key --user-name pulumi-iam-manager > iam-manager-keys.json
echo "⚠️  IAM manager access keys saved to iam-manager-keys.json - KEEP SECURE!"

echo "✅ IAM separation setup complete!"
echo ""
echo "Next steps:"
echo "1. Save the IAM manager credentials securely"
echo "2. Update your deployment process to use both users"
echo "3. Test the deployment with the new setup"