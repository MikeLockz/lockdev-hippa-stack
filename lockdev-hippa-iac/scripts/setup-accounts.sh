#!/bin/bash

# AWS Account Setup Script
# Helps configure AWS CLI profiles for multiple accounts
# Sets up root user credentials for multi-account deployment

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
ACCOUNTS_CONFIG="$PROJECT_DIR/configs/accounts.yaml"

# Help function
show_help() {
    echo -e "${GREEN}AWS Account Setup for Multi-Account Deployment${NC}"
    echo ""
    echo "This script helps you configure AWS CLI profiles for multiple accounts."
    echo "It guides you through setting up root user credentials for each account."
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -c, --config FILE       Accounts configuration file (default: configs/accounts.yaml)"
    echo "  -l, --list              List configured profiles"
    echo "  -t, --test              Test access to all configured accounts"
    echo "  -r, --rotate            Help rotate access keys for security"
    echo ""
    echo "Examples:"
    echo "  $0                      # Interactive setup for all accounts"
    echo "  $0 --list              # List current AWS profiles"
    echo "  $0 --test              # Test access to all accounts"
}

# Parse command line arguments
LIST_PROFILES=false
TEST_ACCESS=false
ROTATE_KEYS=false

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
        -l|--list)
            LIST_PROFILES=true
            shift
            ;;
        -t|--test)
            TEST_ACCESS=true
            shift
            ;;
        -r|--rotate)
            ROTATE_KEYS=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Function to check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}🔍 Checking prerequisites...${NC}"
    
    local tools=("aws" "yq")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            echo -e "${RED}❌ Required tool not found: $tool${NC}"
            if [[ "$tool" == "yq" ]]; then
                echo -e "${BLUE}💡 Install with: brew install yq${NC}"
            fi
            exit 1
        fi
    done
    
    echo -e "${GREEN}✅ Prerequisites check passed${NC}"
}

# Function to list AWS profiles
list_profiles() {
    echo -e "${CYAN}📋 Configured AWS Profiles${NC}"
    echo -e "${CYAN}=========================${NC}"
    
    if [[ -f ~/.aws/config ]]; then
        grep '^\[profile ' ~/.aws/config | sed 's/\[profile \(.*\)\]/\1/' | while read -r profile; do
            echo -e "${BLUE}📍 $profile${NC}"
            
            # Test if credentials exist
            if AWS_PROFILE="$profile" aws sts get-caller-identity &> /dev/null; then
                local account_id=$(AWS_PROFILE="$profile" aws sts get-caller-identity --query Account --output text 2>/dev/null)
                local region=$(AWS_PROFILE="$profile" aws configure get region 2>/dev/null || echo "Not set")
                echo -e "${GREEN}   ✅ Active (Account: $account_id, Region: $region)${NC}"
            else
                echo -e "${RED}   ❌ Invalid credentials${NC}"
            fi
            echo ""
        done
    else
        echo -e "${YELLOW}No AWS profiles configured${NC}"
    fi
}

# Function to test account access
test_account_access() {
    echo -e "${CYAN}🔍 Testing Account Access${NC}"
    echo -e "${CYAN}========================${NC}"
    
    if [[ ! -f "$ACCOUNTS_CONFIG" ]]; then
        echo -e "${RED}❌ Accounts config not found: $ACCOUNTS_CONFIG${NC}"
        echo -e "${BLUE}💡 Run the main deployment script first to create example config${NC}"
        exit 1
    fi
    
    local accounts=($(yq eval '.accounts | keys | .[]' "$ACCOUNTS_CONFIG"))
    
    for account in "${accounts[@]}"; do
        local profile=$(yq eval ".accounts.$account.profile" "$ACCOUNTS_CONFIG")
        local region=$(yq eval ".accounts.$account.region" "$ACCOUNTS_CONFIG")
        
        echo -e "${YELLOW}Testing $account (profile: $profile)...${NC}"
        
        if AWS_PROFILE="$profile" AWS_DEFAULT_REGION="$region" aws sts get-caller-identity &> /dev/null; then
            local account_id=$(AWS_PROFILE="$profile" AWS_DEFAULT_REGION="$region" aws sts get-caller-identity --query Account --output text)
            local user_arn=$(AWS_PROFILE="$profile" AWS_DEFAULT_REGION="$region" aws sts get-caller-identity --query Arn --output text)
            echo -e "${GREEN}   ✅ Success: $account_id${NC}"
            echo -e "${BLUE}   👤 User: $user_arn${NC}"
        else
            echo -e "${RED}   ❌ Failed: Cannot access account${NC}"
        fi
        echo ""
    done
}

# Function to setup account profile
setup_account_profile() {
    local account=$1
    local profile=$2
    local region=$3
    
    echo -e "${CYAN}🔧 Setting up profile: $profile${NC}"
    echo -e "${BLUE}Account: $account${NC}"
    echo -e "${BLUE}Region: $region${NC}"
    echo ""
    
    echo -e "${YELLOW}Please provide AWS root user credentials for this account:${NC}"
    echo -e "${RED}⚠️  Important: Use root user access keys (not IAM user)${NC}"
    echo -e "${BLUE}💡 Create access keys: AWS Console → Security Credentials → Access Keys${NC}"
    echo ""
    
    # Configure AWS profile
    aws configure --profile "$profile" set region "$region"
    
    read -p "AWS Access Key ID: " access_key
    read -s -p "AWS Secret Access Key: " secret_key
    echo ""
    
    aws configure --profile "$profile" set aws_access_key_id "$access_key"
    aws configure --profile "$profile" set aws_secret_access_key "$secret_key"
    
    # Test the configuration
    echo -e "${YELLOW}🔍 Testing profile configuration...${NC}"
    if AWS_PROFILE="$profile" aws sts get-caller-identity &> /dev/null; then
        local account_id=$(AWS_PROFILE="$profile" aws sts get-caller-identity --query Account --output text)
        echo -e "${GREEN}✅ Profile configured successfully!${NC}"
        echo -e "${BLUE}Account ID: $account_id${NC}"
        
        # Verify it's root user
        local user_arn=$(AWS_PROFILE="$profile" aws sts get-caller-identity --query Arn --output text)
        if [[ "$user_arn" == *":root" ]]; then
            echo -e "${GREEN}✅ Confirmed: Root user credentials${NC}"
        else
            echo -e "${YELLOW}⚠️  Warning: Not root user credentials${NC}"
            echo -e "${BLUE}ARN: $user_arn${NC}"
        fi
    else
        echo -e "${RED}❌ Configuration failed. Please check your credentials.${NC}"
        return 1
    fi
    
    echo ""
}

# Function to rotate access keys
rotate_access_keys() {
    echo -e "${CYAN}🔄 Access Key Rotation Guide${NC}"
    echo -e "${CYAN}============================${NC}"
    echo ""
    echo -e "${YELLOW}For security, regularly rotate your AWS access keys:${NC}"
    echo ""
    echo -e "${BLUE}1. Create new access key:${NC}"
    echo "   - Login to AWS Console as root user"
    echo "   - Go to Security Credentials"
    echo "   - Create new access key"
    echo ""
    echo -e "${BLUE}2. Update local configuration:${NC}"
    echo "   aws configure --profile PROFILE_NAME"
    echo ""
    echo -e "${BLUE}3. Test new credentials:${NC}"
    echo "   aws sts get-caller-identity --profile PROFILE_NAME"
    echo ""
    echo -e "${BLUE}4. Delete old access key:${NC}"
    echo "   - Return to AWS Console"
    echo "   - Delete the old access key"
    echo ""
    echo -e "${RED}⚠️  Important: Test new key before deleting old one!${NC}"
    echo ""
    
    if [[ -f "$ACCOUNTS_CONFIG" ]]; then
        echo -e "${YELLOW}Your configured profiles:${NC}"
        yq eval '.accounts[] | .profile' "$ACCOUNTS_CONFIG" | sort -u
    fi
}

# Function to interactive setup
interactive_setup() {
    echo -e "${GREEN}🚀 Interactive AWS Account Setup${NC}"
    echo ""
    
    if [[ ! -f "$ACCOUNTS_CONFIG" ]]; then
        echo -e "${RED}❌ Accounts config not found: $ACCOUNTS_CONFIG${NC}"
        echo -e "${BLUE}💡 Run the main deployment script first to create example config${NC}"
        exit 1
    fi
    
    local accounts=($(yq eval '.accounts | keys | .[]' "$ACCOUNTS_CONFIG"))
    
    echo -e "${BLUE}Found ${#accounts[@]} accounts in configuration:${NC}"
    printf "   %s\n" "${accounts[@]}"
    echo ""
    
    for account in "${accounts[@]}"; do
        local profile=$(yq eval ".accounts.$account.profile" "$ACCOUNTS_CONFIG")
        local region=$(yq eval ".accounts.$account.region" "$ACCOUNTS_CONFIG")
        
        echo -e "${CYAN}================================================${NC}"
        echo -e "${CYAN}Setting up: $account${NC}"
        echo -e "${CYAN}================================================${NC}"
        
        # Check if profile already exists and works
        if AWS_PROFILE="$profile" aws sts get-caller-identity &> /dev/null; then
            local account_id=$(AWS_PROFILE="$profile" aws sts get-caller-identity --query Account --output text)
            echo -e "${GREEN}✅ Profile already configured and working${NC}"
            echo -e "${BLUE}Account ID: $account_id${NC}"
            
            read -p "Reconfigure this profile? (y/N): " -n 1 -r
            echo ""
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                continue
            fi
        fi
        
        setup_account_profile "$account" "$profile" "$region"
    done
    
    echo -e "${GREEN}🎉 Account setup complete!${NC}"
    echo -e "${BLUE}💡 Next steps:${NC}"
    echo "   1. Test access: $0 --test"
    echo "   2. Deploy infrastructure: ./scripts/multi-account-deploy.sh"
}

# Main execution
main() {
    check_prerequisites
    
    if [[ "$LIST_PROFILES" == true ]]; then
        list_profiles
    elif [[ "$TEST_ACCESS" == true ]]; then
        test_account_access
    elif [[ "$ROTATE_KEYS" == true ]]; then
        rotate_access_keys
    else
        interactive_setup
    fi
}

# Run main function
main "$@"