#!/bin/bash

# Multi-Account HIPAA Infrastructure Deployment
# Deploys identical infrastructure across multiple AWS accounts
# Uses root user credentials for maximum repeatability

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUTS_DIR="$PROJECT_DIR/outputs"
ACCOUNTS_CONFIG="$PROJECT_DIR/configs/accounts.yaml"

# Create outputs directory
mkdir -p "$OUTPUTS_DIR"

# Help function
show_help() {
    echo -e "${GREEN}Multi-Account HIPAA Infrastructure Deployment${NC}"
    echo ""
    echo "Usage: $0 [OPTIONS] [ACCOUNTS...]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -c, --config FILE       Accounts configuration file (default: configs/accounts.yaml)"
    echo "  -o, --outputs-dir DIR   Directory for deployment outputs (default: outputs/)"
    echo "  -d, --destroy           Destroy infrastructure instead of deploy"
    echo "  -p, --preview           Preview changes only (no deployment)"
    echo "  -f, --force             Skip confirmation prompts"
    echo "  --stack-prefix PREFIX   Prefix for Pulumi stack names (default: hipaa)"
    echo ""
    echo "Examples:"
    echo "  $0 dev staging prod              # Deploy to specific accounts"
    echo "  $0 --destroy dev                 # Destroy dev account infrastructure"
    echo "  $0 --preview --config accounts.yaml  # Preview all accounts from config"
    echo ""
    echo "Account Configuration (configs/accounts.yaml):"
    echo "accounts:"
    echo "  dev:"
    echo "    profile: dev-root"
    echo "    region: us-east-1"
    echo "    environment: development"
    echo "  prod:"
    echo "    profile: prod-root"
    echo "    region: us-west-2"
    echo "    environment: production"
}

# Default values
DESTROY=false
PREVIEW=false
FORCE=false
STACK_PREFIX="hipaa"
SELECTED_ACCOUNTS=()

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -c|--config)
            ACCOUNTS_CONFIG="$2"
            shift 2
            ;;
        -o|--outputs-dir)
            OUTPUTS_DIR="$2"
            shift 2
            ;;
        -d|--destroy)
            DESTROY=true
            shift
            ;;
        -p|--preview)
            PREVIEW=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        --stack-prefix)
            STACK_PREFIX="$2"
            shift 2
            ;;
        -*)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
        *)
            SELECTED_ACCOUNTS+=("$1")
            shift
            ;;
    esac
done

# Function to check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}🔍 Checking prerequisites...${NC}"
    
    # Check if we're in the right directory
    if [[ ! -f "$PROJECT_DIR/Pulumi.yaml" ]]; then
        echo -e "${RED}❌ Not in Pulumi project directory. Run from lockdev-hippa-iac/${NC}"
        exit 1
    fi
    
    # Check required tools
    local tools=("pulumi" "aws" "poetry" "yq")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            echo -e "${RED}❌ Required tool not found: $tool${NC}"
            exit 1
        fi
    done
    
    # Check if logged into Pulumi
    if ! pulumi whoami &> /dev/null; then
        echo -e "${RED}❌ Not logged into Pulumi. Run 'pulumi login'${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Prerequisites check passed${NC}"
}

# Function to load account configuration
load_accounts_config() {
    if [[ ! -f "$ACCOUNTS_CONFIG" ]]; then
        echo -e "${YELLOW}⚠️  Accounts config not found: $ACCOUNTS_CONFIG${NC}"
        echo -e "${BLUE}Creating example configuration...${NC}"
        create_example_config
        return 1
    fi
    
    # If no accounts specified, load all from config
    if [[ ${#SELECTED_ACCOUNTS[@]} -eq 0 ]]; then
        SELECTED_ACCOUNTS=($(yq eval '.accounts | keys | .[]' "$ACCOUNTS_CONFIG"))
    fi
    
    echo -e "${GREEN}✅ Loaded configuration for ${#SELECTED_ACCOUNTS[@]} accounts${NC}"
}

# Function to create example accounts configuration
create_example_config() {
    mkdir -p "$(dirname "$ACCOUNTS_CONFIG")"
    cat > "$ACCOUNTS_CONFIG" << 'EOF'
# Multi-Account HIPAA Infrastructure Configuration
# Configure AWS profiles and deployment settings for each account

accounts:
  dev:
    profile: dev-root
    region: us-east-1
    environment: development
    tags:
      CostCenter: "Development"
      Owner: "DevTeam"
    
  staging:
    profile: staging-root
    region: us-east-1
    environment: staging
    tags:
      CostCenter: "QA"
      Owner: "QATeam"
    
  prod-us:
    profile: prod-us-root
    region: us-east-1
    environment: production
    tags:
      CostCenter: "Production"
      Owner: "OpsTeam"
      Region: "US"
    
  prod-eu:
    profile: prod-eu-root
    region: eu-west-1
    environment: production
    tags:
      CostCenter: "Production"
      Owner: "OpsTeam"
      Region: "EU"

# Global settings
global:
  stack_prefix: hipaa
  pulumi_backend: pulumi.com  # or s3://your-bucket
  confirm_destroy: true
EOF
    
    echo -e "${GREEN}✅ Created example configuration: $ACCOUNTS_CONFIG${NC}"
    echo -e "${BLUE}Please edit this file with your account details and run again${NC}"
}

# Function to get account configuration
get_account_config() {
    local account=$1
    local key=$2
    yq eval ".accounts.$account.$key" "$ACCOUNTS_CONFIG"
}

# Function to validate account access
validate_account_access() {
    local account=$1
    local profile=$(get_account_config "$account" "profile")
    local region=$(get_account_config "$account" "region")
    
    echo -e "${YELLOW}🔐 Validating access to account: $account (profile: $profile)${NC}"
    
    # Test AWS access
    if ! AWS_PROFILE="$profile" AWS_DEFAULT_REGION="$region" aws sts get-caller-identity &> /dev/null; then
        echo -e "${RED}❌ Cannot access AWS account with profile: $profile${NC}"
        echo -e "${BLUE}💡 Configure credentials: aws configure --profile $profile${NC}"
        return 1
    fi
    
    local account_id=$(AWS_PROFILE="$profile" AWS_DEFAULT_REGION="$region" aws sts get-caller-identity --query Account --output text)
    echo -e "${GREEN}✅ Access validated for account: $account_id${NC}"
    return 0
}

# Function to deploy to single account
deploy_account() {
    local account=$1
    local profile=$(get_account_config "$account" "profile")
    local region=$(get_account_config "$account" "region")
    local environment=$(get_account_config "$account" "environment")
    
    echo -e "${CYAN}================================================${NC}"
    echo -e "${CYAN}🚀 Deploying to Account: $account${NC}"
    echo -e "${CYAN}================================================${NC}"
    echo -e "${BLUE}Profile: $profile${NC}"
    echo -e "${BLUE}Region: $region${NC}"
    echo -e "${BLUE}Environment: $environment${NC}"
    echo ""
    
    local stack_name="${STACK_PREFIX}-${account}"
    
    # Set environment variables
    export AWS_PROFILE="$profile"
    export AWS_DEFAULT_REGION="$region"
    export PULUMI_CONFIG_PASSPHRASE=""
    
    # Create or select stack
    echo -e "${YELLOW}📋 Preparing Pulumi stack: $stack_name${NC}"
    
    if poetry run pulumi stack ls | grep -q "^$stack_name"; then
        poetry run pulumi stack select "$stack_name"
        echo -e "${GREEN}✅ Selected existing stack: $stack_name${NC}"
    else
        poetry run pulumi stack init "$stack_name"
        echo -e "${GREEN}✅ Created new stack: $stack_name${NC}"
    fi
    
    # Set stack configuration
    poetry run pulumi config set aws:region "$region"
    poetry run pulumi config set environment "$environment"
    poetry run pulumi config set account "$account"
    
    # Set tags from configuration (skip for now due to provider config issues)
    # local tags=$(yq eval ".accounts.$account.tags // {}" "$ACCOUNTS_CONFIG" -o json)
    # if [[ "$tags" != "null" && "$tags" != "{}" ]]; then
    #     # Set tags using the correct AWS provider format
    #     poetry run pulumi config set aws:defaultTags "$tags"
    # fi
    
    # Preview or deploy
    if [[ "$PREVIEW" == true ]]; then
        echo -e "${YELLOW}👁️  Previewing changes for $account...${NC}"
        poetry run pulumi preview
    elif [[ "$DESTROY" == true ]]; then
        echo -e "${YELLOW}💥 Destroying infrastructure for $account...${NC}"
        if [[ "$FORCE" == true ]]; then
            poetry run pulumi destroy --yes
        else
            poetry run pulumi destroy
        fi
        echo -e "${GREEN}✅ Destruction complete for $account${NC}"
    else
        echo -e "${YELLOW}🚀 Deploying infrastructure for $account...${NC}"
        if [[ "$FORCE" == true ]]; then
            poetry run pulumi up --yes
        else
            poetry run pulumi up
        fi
        
        # Save outputs
        local output_file="$OUTPUTS_DIR/${account}-outputs.json"
        poetry run pulumi stack output --json > "$output_file"
        echo -e "${GREEN}✅ Deployment complete for $account${NC}"
        echo -e "${BLUE}📊 Outputs saved to: $output_file${NC}"
    fi
    
    echo ""
}

# Function to display summary
display_summary() {
    echo -e "${CYAN}================================================${NC}"
    echo -e "${CYAN}📊 Deployment Summary${NC}"
    echo -e "${CYAN}================================================${NC}"
    
    for account in "${SELECTED_ACCOUNTS[@]}"; do
        local output_file="$OUTPUTS_DIR/${account}-outputs.json"
        if [[ -f "$output_file" ]]; then
            echo -e "${GREEN}✅ $account: Deployed successfully${NC}"
            
            # Show key outputs
            if command -v jq &> /dev/null; then
                local alb_dns=$(jq -r '.alb_dns_name // "N/A"' "$output_file")
                local ecr_url=$(jq -r '.ecr_repository_url // "N/A"' "$output_file")
                echo -e "${BLUE}   ALB DNS: $alb_dns${NC}"
                echo -e "${BLUE}   ECR URL: $ecr_url${NC}"
            fi
        else
            echo -e "${YELLOW}⚠️  $account: No outputs found${NC}"
        fi
    done
    
    echo ""
    echo -e "${GREEN}🎉 Multi-account deployment complete!${NC}"
    echo -e "${BLUE}📁 All outputs saved to: $OUTPUTS_DIR/${NC}"
}

# Main execution
main() {
    echo -e "${GREEN}🌟 Multi-Account HIPAA Infrastructure Deployment${NC}"
    echo ""
    
    # Check prerequisites
    check_prerequisites
    
    # Load configuration
    if ! load_accounts_config; then
        exit 1
    fi
    
    # Validate access to all accounts
    echo -e "${YELLOW}🔍 Validating access to all accounts...${NC}"
    for account in "${SELECTED_ACCOUNTS[@]}"; do
        if ! validate_account_access "$account"; then
            echo -e "${RED}❌ Validation failed for account: $account${NC}"
            exit 1
        fi
    done
    
    # Confirmation prompt
    if [[ "$FORCE" == false ]]; then
        echo ""
        echo -e "${YELLOW}📋 About to process ${#SELECTED_ACCOUNTS[@]} accounts:${NC}"
        printf "   %s\n" "${SELECTED_ACCOUNTS[@]}"
        echo ""
        
        if [[ "$DESTROY" == true ]]; then
            echo -e "${RED}⚠️  WARNING: This will DESTROY infrastructure in all selected accounts!${NC}"
        fi
        
        read -p "Continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}Deployment cancelled${NC}"
            exit 0
        fi
    fi
    
    # Change to project directory
    cd "$PROJECT_DIR"
    
    # Deploy to each account
    for account in "${SELECTED_ACCOUNTS[@]}"; do
        if ! deploy_account "$account"; then
            echo -e "${RED}❌ Deployment failed for account: $account${NC}"
            exit 1
        fi
    done
    
    # Display summary
    if [[ "$PREVIEW" == false && "$DESTROY" == false ]]; then
        display_summary
    fi
}

# Run main function
main "$@"