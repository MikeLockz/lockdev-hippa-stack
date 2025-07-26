#!/bin/bash

# HIPAA Infrastructure Environment Setup
# Phase 1 of the security model: Uses ROOT credentials to create service users
# 
# This script:
# 1. Uses root account credentials (dev-root, staging-root, prod-root)
# 2. Creates service users (pulumi-deploy-user-<env>) with limited permissions
# 3. Creates access keys for service users
# 4. Sets up policies for HIPAA-compliant infrastructure deployment
#
# Security Model:
# ROOT ACCOUNT (setup only) → SERVICE USER (operations) → Pulumi Resources

set -e

# Load shared utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Script-specific configuration
POLICY_FILE="$PROJECT_DIR/policies/infrastructure-policy.json"

# Help function
show_help() {
    echo -e "${GREEN}HIPAA Infrastructure Environment Setup${NC}"
    echo ""
    echo -e "${YELLOW}Phase 1: Root Account → Service User Creation${NC}"
    echo ""
    echo "This script uses ROOT account credentials to create service users"
    echo "with comprehensive permissions for Pulumi infrastructure deployment and cleanup."
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    show_common_help
    echo "Examples:"
    echo "  $0 -e dev                    # Setup development environment"
    echo "  $0 -e staging --dry-run      # Preview staging setup"
    echo "  $0 -e prod --force           # Setup production (skip prompts)"
    echo ""
    echo "Security Model:"
    echo "  1. ROOT credentials → Create service user + policies"
    echo "  2. SERVICE credentials → Deploy infrastructure (see deploy.sh)"
    echo ""
    echo "Prerequisites:"
    echo "  - AWS CLI configured with root account profiles"
    echo "  - Environments configuration in configs/environments.yaml"
    echo ""
}

# Create IAM policy for service user
create_service_user_policy() {
    local root_profile="$1"
    local policy_name="$2"
    local environment="$3"
    
    log_step "Creating IAM policy: $policy_name"
    
    # Check if policy already exists
    local account_id=$(AWS_PROFILE="$root_profile" aws sts get-caller-identity --query Account --output text)
    
    if aws_policy_exists "$root_profile" "$policy_name" "$account_id"; then
        log_warning "Policy already exists: $policy_name"
        log_info "Auto-updating existing policy"
        
        if is_dry_run; then
            log_info "[DRY RUN] Would update policy: $policy_name"
            return
        fi
        
        # Update existing policy
        local policy_arn="arn:aws:iam::$account_id:policy/$policy_name"
        
        # Check number of existing versions and clean up if needed
        local versions=$(AWS_PROFILE="$root_profile" aws iam list-policy-versions \
            --policy-arn "$policy_arn" \
            --query 'Versions[?!IsDefaultVersion].VersionId' \
            --output text)
        
        local version_count=$(echo "$versions" | wc -w | tr -d ' ')
        
        # AWS allows maximum 5 versions, so if we have 4 non-default versions, delete the oldest
        if [[ "$version_count" -ge 4 ]]; then
            log_info "Policy has maximum versions (5). Cleaning up oldest non-default version."
            
            # Get the oldest non-default version
            local oldest_version=$(AWS_PROFILE="$root_profile" aws iam list-policy-versions \
                --policy-arn "$policy_arn" \
                --query 'Versions[?!IsDefaultVersion] | sort_by(@, &CreateDate) | [0].VersionId' \
                --output text)
            
            if [[ -n "$oldest_version" && "$oldest_version" != "None" ]]; then
                log_info "Deleting oldest policy version: $oldest_version"
                AWS_PROFILE="$root_profile" aws iam delete-policy-version \
                    --policy-arn "$policy_arn" \
                    --version-id "$oldest_version"
            fi
        fi
        
        # Now create the new version
        local version_output=$(AWS_PROFILE="$root_profile" aws iam create-policy-version \
            --policy-arn "$policy_arn" \
            --policy-document file://"$POLICY_FILE" \
            --set-as-default)
        
        local version_id=$(echo "$version_output" | jq -r '.PolicyVersion.VersionId')
        log_success "Policy updated: $policy_name (version $version_id)"
    else
        if is_dry_run; then
            log_info "[DRY RUN] Would create policy: $policy_name"
            return
        fi
        
        # Create new policy
        local policy_output=$(AWS_PROFILE="$root_profile" aws iam create-policy \
            --policy-name "$policy_name" \
            --policy-document file://"$POLICY_FILE" \
            --description "HIPAA infrastructure deployment policy for $environment environment" \
            --tags Key=Environment,Value="$environment" \
                   Key=Purpose,Value=InfrastructureDeployment \
                   Key=ManagedBy,Value=setup-env-script)
        
        local policy_arn=$(echo "$policy_output" | jq -r '.Policy.Arn')
        log_success "Policy created: $policy_name ($policy_arn)"
    fi
}

# Create IAM service user
create_service_user() {
    local root_profile="$1"
    local user_name="$2"
    local policy_name="$3"
    local environment="$4"
    
    log_step "Creating IAM user: $user_name"
    
    # Check if user already exists
    if aws_user_exists "$root_profile" "$user_name"; then
        log_warning "User already exists: $user_name"
        log_info "Continuing with existing user"
    else
        if is_dry_run; then
            log_info "[DRY RUN] Would create user: $user_name"
        else
            # Create new user
            local user_output=$(AWS_PROFILE="$root_profile" aws iam create-user \
                --user-name "$user_name" \
                --tags Key=Environment,Value="$environment" \
                       Key=Purpose,Value=InfrastructureDeployment \
                       Key=ManagedBy,Value=setup-env-script)
            
            local user_arn=$(echo "$user_output" | jq -r '.User.Arn')
            log_success "User created: $user_name ($user_arn)"
        fi
    fi
    
    # Attach policy to user
    log_step "Attaching policy to user: $user_name"
    
    if is_dry_run; then
        log_info "[DRY RUN] Would attach policy $policy_name to user $user_name"
    else
        local account_id=$(AWS_PROFILE="$root_profile" aws sts get-caller-identity --query Account --output text)
        local policy_arn="arn:aws:iam::$account_id:policy/$policy_name"
        
        # Check if policy is already attached
        local attached_policies=$(AWS_PROFILE="$root_profile" aws iam list-attached-user-policies \
            --user-name "$user_name" \
            --query "AttachedPolicies[?PolicyArn=='$policy_arn'].PolicyName" \
            --output text)
        
        if [[ -n "$attached_policies" ]]; then
            log_info "Policy already attached to user: $user_name"
        else
            AWS_PROFILE="$root_profile" aws iam attach-user-policy \
                --user-name "$user_name" \
                --policy-arn "$policy_arn"
            
            log_success "Policy attached to user: $user_name"
        fi
    fi
}

# Create access keys for service user
create_access_keys() {
    local root_profile="$1"
    local user_name="$2"
    local environment="$3"
    
    log_step "Creating access keys for user: $user_name"
    
    if is_dry_run; then
        log_info "[DRY RUN] Would create access keys for user: $user_name"
        return
    fi
    
    local creds_file="$PROJECT_DIR/.credentials-$environment.json"
    
    # Check if credentials file already exists and is valid
    if [[ -f "$creds_file" ]] && [[ -s "$creds_file" ]]; then
        # Verify the existing credentials are still valid
        local existing_access_key=$(jq -r '.AccessKey.AccessKeyId // empty' "$creds_file" 2>/dev/null)
        if [[ -n "$existing_access_key" ]]; then
            # Test if the existing key is still active
            local key_status=$(AWS_PROFILE="$root_profile" aws iam get-access-key-last-used \
                --access-key-id "$existing_access_key" \
                --query 'AccessKeyLastUsed.LastUsedDate' \
                --output text 2>/dev/null || echo "INVALID")
            
            if [[ "$key_status" != "INVALID" ]]; then
                log_info "Using existing valid access keys from: $creds_file"
                # Extract credentials for display
                local access_key=$(jq -r '.AccessKey.AccessKeyId' "$creds_file")
                local secret_key=$(jq -r '.AccessKey.SecretAccessKey' "$creds_file")
                
                echo ""
                log_info "Service User Credentials:"
                echo -e "${BLUE}Access Key ID: ${CYAN}$access_key${NC}"
                echo -e "${BLUE}Secret Access Key: ${CYAN}$secret_key${NC}"
                echo ""
                
                # Generate AWS CLI profile setup commands
                log_info "To configure AWS CLI profile for deployment:"
                echo -e "${CYAN}aws configure --profile pulumi-deploy-user-$environment set aws_access_key_id $access_key${NC}"
                echo -e "${CYAN}aws configure --profile pulumi-deploy-user-$environment set aws_secret_access_key $secret_key${NC}"
                echo -e "${CYAN}aws configure --profile pulumi-deploy-user-$environment set region $(get_env_config "$environment" "region")${NC}"
                echo ""
                return
            fi
        fi
    fi
    
    # Check existing access keys count
    local existing_keys=$(AWS_PROFILE="$root_profile" aws iam list-access-keys \
        --user-name "$user_name" \
        --query 'AccessKeyMetadata[].AccessKeyId' \
        --output text)
    
    local key_count=$(echo "$existing_keys" | wc -w | tr -d ' ')
    
    if [[ "$key_count" -ge 2 ]]; then
        log_warning "User already has maximum number of access keys (2)"
        log_info "Rotating oldest access key to create new one"
        
        # Get the oldest key
        local oldest_key=$(AWS_PROFILE="$root_profile" aws iam list-access-keys \
            --user-name "$user_name" \
            --query 'AccessKeyMetadata | sort_by(@, &CreateDate) | [0].AccessKeyId' \
            --output text)
        
        log_info "Deleting oldest access key: $oldest_key"
        AWS_PROFILE="$root_profile" aws iam delete-access-key \
            --user-name "$user_name" \
            --access-key-id "$oldest_key"
    fi
    
    # Create new access key
    local key_output=$(AWS_PROFILE="$root_profile" aws iam create-access-key --user-name "$user_name")
    
    # Save credentials to secure file
    echo "$key_output" > "$creds_file"
    chmod 600 "$creds_file"
    
    log_success "New access keys created and saved to: $creds_file"
    log_warning "IMPORTANT: Keep this file secure and add to .gitignore!"
    
    # Extract credentials for display
    local access_key=$(echo "$key_output" | jq -r '.AccessKey.AccessKeyId')
    local secret_key=$(echo "$key_output" | jq -r '.AccessKey.SecretAccessKey')
    
    echo ""
    log_info "Service User Credentials:"
    echo -e "${BLUE}Access Key ID: ${CYAN}$access_key${NC}"
    echo -e "${BLUE}Secret Access Key: ${CYAN}$secret_key${NC}"
    echo ""
    
    # Generate AWS CLI profile setup commands
    log_info "To configure AWS CLI profile for deployment:"
    echo -e "${CYAN}aws configure --profile pulumi-deploy-user-$environment set aws_access_key_id $access_key${NC}"
    echo -e "${CYAN}aws configure --profile pulumi-deploy-user-$environment set aws_secret_access_key $secret_key${NC}"
    echo -e "${CYAN}aws configure --profile pulumi-deploy-user-$environment set region $(get_env_config "$environment" "region")${NC}"
    echo ""
}

# Ensure credentials file is in .gitignore
ensure_gitignore() {
    local environment="$1"
    local gitignore_file="$PROJECT_DIR/.gitignore"
    local credentials_pattern=".credentials-*.json"
    
    if [[ ! -f "$gitignore_file" ]]; then
        log_info "Creating .gitignore file"
        touch "$gitignore_file"
    fi
    
    if ! grep -q "$credentials_pattern" "$gitignore_file"; then
        log_info "Adding credentials pattern to .gitignore"
        echo "" >> "$gitignore_file"
        echo "# AWS credentials files (generated by setup scripts)" >> "$gitignore_file"
        echo "$credentials_pattern" >> "$gitignore_file"
    fi
}

# Validate prerequisites specific to setup
validate_setup_prerequisites() {
    log_step "Validating setup prerequisites..."
    
    # Check if infrastructure policy file exists
    if [[ ! -f "$POLICY_FILE" ]]; then
        die "Infrastructure policy file not found: $POLICY_FILE"
    fi
    
    # Validate policy JSON
    if ! jq empty "$POLICY_FILE" &> /dev/null; then
        die "Invalid JSON in policy file: $POLICY_FILE"
    fi
    
    # Check if jq is available (needed for credential parsing)
    if ! command -v jq &> /dev/null; then
        die "jq is required for credential handling. Install with: brew install jq"
    fi
    
    log_success "Setup prerequisites validated"
}

# Setup single environment
setup_environment() {
    local env_name="$1"
    
    log_section "Setting up environment: $env_name"
    
    # Load environment configuration
    load_environment_config "$env_name"
    
    # Get environment settings
    local root_profile=$(get_env_config "$env_name" "root_profile")
    local region=$(get_env_config "$env_name" "region")
    local user_name=$(get_env_config "$env_name" "service_user.name")
    local policy_name=$(get_env_config "$env_name" "service_user.policy_name")
    
    log_info "Environment: $env_name"
    log_info "Root Profile: $root_profile"
    log_info "Region: $region"
    log_info "Service User: $user_name"
    log_info "Policy: $policy_name"
    
    # Validate root account access
    validate_aws_credentials "$root_profile" "$region"
    
    # Show setup information
    if ! is_dry_run; then
        echo ""
        log_info "Setting up environment '$env_name' using ROOT credentials"
        log_info "This will create/update:"
        echo "  • IAM Policy: $policy_name"
        echo "  • IAM User: $user_name"
        echo "  • Access Keys for: $user_name"
        echo ""
        log_info "Proceeding with environment setup..."
    fi
    
    # Setup AWS environment
    setup_aws_env "$root_profile" "$region"
    
    # Ensure .gitignore is configured
    ensure_gitignore "$env_name"
    
    # Create policy
    create_service_user_policy "$root_profile" "$policy_name" "$env_name"
    
    # Create service user
    create_service_user "$root_profile" "$user_name" "$policy_name" "$env_name"
    
    # Create access keys
    create_access_keys "$root_profile" "$user_name" "$env_name"
    
    log_success "Environment setup complete: $env_name"
}

# Main function
main() {
    local remaining_args
    
    # Parse command line arguments
    remaining_args=$(parse_common_args "$@") || {
        show_help
        exit 0
    }
    
    # Parse environment from the command name using multiple robust methods
    if [[ -z "$ENVIRONMENT" ]]; then
        # Method 1: Check MAKECMDGOALS (set by Makefile)
        if [[ -n "${MAKECMDGOALS:-}" ]]; then
            for pattern in "dev" "staging" "prod" "prd"; do
                if [[ "$MAKECMDGOALS" == *"-$pattern"* ]] || [[ "$MAKECMDGOALS" == *"$pattern-"* ]]; then
                    ENVIRONMENT="$pattern"
                    [[ "$ENVIRONMENT" == "prd" ]] && ENVIRONMENT="prod"
                    break
                fi
            done
        fi
        
        # Method 2: Check process command line
        if [[ -z "$ENVIRONMENT" ]]; then
            local cmd_line=$(ps -o args= -p $$ 2>/dev/null || echo "")
            local parent_cmd=$(ps -o args= -p $PPID 2>/dev/null || echo "")
            
            for pattern in "dev" "staging" "prod" "prd"; do
                if [[ "$cmd_line" == *"-$pattern"* ]] || [[ "$parent_cmd" == *"-$pattern"* ]]; then
                    ENVIRONMENT="$pattern"
                    [[ "$ENVIRONMENT" == "prd" ]] && ENVIRONMENT="prod"
                    break
                fi
            done
        fi
        
        # Method 3: Check script arguments
        if [[ -z "$ENVIRONMENT" ]]; then
            local all_args="$(basename "$0") $*"
            for pattern in "dev" "staging" "prod" "prd"; do
                if [[ "$all_args" == *"-$pattern"* ]]; then
                    ENVIRONMENT="$pattern"
                    [[ "$ENVIRONMENT" == "prd" ]] && ENVIRONMENT="prod"
                    break
                fi
            done
        fi
        
        # Method 4: Check MAKEFLAGS for environment
        if [[ -z "$ENVIRONMENT" ]] && [[ -n "${MAKEFLAGS:-}" ]]; then
            for pattern in "dev" "staging" "prod" "prd"; do
                if [[ "$MAKEFLAGS" == *"-$pattern"* ]]; then
                    ENVIRONMENT="$pattern"
                    [[ "$ENVIRONMENT" == "prd" ]] && ENVIRONMENT="prod"
                    break
                fi
            done
        fi
        
        # Final fallback
        if [[ -z "$ENVIRONMENT" ]]; then
            require_environment
        fi
    fi
    
    log_section "HIPAA Infrastructure Environment Setup"
    log_info "Phase 1: Root Account → Service User Creation"
    
    # Validate prerequisites
    check_prerequisites
    validate_setup_prerequisites
    
    # Create environments config if it doesn't exist
    if [[ ! -f "$ENVIRONMENTS_CONFIG" ]]; then
        log_warning "Environments configuration not found"
        create_example_environments_config
        die "Please edit $ENVIRONMENTS_CONFIG with your account details and run again"
    fi
    
    # Show detected environment
    log_info "Detected environment: $ENVIRONMENT"
    
    # Show dry-run mode if enabled
    if is_dry_run; then
        log_warning "DRY RUN MODE: No changes will be made"
        echo ""
    fi
    
    # Setup the specified environment
    setup_environment "$ENVIRONMENT"
    
    echo ""
    log_section "Setup Complete"
    log_success "Environment '$ENVIRONMENT' is ready for deployment"
    echo ""
    log_info "Next Steps:"
    echo "  1. Test service user access:"
    echo "     aws sts get-caller-identity --profile pulumi-deploy-user-$ENVIRONMENT"
    echo ""
    echo "  2. Deploy infrastructure:"
    echo "     ./scripts/deploy.sh -e $ENVIRONMENT"
    echo ""
    log_warning "SECURITY: Store credentials securely and rotate regularly"
}

# Run main function
main "$@"