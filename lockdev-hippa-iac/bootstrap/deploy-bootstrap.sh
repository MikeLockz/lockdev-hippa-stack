#!/bin/bash

# HIPAA Infrastructure Bootstrap Deployment
# One-time setup for IAM separation using CloudFormation
# This creates the foundation for repeatable Pulumi deployments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STACK_NAME="hipaa-iam-bootstrap"
ENVIRONMENT=${1:-"test"}
PROJECT_NAME="hipaa"
TEMPLATE_FILE="bootstrap/iam-bootstrap.yaml"

echo -e "${GREEN}🚀 HIPAA Infrastructure Bootstrap Deployment${NC}"
echo -e "${BLUE}Environment: ${ENVIRONMENT}${NC}"
echo -e "${BLUE}Stack Name: ${STACK_NAME}-${ENVIRONMENT}${NC}"
echo ""

# Validate template
echo -e "${YELLOW}📋 Validating CloudFormation template...${NC}"
aws cloudformation validate-template --template-body file://$TEMPLATE_FILE
echo -e "${GREEN}✅ Template validation successful${NC}"
echo ""

# Check if stack exists
echo -e "${YELLOW}🔍 Checking if stack exists...${NC}"
if aws cloudformation describe-stacks --stack-name "${STACK_NAME}-${ENVIRONMENT}" >/dev/null 2>&1; then
    echo -e "${YELLOW}📝 Stack exists, updating...${NC}"
    ACTION="update-stack"
    WAIT_CONDITION="stack-update-complete"
else
    echo -e "${YELLOW}📝 Stack does not exist, creating...${NC}"
    ACTION="create-stack"
    WAIT_CONDITION="stack-create-complete"
fi

# Deploy/Update stack
echo -e "${YELLOW}🚀 Deploying CloudFormation stack...${NC}"
aws cloudformation $ACTION \
    --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
    --template-body file://$TEMPLATE_FILE \
    --parameters \
        ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
        ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
    --capabilities CAPABILITY_NAMED_IAM \
    --tags \
        Key=Environment,Value=$ENVIRONMENT \
        Key=Project,Value=$PROJECT_NAME \
        Key=Purpose,Value=IAM-Bootstrap \
        Key=ManagedBy,Value=CloudFormation

# Wait for completion
echo -e "${YELLOW}⏳ Waiting for stack operation to complete...${NC}"
aws cloudformation wait $WAIT_CONDITION --stack-name "${STACK_NAME}-${ENVIRONMENT}"

# Get outputs
echo -e "${GREEN}✅ Bootstrap deployment complete!${NC}"
echo ""
echo -e "${BLUE}📊 Stack Outputs:${NC}"
aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

# Save credentials to file for automation
echo -e "${YELLOW}💾 Retrieving IAM Manager credentials...${NC}"
SECRET_ARN=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
    --query 'Stacks[0].Outputs[?OutputKey==`SecretsManagerArn`].OutputValue' \
    --output text)

if [ -n "$SECRET_ARN" ]; then
    aws secretsmanager get-secret-value \
        --secret-id "$SECRET_ARN" \
        --query 'SecretString' \
        --output text > iam-manager-credentials.json
    
    echo -e "${GREEN}✅ IAM Manager credentials saved to iam-manager-credentials.json${NC}"
    echo -e "${RED}⚠️  Keep this file secure and add to .gitignore!${NC}"
else
    echo -e "${RED}❌ Could not retrieve credentials from Secrets Manager${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Bootstrap Complete! Next Steps:${NC}"
echo -e "${BLUE}1. Attach infrastructure policy to pulumi-deploy-user:${NC}"
echo "   aws iam attach-user-policy --user-name pulumi-deploy-user --policy-arn \$(aws cloudformation describe-stacks --stack-name ${STACK_NAME}-${ENVIRONMENT} --query 'Stacks[0].Outputs[?OutputKey==\`InfrastructurePolicyArn\`].OutputValue' --output text)"
echo ""
echo -e "${BLUE}2. Deploy infrastructure with separated IAM:${NC}"
echo "   ./deploy-with-separation.sh $ENVIRONMENT"
echo ""
echo -e "${BLUE}3. Clean up bootstrap after successful deployment:${NC}"
echo "   aws cloudformation delete-stack --stack-name ${STACK_NAME}-${ENVIRONMENT}"