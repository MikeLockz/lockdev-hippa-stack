#!/bin/bash

# HIPAA Infrastructure - Shared Utilities
# Common functions for setup, deployment, and cleanup scripts
# Preserves the security model: root credentials for setup, service credentials for operations

set -e

# Colors for output
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export CYAN='\033[0;36m'
export NC='\033[0m' # No Color

# Configuration paths
export SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
export ENVIRONMENTS_CONFIG="$PROJECT_DIR/configs/environments.yaml"

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_step() {
    echo -e "${CYAN}🔧 $1${NC}"
}

log_section() {
    echo ""
    echo -e "${CYAN}================================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}================================================${NC}"
}

# Error handling
die() {
    log_error "$1"
    exit 1
}

# Check if script is being sourced or executed
check_sourced() {
    if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
        die "This script should be sourced, not executed directly. Use: source scripts/common.sh"
    fi
}

# Prerequisite checks
check_prerequisites() {
    log_step "Checking prerequisites..."
    
    # Check if we're in the right directory
    if [[ ! -f "$PROJECT_DIR/Pulumi.yaml" ]]; then
        die "Not in Pulumi project directory. Run from lockdev-hippa-iac/"
    fi
    
    # Check required tools
    local tools=("pulumi" "aws" "yq" "jq")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            die "Required tool not found: $tool"
        fi
    done
    
    # Check if logged into Pulumi
    if ! pulumi whoami &> /dev/null; then
        die "Not logged into Pulumi. Run 'pulumi login'"
    fi
    
    log_success "Prerequisites check passed"
}

# Load environment configuration
load_environment_config() {
    local env_name="$1"
    
    if [[ ! -f "$ENVIRONMENTS_CONFIG" ]]; then
        die "Environments config not found: $ENVIRONMENTS_CONFIG"
    fi
    
    # Check if environment exists
    if ! yq eval ".environments | has(\"$env_name\")" "$ENVIRONMENTS_CONFIG" | grep -q "true"; then
        die "Environment '$env_name' not found in configuration"
    fi
    
    log_success "Loaded configuration for environment: $env_name"
}

# Get environment configuration value
get_env_config() {
    local env_name="$1"
    local key="$2"
    local default_value="$3"
    
    local value=$(yq eval ".environments.$env_name.$key // \"$default_value\"" "$ENVIRONMENTS_CONFIG")
    if [[ "$value" == "null" ]]; then
        echo "$default_value"
    else
        echo "$value"
    fi
}

# Validate AWS credentials
validate_aws_credentials() {
    local profile="$1"
    local region="$2"
    
    log_step "Validating AWS credentials for profile: $profile"
    
    if ! AWS_PROFILE="$profile" AWS_DEFAULT_REGION="$region" aws sts get-caller-identity &> /dev/null; then
        die "Cannot access AWS with profile: $profile"
    fi
    
    local account_id=$(AWS_PROFILE="$profile" AWS_DEFAULT_REGION="$region" aws sts get-caller-identity --query Account --output text)
    local user_arn=$(AWS_PROFILE="$profile" AWS_DEFAULT_REGION="$region" aws sts get-caller-identity --query Arn --output text)
    
    log_success "AWS access validated"
    log_info "Account ID: $account_id"
    log_info "User ARN: $user_arn"
    
    # Return the account ID for use by calling scripts
    echo "$account_id"
}

# Check if AWS user exists
aws_user_exists() {
    local profile="$1"
    local user_name="$2"
    
    AWS_PROFILE="$profile" aws iam get-user --user-name "$user_name" &> /dev/null
}

# Check if AWS policy exists
aws_policy_exists() {
    local profile="$1"
    local policy_name="$2"
    local account_id="$3"
    
    local policy_arn="arn:aws:iam::$account_id:policy/$policy_name"
    AWS_PROFILE="$profile" aws iam get-policy --policy-arn "$policy_arn" &> /dev/null
}

# Set up AWS environment variables for operations
setup_aws_env() {
    local profile="$1"
    local region="$2"
    
    export AWS_PROFILE="$profile"
    export AWS_DEFAULT_REGION="$region"
    export PULUMI_CONFIG_PASSPHRASE=""
    
    log_info "AWS environment configured: profile=$profile, region=$region"
}

# Create or select Pulumi stack
setup_pulumi_stack() {
    local stack_name="$1"
    local environment="$2"
    local region="$3"
    
    log_step "Setting up Pulumi stack: $stack_name"
    
    if poetry run pulumi stack ls | grep -q "^$stack_name"; then
        poetry run pulumi stack select "$stack_name"
        log_success "Selected existing stack: $stack_name"
    else
        poetry run pulumi stack init "$stack_name"
        log_success "Created new stack: $stack_name"
    fi
    
    # Configure stack
    poetry run pulumi config set aws:region "$region"
    poetry run pulumi config set environment "$environment"
    
    log_success "Pulumi stack configured"
}

# Confirmation prompt
confirm_action() {
    local message="$1"
    local confirmation_text="$2"
    
    echo ""
    log_warning "$message"
    echo ""
    
    if [[ -n "$confirmation_text" ]]; then
        read -p "Type '$confirmation_text' to confirm: " user_input
        if [[ "$user_input" != "$confirmation_text" ]]; then
            log_warning "Confirmation failed. Operation cancelled."
            exit 0
        fi
    else
        read -p "Continue? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_warning "Operation cancelled"
            exit 0
        fi
    fi
    
    log_success "Confirmation received"
}

# Check if running with --force flag
is_force_mode() {
    [[ "${FORCE:-false}" == "true" ]]
}

# Check if running in dry-run mode
is_dry_run() {
    [[ "${DRY_RUN:-false}" == "true" ]]
}

# Generate service user name for environment
get_service_user_name() {
    local env_name="$1"
    echo "pulumi-deploy-user-$env_name"
}

# Generate policy name for environment
get_policy_name() {
    local env_name="$1"
    echo "HIPAAInfrastructurePolicy-$env_name"
}

# Check if service user exists and has valid credentials
service_user_exists() {
    local environment="$1"
    local service_profile=$(get_env_config "$environment" "service_profile")
    local region=$(get_env_config "$environment" "region")
    
    # Check if AWS profile exists and works
    if AWS_PROFILE="$service_profile" AWS_DEFAULT_REGION="$region" aws sts get-caller-identity &> /dev/null; then
        return 0  # Service user exists and works
    else
        return 1  # Service user missing or broken
    fi
}

# Check if root credentials are available for setup
root_credentials_available() {
    local environment="$1"
    local root_profile=$(get_env_config "$environment" "root_profile")
    local region=$(get_env_config "$environment" "region")
    
    # Check if root AWS profile exists and works
    if AWS_PROFILE="$root_profile" AWS_DEFAULT_REGION="$region" aws sts get-caller-identity &> /dev/null; then
        return 0  # Root credentials available
    else
        return 1  # Root credentials missing
    fi
}

# Auto-setup service user if missing (requires root credentials)
auto_setup_service_user() {
    local environment="$1"
    
    log_section "Auto-Setup: Service User Missing"
    log_warning "Service user for environment '$environment' not found or not working"
    log_info "Attempting automatic setup using root credentials..."
    
    # Check if root credentials are available
    if ! root_credentials_available "$environment"; then
        local root_profile=$(get_env_config "$environment" "root_profile")
        log_error "Root credentials not available for profile: $root_profile"
        log_error "Cannot auto-setup service user without root access"
        echo ""
        log_info "Manual setup required:"
        echo "  1. Configure root credentials: aws configure --profile $root_profile"
        echo "  2. Run setup manually: ./scripts/setup-env.sh -e $environment"
        echo "  3. Then retry deployment: ./scripts/deploy.sh -e $environment"
        return 1
    fi
    
    # Run setup-env.sh automatically
    log_info "Running automatic environment setup..."
    echo ""
    log_info "🤖 Auto-setup in progress..."
    log_info "This will create the service user and policies using root credentials"
    echo ""
    
    if "$SCRIPT_DIR/setup-env.sh" -e "$environment" --force; then
        echo ""
        log_success "🎉 Auto-setup completed successfully!"
        log_info "Service user is now ready for deployment"
        log_info "Continuing with infrastructure deployment..."
        return 0
    else
        echo ""
        log_error "❌ Auto-setup failed"
        echo ""
        log_info "Possible causes:"
        echo "  • Root credentials not configured correctly"
        echo "  • AWS permissions insufficient"
        echo "  • Network connectivity issues"
        echo "  • Policy file missing or invalid"
        echo ""
        log_info "Manual resolution:"
        echo "  1. Check root credentials: aws sts get-caller-identity --profile $(get_env_config "$environment" "root_profile")"
        echo "  2. Run setup manually: ./scripts/setup-env.sh -e $environment"
        echo "  3. Then retry deployment: ./scripts/deploy.sh -e $environment"
        echo ""
        return 1
    fi
}

# Show help for common options
show_common_help() {
    echo "Common Options:"
    echo "  -h, --help              Show help message"
    echo "  -e, --environment ENV   Environment name (dev, staging, prod)"
    echo "  -f, --force            Skip confirmation prompts"
    echo "  -d, --dry-run          Show what would be done without doing it"
    echo "  -v, --verbose          Verbose output"
    echo ""
}

# Parse common command line arguments
parse_common_args() {
    ENVIRONMENT=""
    FORCE=false
    DRY_RUN=false
    VERBOSE=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                return 1  # Signal caller to show help
                ;;
            -e|--environment)
                ENVIRONMENT="$2"
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
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -*)
                die "Unknown option: $1"
                ;;
            *)
                # Return remaining args for script-specific processing
                echo "$@"
                return 0
                ;;
        esac
    done
    
    return 0
}

# Validate required environment argument
require_environment() {
    if [[ -z "$ENVIRONMENT" ]]; then
        die "Environment is required. Use -e/--environment flag or ensure ENVIRONMENT variable is set."
    fi
}

# Create example environments configuration if it doesn't exist
create_example_environments_config() {
    local config_dir="$(dirname "$ENVIRONMENTS_CONFIG")"
    mkdir -p "$config_dir"
    
    cat > "$ENVIRONMENTS_CONFIG" << 'EOF'
# HIPAA Infrastructure Environments Configuration
# Defines environments and their AWS account mappings

environments:
  dev:
    # Root account profile (for creating service users only)
    root_profile: dev-root
    # Service user profile (for Pulumi operations)
    service_profile: pulumi-deploy-user-dev
    region: us-east-1
    environment: development
    stack_prefix: hipaa
    tags:
      Environment: development
      CostCenter: Development
      Owner: DevTeam
      
  staging:
    root_profile: staging-root
    service_profile: pulumi-deploy-user-staging
    region: us-east-1
    environment: staging
    stack_prefix: hipaa
    tags:
      Environment: staging
      CostCenter: QA
      Owner: QATeam
      
  prod:
    root_profile: prod-root
    service_profile: pulumi-deploy-user-prod
    region: us-west-2
    environment: production
    stack_prefix: hipaa
    tags:
      Environment: production
      CostCenter: Production
      Owner: OpsTeam

# Global settings
global:
  pulumi_backend: pulumi.com
  service_user_prefix: pulumi-deploy-user
  policy_prefix: HIPAAInfrastructurePolicy
EOF
    
    log_success "Created example environments configuration: $ENVIRONMENTS_CONFIG"
    log_info "Please edit this file with your account details"
}

log_info "Common utilities loaded"