#!/bin/bash

# Multi-Account Cleanup Script
# Destroys HIPAA infrastructure across multiple AWS accounts
# Includes safety checks and confirmation prompts

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
    echo -e "${GREEN}Multi-Account HIPAA Infrastructure Cleanup${NC}"
    echo ""
    echo "This script safely destroys HIPAA infrastructure across multiple AWS accounts."
    echo "Includes multiple confirmation prompts and safety checks."
    echo ""
    echo "Usage: $0 [OPTIONS] [ACCOUNTS...]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -c, --config FILE       Accounts configuration file (default: configs/accounts.yaml)"
    echo "  -f, --force             Skip confirmation prompts (DANGEROUS)"
    echo "  -d, --dry-run           Show what would be destroyed without doing it"
    echo "  --confirm TEXT          Required confirmation text for safety"
    echo "  --stack-prefix PREFIX   Prefix for Pulumi stack names (default: hipaa)"
    echo ""
    echo "Safety Features:"
    echo "  - Multiple confirmation prompts"
    echo "  - Account validation before destruction"
    echo "  - Dry-run mode to preview changes"
    echo "  - Required confirmation text"
    echo ""
    echo "Examples:"
    echo "  $0 dev                                    # Destroy dev account (with prompts)"
    echo "  $0 --dry-run dev staging                  # Preview destruction"
    echo "  $0 --confirm \"destroy dev\" dev            # Destroy with confirmation text"
    echo "  $0 --force --confirm \"emergency\" dev      # Emergency destruction"
}

# Default values
FORCE=false
DRY_RUN=false
CONFIRMATION_TEXT=""
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
        -f|--force)
            FORCE=true
            shift
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        --confirm)
            CONFIRMATION_TEXT="$2"
            shift 2
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
    local tools=("pulumi" "aws" "yq")
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

# Function to load accounts configuration
load_accounts_config() {
    if [[ ! -f "$ACCOUNTS_CONFIG" ]]; then
        echo -e "${RED}❌ Accounts config not found: $ACCOUNTS_CONFIG${NC}"
        echo -e "${BLUE}💡 Run setup-accounts.sh first${NC}"
        exit 1
    fi
    
    # If no accounts specified, load all from config
    if [[ ${#SELECTED_ACCOUNTS[@]} -eq 0 ]]; then
        SELECTED_ACCOUNTS=($(yq eval '.accounts | keys | .[]' "$ACCOUNTS_CONFIG"))
    fi
    
    echo -e "${GREEN}✅ Loaded configuration for ${#SELECTED_ACCOUNTS[@]} accounts${NC}"
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
        return 1
    fi
    
    local account_id=$(AWS_PROFILE="$profile" AWS_DEFAULT_REGION="$region" aws sts get-caller-identity --query Account --output text)
    echo -e "${GREEN}✅ Access validated for account: $account_id${NC}"
    return 0
}

# Function to show stack resources (dry-run)
show_stack_resources() {
    local account=$1
    local profile=$(get_account_config "$account" "profile")
    local region=$(get_account_config "$account" "region")
    local stack_name="${STACK_PREFIX}-${account}"
    
    echo -e "${CYAN}📋 Resources in stack: $stack_name${NC}"
    
    # Set environment variables
    export AWS_PROFILE="$profile"
    export AWS_DEFAULT_REGION="$region"
    
    # Check if stack exists
    if ! pulumi stack ls | grep -q "^$stack_name"; then
        echo -e "${YELLOW}⚠️  Stack does not exist: $stack_name${NC}"
        return 0
    fi
    
    pulumi stack select "$stack_name"
    
    # Show preview of destruction
    echo -e "${YELLOW}Resources that would be destroyed:${NC}"
    pulumi preview --diff --show-replacement-steps 2>/dev/null | grep -E "(delete|replace)" || echo "No resources to destroy"
    
    echo ""
}

# Function to destroy account infrastructure
destroy_account() {
    local account=$1
    local profile=$(get_account_config "$account" "profile")
    local region=$(get_account_config "$account" "region")
    local stack_name="${STACK_PREFIX}-${account}"
    
    echo -e "${CYAN}================================================${NC}"
    echo -e "${CYAN}💥 Destroying Account: $account${NC}"
    echo -e "${CYAN}================================================${NC}"
    echo -e "${BLUE}Profile: $profile${NC}"
    echo -e "${BLUE}Region: $region${NC}"
    echo -e "${BLUE}Stack: $stack_name${NC}"
    echo ""
    
    # Set environment variables
    export AWS_PROFILE="$profile"
    export AWS_DEFAULT_REGION="$region"
    
    # Check if stack exists
    if ! pulumi stack ls | grep -q "^$stack_name"; then
        echo -e "${YELLOW}⚠️  Stack does not exist: $stack_name${NC}"
        return 0
    fi
    
    pulumi stack select "$stack_name"
    
    # Final confirmation for this account
    if [[ "$FORCE" == false ]]; then
        echo -e "${RED}⚠️  FINAL WARNING: About to destroy ALL resources in $account${NC}"
        echo -e "${RED}This action cannot be undone!${NC}"
        echo ""
        read -p "Type 'destroy' to confirm destruction of $account: " confirm
        if [[ "$confirm" != "destroy" ]]; then
            echo -e "${YELLOW}Skipping $account${NC}"
            return 0
        fi
    fi
    
    # Destroy the stack
    echo -e "${YELLOW}💥 Destroying infrastructure for $account...${NC}"
    if [[ "$FORCE" == true ]]; then
        pulumi destroy --yes
    else
        pulumi destroy
    fi
    
    # Remove the stack
    echo -e "${YELLOW}🗑️  Removing Pulumi stack...${NC}"
    pulumi stack rm --yes
    
    echo -e "${GREEN}✅ Destruction complete for $account${NC}"
    echo ""
}

# Function to display destruction summary
display_destruction_summary() {
    echo -e "${CYAN}================================================${NC}"
    echo -e "${CYAN}💥 Destruction Summary${NC}"
    echo -e "${CYAN}================================================${NC}"
    
    for account in "${SELECTED_ACCOUNTS[@]}"; do
        local stack_name="${STACK_PREFIX}-${account}"
        
        # Check if stack still exists
        if pulumi stack ls | grep -q "^$stack_name"; then
            echo -e "${YELLOW}⚠️  $account: Stack still exists (destruction may have failed)${NC}"
        else
            echo -e "${GREEN}✅ $account: Successfully destroyed${NC}"
        fi
    done
    
    echo ""
    echo -e "${GREEN}🎉 Multi-account destruction complete!${NC}"
    echo ""
    echo -e "${BLUE}💡 Cleanup recommendations:${NC}"
    echo "   1. Verify all AWS resources are deleted in each account"
    echo "   2. Check for any remaining costs in AWS billing"
    echo "   3. Rotate AWS access keys if no longer needed"
    echo "   4. Clean up local Pulumi state if desired"
}

# Function to safety checks and confirmations
run_safety_checks() {
    echo -e "${RED}⚠️  DANGER: INFRASTRUCTURE DESTRUCTION${NC}"
    echo -e "${RED}======================================${NC}"
    echo ""
    echo -e "${YELLOW}You are about to PERMANENTLY DESTROY infrastructure in:${NC}"
    printf "   ${RED}%s${NC}\n" "${SELECTED_ACCOUNTS[@]}"
    echo ""
    echo -e "${RED}This will delete ALL resources including:${NC}"
    echo "   • Databases and ALL DATA"
    echo "   • Load balancers and networking"
    echo "   • Container images and repositories"
    echo "   • Security groups and IAM roles"
    echo "   • Monitoring and logging configurations"
    echo "   • KMS keys and encrypted data"
    echo ""
    echo -e "${RED}THIS CANNOT BE UNDONE!${NC}"
    echo ""
    
    if [[ "$FORCE" == false ]]; then
        # First confirmation
        read -p "Are you absolutely sure you want to destroy these accounts? (type 'yes'): " confirm1
        if [[ "$confirm1" != "yes" ]]; then
            echo -e "${YELLOW}Destruction cancelled${NC}"
            exit 0
        fi
        
        # Second confirmation with account names
        echo ""
        echo -e "${YELLOW}Type the following account names to confirm:${NC}"
        printf "   %s\n" "${SELECTED_ACCOUNTS[@]}"
        echo ""
        
        for account in "${SELECTED_ACCOUNTS[@]}"; do
            read -p "Confirm destruction of '$account' (type the account name): " confirm_account
            if [[ "$confirm_account" != "$account" ]]; then
                echo -e "${YELLOW}Confirmation failed for $account. Destruction cancelled.${NC}"
                exit 0
            fi
        done
        
        # Third confirmation with random word
        local random_word=$(openssl rand -hex 4 2>/dev/null || echo "$(date +%s)")
        echo ""
        echo -e "${YELLOW}Final confirmation. Type this random code: ${CYAN}$random_word${NC}"
        read -p "Enter code: " confirm_code
        if [[ "$confirm_code" != "$random_word" ]]; then
            echo -e "${YELLOW}Code confirmation failed. Destruction cancelled.${NC}"
            exit 0
        fi
    fi
    
    # Check confirmation text if provided
    if [[ -n "$CONFIRMATION_TEXT" ]]; then
        echo ""
        echo -e "${YELLOW}Required confirmation text check...${NC}"
        read -p "Enter confirmation text '$CONFIRMATION_TEXT': " provided_text
        if [[ "$provided_text" != "$CONFIRMATION_TEXT" ]]; then
            echo -e "${RED}❌ Confirmation text mismatch. Destruction cancelled.${NC}"
            exit 1
        fi
    fi
    
    echo ""
    echo -e "${GREEN}✅ All safety checks passed. Proceeding with destruction...${NC}"
    echo ""
}

# Main execution
main() {
    echo -e "${RED}💥 Multi-Account HIPAA Infrastructure Cleanup${NC}"
    echo ""
    
    # Check prerequisites
    check_prerequisites
    
    # Load configuration
    load_accounts_config
    
    # Validate access to all accounts
    echo -e "${YELLOW}🔍 Validating access to all accounts...${NC}"
    for account in "${SELECTED_ACCOUNTS[@]}"; do
        if ! validate_account_access "$account"; then
            echo -e "${RED}❌ Validation failed for account: $account${NC}"
            exit 1
        fi
    done
    
    # Change to project directory
    cd "$PROJECT_DIR"
    
    if [[ "$DRY_RUN" == true ]]; then
        echo -e "${CYAN}👁️  DRY RUN MODE: Showing what would be destroyed${NC}"
        echo ""
        for account in "${SELECTED_ACCOUNTS[@]}"; do
            show_stack_resources "$account"
        done
        echo -e "${GREEN}✅ Dry run complete. No resources were destroyed.${NC}"
        exit 0
    fi
    
    # Run safety checks and confirmations
    run_safety_checks
    
    # Destroy each account
    for account in "${SELECTED_ACCOUNTS[@]}"; do
        destroy_account "$account"
    done
    
    # Display summary
    display_destruction_summary
}

# Run main function
main "$@"