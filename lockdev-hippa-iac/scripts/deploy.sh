#!/bin/bash

# HIPAA Infrastructure Deployment
# Phase 2 of the security model: Uses SERVICE USER credentials for Pulumi operations
#
# This script:
# 1. Uses service user credentials (pulumi-deploy-user-<env>)
# 2. Performs Pulumi infrastructure deployment operations
# 3. Supports preview, deploy, and destroy operations
# 4. Maintains audit trail and security compliance
#
# Security Model:
# Root Account (setup) → SERVICE USER (operations) → Pulumi Resources

set -e

# Load shared utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Script-specific configuration
OPERATION="deploy"  # deploy, preview, destroy
OUTPUT_DIR="$PROJECT_DIR/outputs"

# Help function
show_help() {
    echo -e "${GREEN}HIPAA Infrastructure Deployment${NC}"
    echo ""
    echo -e "${YELLOW}Phase 2: Service User → Pulumi Operations${NC}"
    echo ""
    echo "This script uses SERVICE USER credentials to deploy infrastructure"
    echo "with Pulumi. If service users don't exist, they are created automatically."
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    show_common_help
    echo "Deployment Options:"
    echo "  -o, --operation OP      Operation: deploy, preview, destroy (default: deploy)"
    echo "  --output-dir DIR        Directory for deployment outputs (default: outputs/)"
    echo ""
    echo "Examples:"
    echo "  $0 -e dev                        # Smart deploy (auto-setup if needed)"
    echo "  $0 -e staging -o preview         # Preview staging changes"
    echo "  $0 -e prod -o destroy            # Destroy production (careful!)"
    echo "  $0 -e dev --dry-run              # Show what would be deployed"
    echo ""
    echo "Smart Deployment:"
    echo "  • Detects if service user exists"
    echo "  • Auto-runs setup-env.sh if service user missing"
    echo "  • Requires root credentials for auto-setup"
    echo "  • Falls back to manual setup instructions if needed"
    echo ""
    echo "Security Model:"
    echo "  1. AUTO-DETECT: Service user missing?"
    echo "  2. AUTO-SETUP: ROOT credentials → Create service user (if needed)"
    echo "  3. DEPLOY: SERVICE credentials → Deploy infrastructure"
    echo ""
    echo "Prerequisites:"
    echo "  - AWS CLI configured with root account profiles (for auto-setup)"
    echo "  - Pulumi logged in"
    echo ""
}

# Smart validation - checks service user and auto-sets up if needed
smart_validate_service_user() {
    local environment="$1"
    local service_profile="$2"
    local region="$3"
    local user_name="$4"
    
    log_step "Smart validation: Checking service user access"
    
    # Check if service user exists and works
    if service_user_exists "$environment"; then
        log_success "Service user found and working: $service_profile"
        
        # Validate AWS credentials
        local account_id=$(validate_aws_credentials "$service_profile" "$region")
        
        # Verify this is the expected service user
        local current_user=$(AWS_PROFILE="$service_profile" aws sts get-caller-identity --query Arn --output text)
        if [[ ! "$current_user" == *":user/$user_name" ]]; then
            log_warning "Expected service user: $user_name"
            log_warning "Current user ARN: $current_user"
            if ! is_force_mode; then
                confirm_action "Continue with different user?" "continue"
            fi
        fi
        
        log_success "Service user validation complete"
        echo "$account_id"
        return 0
    else
        # Service user missing - attempt auto-setup
        log_warning "Service user not found or not working: $service_profile"
        
        if is_dry_run; then
            log_info "[DRY RUN] Would attempt auto-setup of service user"
            echo "unknown-account-id"
            return 0
        fi
        
        # Attempt automatic setup
        if auto_setup_service_user "$environment"; then
            log_success "Auto-setup completed! Retrying validation..."
            
            # Retry validation after setup
            if service_user_exists "$environment"; then
                local account_id=$(validate_aws_credentials "$service_profile" "$region")
                log_success "Service user now ready for deployment"
                echo "$account_id"
                return 0
            else
                die "Auto-setup completed but service user still not working"
            fi
        else
            die "Auto-setup failed. Manual setup required."
        fi
    fi
}

# Deploy infrastructure to environment
deploy_infrastructure() {
    local environment="$1"
    
    log_section "Deploying Infrastructure: $environment"
    
    # Load environment configuration
    load_environment_config "$environment"
    
    # Get environment settings
    local service_profile=$(get_env_config "$environment" "service_profile")
    local region=$(get_env_config "$environment" "region")
    local stack_prefix=$(get_env_config "$environment" "stack_prefix")
    local user_name=$(get_env_config "$environment" "service_user.name")
    
    log_info "Environment: $environment"
    log_info "Service Profile: $service_profile"
    log_info "Region: $region"
    log_info "Stack: $stack_prefix-$environment"
    
    # Smart validation - auto-setup if needed
    local account_id=$(smart_validate_service_user "$environment" "$service_profile" "$region" "$user_name")
    
    # Setup AWS environment for deployment
    setup_aws_env "$service_profile" "$region"
    
    # Setup Pulumi stack
    local stack_name="$stack_prefix-$environment"
    setup_pulumi_stack "$stack_name" "$environment" "$region"
    
    # Set additional Pulumi configuration
    poetry run pulumi config set account_id "$account_id"
    
    # Ensure database password is configured
    setup_database_password
    
    # Set tags from environment configuration
    local tags=$(yq eval ".environments.$environment.tags // {}" "$ENVIRONMENTS_CONFIG" -o json)
    if [[ "$tags" != "null" && "$tags" != "{}" ]]; then
        # Set each tag individually to avoid provider config issues
        echo "$tags" | jq -r 'to_entries[] | "\(.key)=\(.value)"' | while read -r tag; do
            local key=$(echo "$tag" | cut -d'=' -f1)
            local value=$(echo "$tag" | cut -d'=' -f2-)
            poetry run pulumi config set "aws:defaultTags:$key" "$value" 2>/dev/null || true
        done
    fi
    
    # Perform the requested operation
    case "$OPERATION" in
        "preview")
            preview_changes "$environment" "$stack_name"
            ;;
        "deploy")
            deploy_changes "$environment" "$stack_name"
            ;;
        "destroy")
            destroy_infrastructure "$environment" "$stack_name"
            ;;
        *)
            die "Unknown operation: $OPERATION"
            ;;
    esac
}

# Preview infrastructure changes
preview_changes() {
    local environment="$1"
    local stack_name="$2"
    
    log_step "Previewing infrastructure changes for: $environment"
    
    if is_dry_run; then
        log_info "[DRY RUN] Would preview Pulumi stack: $stack_name"
        return
    fi
    
    poetry run pulumi preview --diff --show-replacement-steps
    
    log_success "Preview complete for: $environment"
}

# Deploy infrastructure changes
deploy_changes() {
    local environment="$1"
    local stack_name="$2"
    
    log_step "Deploying infrastructure changes for: $environment"
    
    # Confirmation for deployment
    if ! is_force_mode && ! is_dry_run; then
        echo ""
        log_warning "About to deploy infrastructure to: $environment"
        log_warning "This will create/modify AWS resources"
        echo ""
        confirm_action "Continue with deployment?" "deploy"
    fi
    
    if is_dry_run; then
        log_info "[DRY RUN] Would deploy Pulumi stack: $stack_name"
        return
    fi
    
    # Perform deployment
    if is_force_mode; then
        poetry run pulumi up --yes
    else
        poetry run pulumi up
    fi
    
    # Save deployment outputs
    save_deployment_outputs "$environment" "$stack_name"
    
    log_success "Deployment complete for: $environment"
}

# Destroy infrastructure
destroy_infrastructure() {
    local environment="$1"
    local stack_name="$2"
    
    log_step "Destroying infrastructure for: $environment"
    
    # Strong confirmation for destruction
    if ! is_force_mode; then
        echo ""
        log_error "⚠️  WARNING: INFRASTRUCTURE DESTRUCTION"
        log_error "This will PERMANENTLY DELETE all resources in: $environment"
        log_error "Including databases, storage, and ALL DATA!"
        echo ""
        log_error "This action CANNOT BE UNDONE!"
        echo ""
        
        # Multiple confirmation steps
        confirm_action "Type environment name to confirm destruction" "$environment"
        
        # Generate random confirmation code
        local confirm_code=$(openssl rand -hex 4 2>/dev/null || echo "$(date +%s)")
        echo ""
        log_warning "Final confirmation. Type this code: $confirm_code"
        read -p "Enter code: " user_code
        if [[ "$user_code" != "$confirm_code" ]]; then
            log_warning "Code mismatch. Destruction cancelled."
            exit 0
        fi
    fi
    
    if is_dry_run; then
        log_info "[DRY RUN] Would destroy Pulumi stack: $stack_name"
        return
    fi
    
    # Perform destruction
    if is_force_mode; then
        poetry run pulumi destroy --yes
    else
        poetry run pulumi destroy
    fi
    
    log_success "Infrastructure destroyed for: $environment"
    log_warning "Verify all AWS resources are deleted in the console"
}

# Save deployment outputs to file
save_deployment_outputs() {
    local environment="$1"
    local stack_name="$2"
    
    log_step "Saving deployment outputs"
    
    # Ensure output directory exists
    mkdir -p "$OUTPUT_DIR"
    
    # Save outputs to JSON file
    local output_file="$OUTPUT_DIR/$environment-outputs.json"
    poetry run pulumi stack output --json > "$output_file"
    
    log_success "Outputs saved to: $output_file"
    
    # Display key outputs
    if command -v jq &> /dev/null && [[ -f "$output_file" ]]; then
        echo ""
        log_info "Key deployment outputs:"
        
        # Show common outputs if they exist
        local alb_dns=$(jq -r '.alb_dns_name // empty' "$output_file")
        local ecr_url=$(jq -r '.ecr_repository_url // empty' "$output_file")
        local vpc_id=$(jq -r '.vpc_id // empty' "$output_file")
        
        [[ -n "$alb_dns" ]] && echo -e "${BLUE}  ALB DNS: ${CYAN}$alb_dns${NC}"
        [[ -n "$ecr_url" ]] && echo -e "${BLUE}  ECR URL: ${CYAN}$ecr_url${NC}"
        [[ -n "$vpc_id" ]] && echo -e "${BLUE}  VPC ID: ${CYAN}$vpc_id${NC}"
        
        echo ""
        log_info "Full outputs available in: $output_file"
    fi
}

# Parse script-specific arguments
parse_deploy_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -o|--operation)
                OPERATION="$2"
                shift 2
                ;;
            --output-dir)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            *)
                # Return unrecognized args for common parsing
                echo "$@"
                return 0
                ;;
        esac
    done
}

# Validate deployment prerequisites
validate_deployment_prerequisites() {
    log_step "Validating deployment prerequisites..."
    
    # Check if we're in a git repository (good practice)
    if [[ ! -d "$PROJECT_DIR/.git" ]]; then
        log_warning "Not in a git repository. Consider using version control."
    fi
    
    # Validate operation
    case "$OPERATION" in
        "preview"|"deploy"|"destroy")
            log_info "Operation: $OPERATION"
            ;;
        *)
            die "Invalid operation: $OPERATION. Use: preview, deploy, or destroy"
            ;;
    esac
    
    # Check if environments config exists
    if [[ ! -f "$ENVIRONMENTS_CONFIG" ]]; then
        log_error "Environments configuration not found: $ENVIRONMENTS_CONFIG"
        log_info "Create configuration with: make create-config"
        log_info "Then edit configs/environments.yaml with your AWS account details"
        die "Configuration required for smart deployment"
    fi
    
    # Validate environment exists in config
    load_environment_config "$ENVIRONMENT"
    
    # Check root profile configuration (needed for auto-setup)
    local root_profile=$(get_env_config "$ENVIRONMENT" "root_profile")
    if [[ "$root_profile" == "null" || -z "$root_profile" ]]; then
        die "Root profile not configured for environment: $ENVIRONMENT. Check configs/environments.yaml"
    fi
    
    # Check service profile configuration
    local service_profile=$(get_env_config "$ENVIRONMENT" "service_profile")
    if [[ "$service_profile" == "null" || -z "$service_profile" ]]; then
        die "Service profile not configured for environment: $ENVIRONMENT. Check configs/environments.yaml"
    fi
    
    log_success "Deployment prerequisites validated"
    log_info "Smart deployment ready for environment: $ENVIRONMENT"
}

# Main function
main() {
    local remaining_args
    
    # Parse script-specific arguments first
    remaining_args=$(parse_deploy_args "$@")
    
    # Parse common arguments
    remaining_args=$(parse_common_args $remaining_args) || {
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
    
    log_section "HIPAA Infrastructure Smart Deployment"
    log_info "Smart Deployment: Auto-setup + Deploy"
    log_info "Operation: $OPERATION"
    log_info "Environment: $ENVIRONMENT"
    
    # Validate prerequisites
    check_prerequisites
    validate_deployment_prerequisites
    
    # Create environments config if it doesn't exist
    if [[ ! -f "$ENVIRONMENTS_CONFIG" ]]; then
        die "Environments configuration not found: $ENVIRONMENTS_CONFIG. Run setup-env.sh first."
    fi
    
    # Show dry-run mode if enabled
    if is_dry_run; then
        log_warning "DRY RUN MODE: No changes will be made"
        echo ""
    fi
    
    # Change to project directory for Pulumi operations
    cd "$PROJECT_DIR"
    
    # Perform deployment operation
    deploy_infrastructure "$ENVIRONMENT"
    
    echo ""
    log_section "Deployment Complete"
    
    case "$OPERATION" in
        "preview")
            log_success "Preview completed for environment: $ENVIRONMENT"
            echo ""
            log_info "To deploy: ./scripts/deploy.sh -e $ENVIRONMENT -o deploy"
            ;;
        "deploy")
            log_success "Deployment completed for environment: $ENVIRONMENT"
            echo ""
            log_info "Monitor resources in AWS Console"
            log_info "Outputs saved to: $OUTPUT_DIR/$ENVIRONMENT-outputs.json"
            ;;
        "destroy")
            log_success "Destruction completed for environment: $ENVIRONMENT"
            echo ""
            log_warning "Verify all resources are deleted in AWS Console"
            ;;
    esac
}

# Run main function
main "$@"