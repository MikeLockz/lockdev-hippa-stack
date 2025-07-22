#!/bin/bash

# HIPAA Infrastructure Deployment with IAM Separation
# Uses credentials from CloudFormation bootstrap for secure deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-"test"}
PROJECT_NAME="hipaa"
BOOTSTRAP_STACK="hipaa-iam-bootstrap-${ENVIRONMENT}"

echo -e "${GREEN}🚀 HIPAA Infrastructure Deployment with IAM Separation${NC}"
echo -e "${BLUE}Environment: ${ENVIRONMENT}${NC}"
echo ""

# Check if bootstrap stack exists
echo -e "${YELLOW}🔍 Checking bootstrap stack...${NC}"
if ! aws cloudformation describe-stacks --stack-name "$BOOTSTRAP_STACK" >/dev/null 2>&1; then
    echo -e "${RED}❌ Bootstrap stack not found. Run bootstrap/deploy-bootstrap.sh first${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Bootstrap stack found${NC}"

# Get IAM Manager credentials from Secrets Manager
echo -e "${YELLOW}🔑 Retrieving IAM Manager credentials...${NC}"
SECRET_ARN=$(aws cloudformation describe-stacks \
    --stack-name "$BOOTSTRAP_STACK" \
    --query 'Stacks[0].Outputs[?OutputKey==`SecretsManagerArn`].OutputValue' \
    --output text)

if [ -z "$SECRET_ARN" ]; then
    echo -e "${RED}❌ Could not find Secrets Manager ARN from bootstrap stack${NC}"
    exit 1
fi

# Get credentials from Secrets Manager
IAM_CREDS=$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_ARN" \
    --query 'SecretString' \
    --output text)

IAM_ACCESS_KEY=$(echo $IAM_CREDS | jq -r '.AccessKeyId')
IAM_SECRET_KEY=$(echo $IAM_CREDS | jq -r '.SecretAccessKey')

if [ -z "$IAM_ACCESS_KEY" ] || [ "$IAM_ACCESS_KEY" = "null" ]; then
    echo -e "${RED}❌ Could not extract IAM Manager credentials${NC}"
    exit 1
fi

# Save current infrastructure credentials
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo -e "${RED}❌ Infrastructure user credentials not set in environment${NC}"
    echo "Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY for pulumi-deploy-user"
    exit 1
fi

INFRA_ACCESS_KEY=$AWS_ACCESS_KEY_ID
INFRA_SECRET_KEY=$AWS_SECRET_ACCESS_KEY

echo -e "${GREEN}✅ Retrieved credentials for both IAM Manager and Infrastructure user${NC}"
echo ""

# Phase 1: Deploy IAM resources with IAM Manager
echo -e "${YELLOW}📋 Phase 1: Deploying IAM Resources${NC}"
echo -e "${BLUE}Using IAM Manager credentials...${NC}"

# Switch to IAM manager credentials
export AWS_ACCESS_KEY_ID=$IAM_ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=$IAM_SECRET_KEY

# Create IAM-only stack file dynamically
cat > __main_iam_only__.py << 'EOF'
"""
HIPAA Infrastructure - IAM Resources Only
This program deploys only IAM-related resources using separated credentials.
"""

import pulumi
from src.security.iam import create_iam_roles
from src.security.kms import create_kms_key

# Create KMS key (needed for other services)
kms_key, kms_alias = create_kms_key()

# Create all IAM roles and policies
iam_resources = create_iam_roles(kms_key)

# Export key IAM outputs for infrastructure stack
pulumi.export("kms_key_id", kms_key.id)
pulumi.export("kms_key_arn", kms_key.arn)
pulumi.export("ecs_task_execution_role_arn", iam_resources["ecs_task_execution_role"].arn)
pulumi.export("ecs_task_role_arn", iam_resources["ecs_task_role"].arn)

# Export all IAM role ARNs for reference
for role_name, role in iam_resources.items():
    if hasattr(role, 'arn'):
        pulumi.export(f"{role_name}_arn", role.arn)
EOF

echo -e "${YELLOW}🚀 Deploying IAM resources...${NC}"
poetry run pulumi up --yes --program __main_iam_only__.py

echo -e "${GREEN}✅ Phase 1 Complete: IAM Resources Deployed${NC}"
echo ""

# Phase 2: Deploy infrastructure with infrastructure user
echo -e "${YELLOW}📋 Phase 2: Deploying Infrastructure Resources${NC}"
echo -e "${BLUE}Using Infrastructure credentials...${NC}"

# Switch back to infrastructure credentials
export AWS_ACCESS_KEY_ID=$INFRA_ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=$INFRA_SECRET_KEY

# Deploy main infrastructure (references existing IAM resources)
echo -e "${YELLOW}🚀 Deploying infrastructure resources...${NC}"
poetry run pulumi up --yes

echo -e "${GREEN}✅ Phase 2 Complete: Infrastructure Resources Deployed${NC}"
echo ""

# Display results
echo -e "${GREEN}🎉 Complete HIPAA Infrastructure Deployment Successful!${NC}"
echo ""
echo -e "${BLUE}📊 Infrastructure Outputs:${NC}"
poetry run pulumi stack output

# Cleanup temporary files
rm -f __main_iam_only__.py

echo ""
echo -e "${GREEN}✅ Deployment complete with IAM separation!${NC}"
echo -e "${BLUE}🔒 Security: IAM and Infrastructure managed by separate users${NC}"
echo -e "${YELLOW}💡 Tip: Save these outputs for application deployment${NC}"