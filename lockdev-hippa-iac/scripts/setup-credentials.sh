#!/bin/bash

# HIPAA Infrastructure AWS Credentials Setup
# Interactive setup for AWS credentials and profiles
# Handles both root profiles and service user profiles

set -e

# Load shared utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Help function
show_help() {
    echo -e "${GREEN}HIPAA Infrastructure AWS Credentials Setup${NC}"
    echo ""
    echo -e "${YELLOW}Interactive AWS Profile Configuration${NC}"
    echo ""
    echo "This script helps you configure AWS profiles needed for the HIPAA infrastructure."
    echo "It will guide you through setting up:"
    echo "  • Root account profiles (for environment setup)"
    echo "  • Service user profiles (for deployments - created automatically)"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e, --environment ENV    Target environment (dev, staging, prod)"
    echo "  -h, --help              Show this help message"
    echo "  --interactive           Force interactive mode (default)"
    echo ""
    echo "Examples:"
    echo "  $0 -e dev               # Setup development credentials"
    echo "  $0 --interactive        # Interactive setup for all environments"
    echo ""
}

# Interactive AWS credential collection
collect_aws_credentials() {
    local profile_name="$1"
    local environment="$2"
    
    echo ""
    log_section "AWS Credentials Setup for Profile: $profile_name"
    
    echo "Please provide your AWS credentials for the $environment environment."
    echo "These should be ROOT ACCOUNT credentials with administrative access."
    echo ""
    log_warning "SECURITY: These credentials will be stored in ~/.aws/credentials"
    echo ""
    
    # Collect access key
    echo -n "AWS Access Key ID: "
    read -r access_key
    if [[ -z "$access_key" ]]; then
        die "Access Key ID is required"
    fi
    
    # Collect secret key (hidden input)
    echo -n "AWS Secret Access Key: "
    read -s secret_key
    echo ""
    if [[ -z "$secret_key" ]]; then
        die "Secret Access Key is required"
    fi
    
    # Collect region
    echo -n "AWS Region (default: us-east-1): "
    read -r region
    region=${region:-us-east-1}
    
    # Configure the profile
    log_step "Configuring AWS profile: $profile_name"
    
    aws configure --profile "$profile_name" set aws_access_key_id "$access_key"
    aws configure --profile "$profile_name" set aws_secret_access_key "$secret_key"
    aws configure --profile "$profile_name" set region "$region"
    
    # Test the credentials
    log_step "Testing credentials..."
    if AWS_PROFILE="$profile_name" aws sts get-caller-identity &> /dev/null; then
        local account_id=$(AWS_PROFILE="$profile_name" aws sts get-caller-identity --query Account --output text)
        local user_arn=$(AWS_PROFILE="$profile_name" aws sts get-caller-identity --query Arn --output text)
        
        log_success "Credentials configured successfully!"
        log_info "Account ID: $account_id"
        log_info "User ARN: $user_arn"
        
        return 0
    else
        log_error "Credential test failed!"
        return 1
    fi
}

# Check if profile exists and is valid
check_profile() {
    local profile_name="$1"
    
    if aws configure list --profile "$profile_name" &> /dev/null; then
        log_info "Profile exists: $profile_name"
        
        # Test if it works
        if AWS_PROFILE="$profile_name" aws sts get-caller-identity &> /dev/null; then
            local account_id=$(AWS_PROFILE="$profile_name" aws sts get-caller-identity --query Account --output text)
            log_success "Profile is valid: $profile_name (Account: $account_id)"
            return 0
        else
            log_warning "Profile exists but credentials are invalid: $profile_name"
            return 1
        fi
    else
        log_info "Profile does not exist: $profile_name"
        return 1
    fi
}

# Setup credentials for specific environment
setup_environment_credentials() {
    local env_name="$1"
    
    log_section "Setting up credentials for environment: $env_name"
    
    # Load environment configuration
    if [[ ! -f "$ENVIRONMENTS_CONFIG" ]]; then
        die "Environments config not found: $ENVIRONMENTS_CONFIG"
    fi
    
    # Get root profile name from config
    local root_profile=$(yq eval ".environments.$env_name.root_profile" "$ENVIRONMENTS_CONFIG")
    if [[ "$root_profile" == "null" ]]; then
        die "Root profile not configured for environment: $env_name"
    fi
    
    log_info "Environment: $env_name"
    log_info "Root Profile: $root_profile"
    
    # Check if profile already exists and is valid
    if check_profile "$root_profile"; then
        echo ""
        echo "Profile $root_profile is already configured and working."
        echo -n "Do you want to reconfigure it? (y/N): "
        read -r reconfigure
        if [[ "$reconfigure" != "y" && "$reconfigure" != "Y" ]]; then
            log_info "Keeping existing profile: $root_profile"
            return 0
        fi
    fi
    
    # Collect and configure credentials
    if collect_aws_credentials "$root_profile" "$env_name"; then
        log_success "Environment credentials setup complete: $env_name"
    else
        die "Failed to setup credentials for environment: $env_name"
    fi
}

# Interactive environment selection
select_environment() {
    echo ""
    log_section "Environment Selection"
    
    echo "Available environments:"
    echo "  1) dev      - Development environment"
    echo "  2) staging  - Staging environment" 
    echo "  3) prod     - Production environment"
    echo "  4) all      - Setup all environments"
    echo ""
    echo -n "Select environment (1-4): "
    read -r choice
    
    case $choice in
        1)
            echo "dev"
            ;;
        2)
            echo "staging"
            ;;
        3)
            echo "prod"
            ;;
        4)
            echo "all"
            ;;
        *)
            log_error "Invalid choice: $choice"
            return 1
            ;;
    esac
}

# Setup all environments
setup_all_environments() {
    log_section "Setting up credentials for all environments"
    
    for env in dev staging prod; do
        echo ""
        echo -n "Setup credentials for $env environment? (Y/n): "
        read -r setup_env
        if [[ "$setup_env" != "n" && "$setup_env" != "N" ]]; then
            setup_environment_credentials "$env"
        else
            log_info "Skipping environment: $env"
        fi
    done
}

# Show current profile status
show_profile_status() {
    log_section "Current AWS Profile Status"
    
    for env in dev staging prod; do
        local root_profile=$(yq eval ".environments.$env.root_profile" "$ENVIRONMENTS_CONFIG" 2>/dev/null || echo "null")
        local service_profile=$(yq eval ".environments.$env.service_profile" "$ENVIRONMENTS_CONFIG" 2>/dev/null || echo "null")
        
        echo ""
        echo -e "${CYAN}Environment: $env${NC}"
        echo "─────────────────────"
        
        if [[ "$root_profile" != "null" ]]; then
            echo -n "Root Profile ($root_profile): "
            if check_profile "$root_profile" &> /dev/null; then
                echo -e "${GREEN}✅ Valid${NC}"
            else
                echo -e "${RED}❌ Invalid/Missing${NC}"
            fi
        fi
        
        if [[ "$service_profile" != "null" ]]; then
            echo -n "Service Profile ($service_profile): "
            if check_profile "$service_profile" &> /dev/null; then
                echo -e "${GREEN}✅ Valid${NC}"
            else
                echo -e "${YELLOW}⚠️  Not created yet (run setup-env-$env)${NC}"
            fi
        fi
    done
}

# Main function
main() {
    local environment=""
    local interactive=true
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                environment="$2"
                interactive=false
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            --interactive)
                interactive=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    log_section "HIPAA Infrastructure AWS Credentials Setup"
    
    # Check prerequisites
    if ! command -v aws &> /dev/null; then
        die "AWS CLI not found. Install it first with: make install-aws-cli"
    fi
    
    if ! command -v yq &> /dev/null; then
        die "yq not found. Install it first with: make install-deps"
    fi
    
    # Show current status
    if [[ -f "$ENVIRONMENTS_CONFIG" ]]; then
        show_profile_status
    else
        log_warning "Environments config not found. Creating default configuration..."
        # This would be handled by the setup-env.sh script
    fi
    
    echo ""
    
    # Interactive mode
    if [[ "$interactive" == "true" && -z "$environment" ]]; then
        environment=$(select_environment)
        if [[ $? -ne 0 ]]; then
            exit 1
        fi
    fi
    
    # Validate environment
    if [[ -z "$environment" ]]; then
        die "Environment not specified. Use -e option or interactive mode."
    fi
    
    # Setup credentials
    if [[ "$environment" == "all" ]]; then
        setup_all_environments
    else
        setup_environment_credentials "$environment"
    fi
    
    echo ""
    log_section "Setup Complete"
    log_success "AWS credentials configured for environment: $environment"
    echo ""
    log_info "Next Steps:"
    if [[ "$environment" == "all" ]]; then
        echo "  1. Run setup for each environment:"
        echo "     make setup-env-dev"
        echo "     make setup-env-staging"
        echo "     make setup-env-prod"
    else
        echo "  1. Run environment setup:"
        echo "     make setup-env-$environment"
    fi
    echo ""
    echo "  2. Deploy infrastructure:"
    if [[ "$environment" != "all" ]]; then
        echo "     make deploy-$environment"
    else
        echo "     make deploy-dev      # or staging/prod"
    fi
    echo ""
}

# Run main function
main "$@"