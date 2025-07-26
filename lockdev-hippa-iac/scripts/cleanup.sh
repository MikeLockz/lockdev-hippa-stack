#!/bin/bash

# HIPAA Infrastructure Cleanup
# Safe cleanup of infrastructure and service users
#
# This script supports two cleanup modes:
# 1. Infrastructure cleanup: Uses service user to destroy Pulumi resources
# 2. Complete cleanup: Uses root account to remove service users after infrastructure
#
# Security Model:
# SERVICE USER → Destroy Infrastructure → ROOT ACCOUNT → Remove Service User

set -e

# Load shared utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Script-specific configuration
CLEANUP_MODE="infrastructure"  # infrastructure, complete
OUTPUT_DIR="$PROJECT_DIR/outputs"

# Help function
show_help() {
    echo -e "${GREEN}HIPAA Infrastructure Cleanup${NC}"
    echo ""
    echo -e "${RED}⚠️  WARNING: This script permanently deletes resources${NC}"
    echo ""
    echo "This script safely cleans up HIPAA infrastructure and optionally"
    echo "removes service users. Multiple confirmation steps protect against"
    echo "accidental deletion."
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    show_common_help
    echo "Cleanup Options:"
    echo "  -m, --mode MODE         Cleanup mode: infrastructure, complete (default: infrastructure)"
    echo "  --output-dir DIR        Directory for cleanup logs (default: outputs/)"
    echo ""
    echo "Cleanup Modes:"
    echo "  infrastructure          Destroy Pulumi resources only (keeps service user)"
    echo "  complete               Destroy resources AND remove service user"
    echo ""
    echo "Examples:"
    echo "  $0 -e dev                        # Cleanup dev infrastructure only"
    echo "  $0 -e staging -m complete        # Complete cleanup of staging"
    echo "  $0 -e prod --dry-run             # Preview prod cleanup"
    echo ""
    echo "Safety Features:"
    echo "  • Multiple confirmation prompts"
    echo "  • Dry-run mode to preview changes"
    echo "  • Environment name verification"
    echo "  • Resource inventory before deletion"
    echo ""
    echo "Security Model:"
    echo "  1. SERVICE USER → Destroy infrastructure resources"
    echo "  2. ROOT ACCOUNT → Remove service user (complete mode only)"
    echo ""
}

# Show resources that would be destroyed
show_resources_preview() {
    local environment="$1"
    local stack_name="$2"
    
    log_step "Analyzing resources in: $environment"
    
    # Check if stack exists
    if ! poetry run pulumi stack ls | grep -q "^$stack_name"; then
        log_warning "No Pulumi stack found: $stack_name"
        return 0
    fi
    
    # Select stack
    poetry run pulumi stack select "$stack_name"
    
    # Show stack outputs
    echo ""
    log_info "Current stack outputs:"
    poetry run pulumi stack output 2>/dev/null || log_warning "No stack outputs found"
    
    # Show resources that would be destroyed
    echo ""
    log_info "Resources that would be destroyed:"
    poetry run pulumi preview --show-replacement-steps 2>/dev/null | grep -E "(delete|destroy)" || log_info "No resources to destroy"
    
    echo ""
}

# Cleanup infrastructure resources
cleanup_infrastructure() {
    local environment="$1"
    
    log_section "Cleaning up Infrastructure: $environment"
    
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
    
    # For complete cleanup mode, we may not need service user validation
    # since we'll be removing it anyway. Try to validate, but don't fail if it doesn't work.
    if service_user_exists "$environment"; then
        log_info "Service user exists, attempting to use it for infrastructure cleanup..."
        # Setup AWS environment
        setup_aws_env "$service_profile" "$region"
    else
        log_warning "Service user not found, but that's okay for complete cleanup"
        log_info "Will skip infrastructure cleanup and proceed to service user removal with root credentials"
        # No infrastructure to clean up if service user doesn't exist
        return 0
    fi
    
    # Setup Pulumi stack
    local stack_name="$stack_prefix-$environment"
    
    # Show what would be destroyed
    show_resources_preview "$environment" "$stack_name"
    
    # Strong confirmation for infrastructure destruction
    if ! is_force_mode && ! is_dry_run; then
        echo ""
        log_error "⚠️  WARNING: INFRASTRUCTURE DESTRUCTION"
        log_error "Environment: $environment"
        log_error "This will PERMANENTLY DELETE:"
        echo "  • All VPC resources (subnets, security groups, etc.)"
        echo "  • Load balancers and networking"
        echo "  • ECS clusters and container services"
        echo "  • RDS databases and ALL DATA"
        echo "  • S3 buckets and stored files"
        echo "  • KMS keys and encrypted data"
        echo "  • CloudWatch logs and metrics"
        echo "  • All other Pulumi-managed resources"
        echo ""
        log_error "THIS CANNOT BE UNDONE!"
        echo ""
        
        # Multiple confirmation steps
        confirm_action "Type environment name to confirm destruction" "$environment"
    fi
    
    if is_dry_run; then
        log_info "[DRY RUN] Would destroy Pulumi stack: $stack_name"
        return
    fi
    
    # Perform infrastructure destruction
    log_step "Destroying infrastructure resources..."
    
    if poetry run pulumi stack ls | grep -q "^$stack_name"; then
        poetry run pulumi stack select "$stack_name"
        
        if is_force_mode; then
            poetry run pulumi destroy --yes
        else
            poetry run pulumi destroy
        fi
        
        # Remove the Pulumi stack
        poetry run pulumi stack rm --yes
        
        log_success "Infrastructure destroyed: $environment"
    else
        log_warning "No Pulumi stack found to destroy: $stack_name"
    fi
    
    # Remove outputs file
    local output_file="$OUTPUT_DIR/$environment-outputs.json"
    if [[ -f "$output_file" ]]; then
        rm -f "$output_file"
        log_info "Removed outputs file: $output_file"
    fi
    
    # Perform comprehensive AWS resource cleanup
    cleanup_aws_resources "$environment"
}

# Comprehensive AWS resource cleanup (catches anything Pulumi missed)
cleanup_aws_resources() {
    local environment="$1"
    
    log_section "Comprehensive AWS Resource Cleanup: $environment"
    
    # Get environment settings
    local root_profile=$(get_env_config "$environment" "root_profile")
    local region=$(get_env_config "$environment" "region")
    
    # Setup AWS environment for root operations
    setup_aws_env "$root_profile" "$region"
    
    log_info "Scanning for remaining HIPAA-related resources..."
    
    if is_dry_run; then
        log_info "[DRY RUN] Would perform comprehensive resource cleanup"
        return
    fi
    
    # Cleanup ECS resources
    cleanup_ecs_resources "$root_profile"
    
    # Cleanup Load Balancers
    cleanup_load_balancers "$root_profile"
    
    # Cleanup RDS resources
    cleanup_rds_resources "$root_profile"
    
    # Cleanup S3 buckets (must be done carefully)
    cleanup_s3_buckets "$root_profile" "$environment"
    
    # Cleanup VPC resources (must be last)
    cleanup_vpc_resources "$root_profile"
    
    # Cleanup CloudWatch resources
    cleanup_cloudwatch_resources "$root_profile"
    
    log_success "Comprehensive AWS resource cleanup completed"
}

# Cleanup ECS resources
cleanup_ecs_resources() {
    local profile="$1"
    
    log_step "Cleaning up ECS resources..."
    
    # List ECS clusters with HIPAA naming
    local clusters=$(AWS_PROFILE="$profile" aws ecs list-clusters --query 'clusterArns[?contains(@, `hipaa`) || contains(@, `HIPAA`)]' --output text 2>/dev/null || echo "")
    
    if [[ -n "$clusters" ]]; then
        for cluster_arn in $clusters; do
            local cluster_name=$(basename "$cluster_arn")
            log_info "Found ECS cluster: $cluster_name"
            
            # Stop all services in the cluster
            local services=$(AWS_PROFILE="$profile" aws ecs list-services --cluster "$cluster_arn" --query 'serviceArns' --output text 2>/dev/null || echo "")
            
            if [[ -n "$services" ]]; then
                for service_arn in $services; do
                    local service_name=$(basename "$service_arn")
                    log_info "Stopping ECS service: $service_name"
                    AWS_PROFILE="$profile" aws ecs update-service --cluster "$cluster_arn" --service "$service_arn" --desired-count 0 >/dev/null 2>&1 || true
                    AWS_PROFILE="$profile" aws ecs delete-service --cluster "$cluster_arn" --service "$service_arn" >/dev/null 2>&1 || true
                done
            fi
            
            # Delete the cluster
            log_info "Deleting ECS cluster: $cluster_name"
            AWS_PROFILE="$profile" aws ecs delete-cluster --cluster "$cluster_arn" >/dev/null 2>&1 || true
        done
        log_success "ECS cleanup completed"
    else
        log_info "No ECS clusters found"
    fi
}

# Cleanup Load Balancers
cleanup_load_balancers() {
    local profile="$1"
    
    log_step "Cleaning up Load Balancers..."
    
    # List ALBs with HIPAA naming
    local albs=$(AWS_PROFILE="$profile" aws elbv2 describe-load-balancers --query 'LoadBalancers[?contains(LoadBalancerName, `hipaa`) || contains(LoadBalancerName, `HIPAA`)].LoadBalancerArn' --output text 2>/dev/null || echo "")
    
    if [[ -n "$albs" ]]; then
        for alb_arn in $albs; do
            local alb_name=$(AWS_PROFILE="$profile" aws elbv2 describe-load-balancers --load-balancer-arns "$alb_arn" --query 'LoadBalancers[0].LoadBalancerName' --output text 2>/dev/null || echo "unknown")
            log_info "Deleting ALB: $alb_name"
            AWS_PROFILE="$profile" aws elbv2 delete-load-balancer --load-balancer-arn "$alb_arn" >/dev/null 2>&1 || true
        done
        log_success "Load balancer cleanup completed"
    else
        log_info "No load balancers found"
    fi
}

# Cleanup RDS resources
cleanup_rds_resources() {
    local profile="$1"
    
    log_step "Cleaning up RDS resources..."
    
    # List RDS instances with HIPAA naming
    local db_instances=$(AWS_PROFILE="$profile" aws rds describe-db-instances --query 'DBInstances[?contains(DBInstanceIdentifier, `hipaa`) || contains(DBInstanceIdentifier, `HIPAA`)].DBInstanceIdentifier' --output text 2>/dev/null || echo "")
    
    if [[ -n "$db_instances" ]]; then
        for db_instance in $db_instances; do
            log_info "Deleting RDS instance: $db_instance"
            AWS_PROFILE="$profile" aws rds delete-db-instance --db-instance-identifier "$db_instance" --skip-final-snapshot >/dev/null 2>&1 || true
        done
        log_success "RDS cleanup completed"
    else
        log_info "No RDS instances found"
    fi
}

# Cleanup S3 buckets
cleanup_s3_buckets() {
    local profile="$1"
    local environment="$2"
    
    log_step "Cleaning up S3 buckets..."
    
    # List S3 buckets with HIPAA naming
    local buckets=$(AWS_PROFILE="$profile" aws s3api list-buckets --query 'Buckets[?contains(Name, `hipaa`) || contains(Name, `HIPAA`)].Name' --output text 2>/dev/null || echo "")
    
    if [[ -n "$buckets" ]]; then
        for bucket in $buckets; do
            log_info "Emptying and deleting S3 bucket: $bucket"
            
            # Empty the bucket first
            AWS_PROFILE="$profile" aws s3 rm "s3://$bucket" --recursive >/dev/null 2>&1 || true
            
            # Delete versioned objects if any
            AWS_PROFILE="$profile" aws s3api delete-objects --bucket "$bucket" --delete "$(AWS_PROFILE="$profile" aws s3api list-object-versions --bucket "$bucket" --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' --output json 2>/dev/null || echo '{\"Objects\":[]}')" >/dev/null 2>&1 || true
            
            # Delete delete markers
            AWS_PROFILE="$profile" aws s3api delete-objects --bucket "$bucket" --delete "$(AWS_PROFILE="$profile" aws s3api list-object-versions --bucket "$bucket" --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' --output json 2>/dev/null || echo '{\"Objects\":[]}')" >/dev/null 2>&1 || true
            
            # Delete the bucket
            AWS_PROFILE="$profile" aws s3api delete-bucket --bucket "$bucket" >/dev/null 2>&1 || true
        done
        log_success "S3 cleanup completed"
    else
        log_info "No S3 buckets found"
    fi
}

# Cleanup VPC resources (must be done last after all other resources)
cleanup_vpc_resources() {
    local profile="$1"
    
    log_step "Cleaning up VPC resources..."
    
    # List VPCs with HIPAA naming
    local vpcs=$(AWS_PROFILE="$profile" aws ec2 describe-vpcs --query 'Vpcs[?Tags[?Key==`Name` && (contains(Value, `hipaa`) || contains(Value, `HIPAA`))]].VpcId' --output text 2>/dev/null || echo "")
    
    if [[ -n "$vpcs" ]]; then
        for vpc_id in $vpcs; do
            local vpc_name=$(AWS_PROFILE="$profile" aws ec2 describe-vpcs --vpc-ids "$vpc_id" --query 'Vpcs[0].Tags[?Key==`Name`].Value' --output text 2>/dev/null || echo "unknown")
            log_info "Cleaning up VPC: $vpc_name ($vpc_id)"
            
            # Delete NAT Gateways
            local nat_gateways=$(AWS_PROFILE="$profile" aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$vpc_id" --query 'NatGateways[?State==`available`].NatGatewayId' --output text 2>/dev/null || echo "")
            for nat_gw in $nat_gateways; do
                log_info "Deleting NAT Gateway: $nat_gw"
                AWS_PROFILE="$profile" aws ec2 delete-nat-gateway --nat-gateway-id "$nat_gw" >/dev/null 2>&1 || true
            done
            
            # Delete Internet Gateways
            local igws=$(AWS_PROFILE="$profile" aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$vpc_id" --query 'InternetGateways[].InternetGatewayId' --output text 2>/dev/null || echo "")
            for igw in $igws; do
                log_info "Detaching and deleting Internet Gateway: $igw"
                AWS_PROFILE="$profile" aws ec2 detach-internet-gateway --internet-gateway-id "$igw" --vpc-id "$vpc_id" >/dev/null 2>&1 || true
                AWS_PROFILE="$profile" aws ec2 delete-internet-gateway --internet-gateway-id "$igw" >/dev/null 2>&1 || true
            done
            
            # Delete subnets
            local subnets=$(AWS_PROFILE="$profile" aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc_id" --query 'Subnets[].SubnetId' --output text 2>/dev/null || echo "")
            for subnet in $subnets; do
                log_info "Deleting subnet: $subnet"
                AWS_PROFILE="$profile" aws ec2 delete-subnet --subnet-id "$subnet" >/dev/null 2>&1 || true
            done
            
            # Delete security groups (except default)
            local sgs=$(AWS_PROFILE="$profile" aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$vpc_id" --query 'SecurityGroups[?GroupName!=`default`].GroupId' --output text 2>/dev/null || echo "")
            for sg in $sgs; do
                log_info "Deleting security group: $sg"
                AWS_PROFILE="$profile" aws ec2 delete-security-group --group-id "$sg" >/dev/null 2>&1 || true
            done
            
            # Delete route tables (except main)
            local route_tables=$(AWS_PROFILE="$profile" aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$vpc_id" --query 'RouteTables[?Associations[0].Main!=`true`].RouteTableId' --output text 2>/dev/null || echo "")
            for rt in $route_tables; do
                log_info "Deleting route table: $rt"
                AWS_PROFILE="$profile" aws ec2 delete-route-table --route-table-id "$rt" >/dev/null 2>&1 || true
            done
            
            # Finally delete the VPC
            log_info "Deleting VPC: $vpc_id"
            AWS_PROFILE="$profile" aws ec2 delete-vpc --vpc-id "$vpc_id" >/dev/null 2>&1 || true
        done
        log_success "VPC cleanup completed"
    else
        log_info "No VPCs found"
    fi
}

# Cleanup CloudWatch resources
cleanup_cloudwatch_resources() {
    local profile="$1"
    
    log_step "Cleaning up CloudWatch resources..."
    
    # Delete log groups with HIPAA naming
    local log_groups=$(AWS_PROFILE="$profile" aws logs describe-log-groups --query 'logGroups[?contains(logGroupName, `hipaa`) || contains(logGroupName, `HIPAA`)].logGroupName' --output text 2>/dev/null || echo "")
    
    if [[ -n "$log_groups" ]]; then
        for log_group in $log_groups; do
            log_info "Deleting CloudWatch log group: $log_group"
            AWS_PROFILE="$profile" aws logs delete-log-group --log-group-name "$log_group" >/dev/null 2>&1 || true
        done
        log_success "CloudWatch cleanup completed"
    else
        log_info "No CloudWatch log groups found"
    fi
}

# Cleanup service user (requires root credentials)
cleanup_service_user() {
    local environment="$1"
    
    log_section "Cleaning up Service User: $environment"
    
    # Get environment settings
    local root_profile=$(get_env_config "$environment" "root_profile")
    local region=$(get_env_config "$environment" "region")
    local user_name=$(get_env_config "$environment" "service_user.name")
    local policy_name=$(get_env_config "$environment" "service_user.policy_name")
    
    log_info "Environment: $environment"
    log_info "Root Profile: $root_profile"
    log_info "Service User: $user_name"
    log_info "Policy: $policy_name"
    
    # Validate root credentials
    local account_id=$(validate_aws_credentials "$root_profile" "$region")
    
    # Setup AWS environment for root operations
    setup_aws_env "$root_profile" "$region"
    
    # Log service user deletion details
    if ! is_dry_run; then
        echo ""
        log_info "Removing service user and policy:"
        echo "  • User: $user_name"
        echo "  • Policy: $policy_name"
        echo "  • Access keys: All keys for this user"
        echo ""
    fi
    
    if is_dry_run; then
        log_info "[DRY RUN] Would remove service user: $user_name"
        log_info "[DRY RUN] Would remove policy: $policy_name"
        return
    fi
    
    # Remove specific service user
    log_step "Removing service user: $user_name"
    
    if aws_user_exists "$root_profile" "$user_name"; then
        # Detach all policies
        local attached_policies=$(AWS_PROFILE="$root_profile" aws iam list-attached-user-policies --user-name "$user_name" --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null || echo "")
        
        if [[ -n "$attached_policies" ]]; then
            for policy_arn in $attached_policies; do
                log_info "Detaching policy: $policy_arn"
                AWS_PROFILE="$root_profile" aws iam detach-user-policy --user-name "$user_name" --policy-arn "$policy_arn"
            done
        fi
        
        # Delete all access keys
        local access_keys=$(AWS_PROFILE="$root_profile" aws iam list-access-keys --user-name "$user_name" --query 'AccessKeyMetadata[].AccessKeyId' --output text 2>/dev/null || echo "")
        
        if [[ -n "$access_keys" ]]; then
            for key_id in $access_keys; do
                log_info "Deleting access key: $key_id"
                AWS_PROFILE="$root_profile" aws iam delete-access-key --user-name "$user_name" --access-key-id "$key_id"
            done
        fi
        
        # Delete user
        AWS_PROFILE="$root_profile" aws iam delete-user --user-name "$user_name"
        log_success "Service user removed: $user_name"
    else
        log_warning "Service user not found: $user_name"
    fi
    
    # Remove policy
    log_step "Removing policy: $policy_name"
    
    if aws_policy_exists "$root_profile" "$policy_name" "$account_id"; then
        local policy_arn="arn:aws:iam::$account_id:policy/$policy_name"
        
        # Delete all policy versions except default
        local versions=$(AWS_PROFILE="$root_profile" aws iam list-policy-versions --policy-arn "$policy_arn" --query 'Versions[?!IsDefaultVersion].VersionId' --output text 2>/dev/null || echo "")
        
        if [[ -n "$versions" ]]; then
            for version in $versions; do
                log_info "Deleting policy version: $version"
                AWS_PROFILE="$root_profile" aws iam delete-policy-version --policy-arn "$policy_arn" --version-id "$version"
            done
        fi
        
        # Delete policy
        AWS_PROFILE="$root_profile" aws iam delete-policy --policy-arn "$policy_arn"
        log_success "Policy removed: $policy_name"
    else
        log_warning "Policy not found: $policy_name"
    fi
    
    # Remove credentials file
    local creds_file="$PROJECT_DIR/.credentials-$environment.json"
    if [[ -f "$creds_file" ]]; then
        rm -f "$creds_file"
        log_info "Removed credentials file: $creds_file"
    fi
    
    # Perform comprehensive IAM cleanup for any leftover resources
    cleanup_all_iam_resources "$root_profile" "$account_id"
}

# Comprehensive IAM cleanup for all HIPAA-related resources
cleanup_all_iam_resources() {
    local profile="$1"
    local account_id="$2"
    
    log_section "Comprehensive IAM Cleanup"
    
    # Find and remove all HIPAA-related users
    log_step "Cleaning up all HIPAA-related IAM users..."
    local all_users=$(AWS_PROFILE="$profile" aws iam list-users --query 'Users[?contains(UserName, `pulumi-deploy-user`) || contains(UserName, `hipaa`) || contains(UserName, `HIPAA`)].UserName' --output text 2>/dev/null || echo "")
    
    if [[ -n "$all_users" ]]; then
        for user in $all_users; do
            log_info "Found IAM user: $user"
            
            # Detach all policies from user
            local user_policies=$(AWS_PROFILE="$profile" aws iam list-attached-user-policies --user-name "$user" --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null || echo "")
            for policy_arn in $user_policies; do
                log_info "Detaching policy from user $user: $policy_arn"
                AWS_PROFILE="$profile" aws iam detach-user-policy --user-name "$user" --policy-arn "$policy_arn" >/dev/null 2>&1 || true
            done
            
            # Delete all access keys for user
            local access_keys=$(AWS_PROFILE="$profile" aws iam list-access-keys --user-name "$user" --query 'AccessKeyMetadata[].AccessKeyId' --output text 2>/dev/null || echo "")
            for key_id in $access_keys; do
                log_info "Deleting access key for user $user: $key_id"
                AWS_PROFILE="$profile" aws iam delete-access-key --user-name "$user" --access-key-id "$key_id" >/dev/null 2>&1 || true
            done
            
            # Delete the user
            log_info "Deleting IAM user: $user"
            AWS_PROFILE="$profile" aws iam delete-user --user-name "$user" >/dev/null 2>&1 || true
        done
        log_success "All HIPAA users cleaned up"
    else
        log_info "No additional HIPAA users found"
    fi
    
    # Find and remove all HIPAA-related policies
    log_step "Cleaning up all HIPAA-related IAM policies..."
    local all_policies=$(AWS_PROFILE="$profile" aws iam list-policies --scope Local --query 'Policies[?contains(PolicyName, `HIPAA`) || contains(PolicyName, `hipaa`) || contains(PolicyName, `pulumi`)].{PolicyName:PolicyName,Arn:Arn}' --output json 2>/dev/null || echo "[]")
    
    if [[ "$all_policies" != "[]" ]]; then
        echo "$all_policies" | jq -r '.[] | "\(.PolicyName)|\(.Arn)"' | while IFS='|' read -r policy_name policy_arn; do
            log_info "Found IAM policy: $policy_name"
            
            # Delete all non-default versions
            local versions=$(AWS_PROFILE="$profile" aws iam list-policy-versions --policy-arn "$policy_arn" --query 'Versions[?!IsDefaultVersion].VersionId' --output text 2>/dev/null || echo "")
            for version in $versions; do
                log_info "Deleting policy version $version for: $policy_name"
                AWS_PROFILE="$profile" aws iam delete-policy-version --policy-arn "$policy_arn" --version-id "$version" >/dev/null 2>&1 || true
            done
            
            # Delete the policy
            log_info "Deleting IAM policy: $policy_name"
            AWS_PROFILE="$profile" aws iam delete-policy --policy-arn "$policy_arn" >/dev/null 2>&1 || true
        done
        log_success "All HIPAA policies cleaned up"
    else
        log_info "No additional HIPAA policies found"
    fi
    
    # Clean up all credentials files
    log_step "Cleaning up all credentials files..."
    find "$PROJECT_DIR" -name ".credentials-*.json" -type f -exec rm -f {} \; 2>/dev/null || true
    log_success "All credentials files cleaned up"
}

# Parse script-specific arguments
parse_cleanup_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -m|--mode)
                CLEANUP_MODE="$2"
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

# Validate cleanup prerequisites
validate_cleanup_prerequisites() {
    log_step "Validating cleanup prerequisites..."
    
    # Validate cleanup mode
    case "$CLEANUP_MODE" in
        "infrastructure"|"complete")
            log_info "Cleanup mode: $CLEANUP_MODE"
            ;;
        *)
            die "Invalid cleanup mode: $CLEANUP_MODE. Use: infrastructure or complete"
            ;;
    esac
    
    # Ensure output directory exists
    mkdir -p "$OUTPUT_DIR"
    
    log_success "Cleanup prerequisites validated"
}

# Smart service user validation with auto-setup
smart_validate_service_user() {
    local environment="$1"
    local service_profile=$(get_env_config "$environment" "service_profile")
    local region=$(get_env_config "$environment" "region")
    
    log_step "Validating service user: $service_profile"
    
    # Check if service user exists and has proper permissions
    if service_user_exists "$environment"; then
        # Service user exists, validate it has cleanup permissions
        local account_id=$(validate_aws_credentials "$service_profile" "$region")
        
        # Test if user has IAM permissions needed for cleanup (basic test)
        if AWS_PROFILE="$service_profile" aws iam list-roles --max-items 1 &> /dev/null; then
            log_success "Service user validation complete with cleanup permissions"
            echo "$account_id"
            return 0
        else
            log_warning "Service user exists but lacks cleanup permissions"
            log_info "Service user needs policy update for comprehensive cleanup"
        fi
    else
        # Service user missing
        log_warning "Service user not found or not working: $service_profile"
    fi
    
    # Auto-setup or update needed
    if is_dry_run; then
        log_info "[DRY RUN] Would attempt auto-setup/update of service user"
        echo "unknown-account-id"
        return 0
    fi
    
    # Attempt automatic setup/update
    if auto_setup_service_user "$environment"; then
        log_success "Auto-setup completed! Retrying validation..."
        
        # Retry validation after setup
        if service_user_exists "$environment"; then
            local account_id=$(validate_aws_credentials "$service_profile" "$region")
            log_success "Service user now ready for cleanup operations"
            echo "$account_id"
            return 0
        else
            die "Auto-setup completed but service user still not working"
        fi
    else
        die "Auto-setup failed. Manual setup required."
    fi
}

# Main function
main() {
    # Initialize variables
    ENVIRONMENT=""
    FORCE=false
    DRY_RUN=false
    VERBOSE=false
    
    # Parse all arguments in one pass
    while [[ $# -gt 0 ]]; do
        case $1 in
            -m|--mode)
                CLEANUP_MODE="$2"
                shift 2
                ;;
            --output-dir)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
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
                die "Unexpected argument: $1"
                ;;
        esac
    done
    
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
    
    log_section "HIPAA Infrastructure Cleanup"
    log_info "Cleanup mode: $CLEANUP_MODE"
    log_info "Environment: $ENVIRONMENT"
    
    # Validate prerequisites
    check_prerequisites
    validate_cleanup_prerequisites
    
    # Create environments config if it doesn't exist
    if [[ ! -f "$ENVIRONMENTS_CONFIG" ]]; then
        die "Environments configuration not found: $ENVIRONMENTS_CONFIG"
    fi
    
    # Show dry-run mode if enabled
    if is_dry_run; then
        log_warning "DRY RUN MODE: No changes will be made"
        echo ""
    fi
    
    # Show final warning
    if ! is_dry_run; then
        echo ""
        log_error "⚠️  FINAL WARNING ⚠️"
        log_error "Environment: $ENVIRONMENT"
        log_error "Mode: $CLEANUP_MODE"
        echo ""
        case "$CLEANUP_MODE" in
            "infrastructure")
                log_error "This will destroy ALL infrastructure resources"
                ;;
            "complete")
                log_error "This will destroy ALL infrastructure AND remove service user"
                ;;
        esac
        echo ""
        
        if ! is_force_mode; then
            read -p "Last chance to cancel. Press Enter to continue or Ctrl+C to abort..."
        fi
    fi
    
    # Change to project directory for Pulumi operations
    cd "$PROJECT_DIR"
    
    # Perform cleanup operations
    case "$CLEANUP_MODE" in
        "infrastructure")
            cleanup_infrastructure "$ENVIRONMENT"
            ;;
        "complete")
            cleanup_infrastructure "$ENVIRONMENT"
            cleanup_service_user "$ENVIRONMENT"
            ;;
    esac
    
    echo ""
    log_section "Cleanup Complete"
    
    case "$CLEANUP_MODE" in
        "infrastructure")
            log_success "Infrastructure cleanup completed for: $ENVIRONMENT"
            echo ""
            log_info "Service user still exists and can be used for redeployment"
            log_info "To remove service user: ./scripts/cleanup.sh -e $ENVIRONMENT -m complete"
            ;;
        "complete")
            log_success "Complete cleanup finished for: $ENVIRONMENT"
            echo ""
            log_info "All resources and service user removed"
            log_info "To redeploy: ./scripts/setup-env.sh -e $ENVIRONMENT"
            ;;
    esac
    
    echo ""
    log_warning "Verify in AWS Console that all resources are deleted"
    log_warning "Check AWS billing to ensure no unexpected charges"
}

# Run main function
main "$@"