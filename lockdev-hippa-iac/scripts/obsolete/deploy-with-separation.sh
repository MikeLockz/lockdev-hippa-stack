#!/bin/bash

# HIPAA Infrastructure Two-Phase Deployment
# Phase 1: Deploy IAM resources with IAM-manager user
# Phase 2: Deploy infrastructure with infrastructure-only user

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting HIPAA Infrastructure Deployment with IAM Separation${NC}"
echo ""

# Check if we have both sets of credentials
if [ ! -f "iam-manager-keys.json" ]; then
    echo -e "${RED}❌ iam-manager-keys.json not found. Run setup-iam-separation.sh first${NC}"
    exit 1
fi

# Extract IAM manager credentials
IAM_ACCESS_KEY=$(jq -r '.AccessKey.AccessKeyId' iam-manager-keys.json)
IAM_SECRET_KEY=$(jq -r '.AccessKey.SecretAccessKey' iam-manager-keys.json)

if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo -e "${RED}❌ Infrastructure user credentials not set in environment${NC}"
    echo "Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY for pulumi-deploy-user"
    exit 1
fi

# Save current credentials
INFRA_ACCESS_KEY=$AWS_ACCESS_KEY_ID
INFRA_SECRET_KEY=$AWS_SECRET_ACCESS_KEY

echo -e "${YELLOW}📋 Phase 1: Deploying IAM Resources${NC}"
echo "Using pulumi-iam-manager credentials..."

# Switch to IAM manager credentials
export AWS_ACCESS_KEY_ID=$IAM_ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=$IAM_SECRET_KEY

# Create IAM-only Pulumi program
cat > __main_iam_only__.py << 'EOF'
"""
HIPAA Infrastructure - IAM Resources Only
This program deploys only IAM-related resources.
"""

import pulumi
from src.security.iam import create_iam_roles
from src.security.kms import create_kms_key

# Create KMS key (needed for other services)
kms_key, kms_alias = create_kms_key()

# Create all IAM roles and policies
iam_resources = create_iam_roles(kms_key)

# Export key IAM outputs
pulumi.export("kms_key_id", kms_key.id)
pulumi.export("kms_key_arn", kms_key.arn)
pulumi.export("ecs_task_execution_role_arn", iam_resources["ecs_task_execution_role"].arn)
pulumi.export("ecs_task_role_arn", iam_resources["ecs_task_role"].arn)
EOF

# Deploy IAM resources
poetry run pulumi up --yes -f __main_iam_only__.py

echo -e "${GREEN}✅ Phase 1 Complete: IAM Resources Deployed${NC}"
echo ""
echo -e "${YELLOW}📋 Phase 2: Deploying Infrastructure Resources${NC}"
echo "Using pulumi-deploy-user credentials..."

# Switch back to infrastructure credentials
export AWS_ACCESS_KEY_ID=$INFRA_ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=$INFRA_SECRET_KEY

# Deploy main infrastructure (without IAM creation)
poetry run pulumi up --yes

echo -e "${GREEN}✅ Phase 2 Complete: Infrastructure Resources Deployed${NC}"
echo ""
echo -e "${GREEN}🎉 Full HIPAA Infrastructure Deployment Complete!${NC}"
echo ""
echo "Outputs:"
poetry run pulumi stack output

# Cleanup temporary files
rm -f __main_iam_only__.py