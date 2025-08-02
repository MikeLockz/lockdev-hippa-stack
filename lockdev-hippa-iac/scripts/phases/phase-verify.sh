#!/bin/bash

# Phase 5: Verification Script
# Comprehensive verification that all resources have been cleaned up

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

PHASE_NAME="verification"

# Main verification function
verify_cleanup() {
    local environment="$1"
    
    log_phase "$PHASE_NAME" "Starting comprehensive verification for: $environment"
    
    # Load environment configuration
    load_environment_config "$environment"
    
    local root_profile=$(get_env_config "$environment" "root_profile")
    local region=$(get_env_config "$environment" "region")
    
    # Setup AWS environment
    setup_aws_env "$root_profile" "$region"
    
    # Perform comprehensive verification
    local verification_results=""
    
    verification_results+=$(verify_pulumi_stacks "$environment")
    verification_results+=$(verify_aws_resources "$environment")
    verification_results+=$(verify_billing_resources "$environment")
    verification_results+=$(verify_iam_resources "$environment")
    
    # Generate verification report
    generate_verification_report "$environment" "$verification_results"
    
    log_phase_success "$PHASE_NAME" "Verification completed"
}

# Verify Pulumi stacks
verify_pulumi_stacks() {
    local environment="$1"
    
    log_step "Verifying Pulumi stacks..."
    
    local project_dir="$PROJECT_DIR"
    local stack_name="hipaa-$environment"
    
    cd "$project_dir" || return 1
    
    # Check if stack exists
    if pulumi stack ls | grep -q "^$stack_name"; then
        log_error "Pulumi stack still exists: $stack_name"
        echo "PULUMI_STACK_EXISTS: $stack_name"
        
        # Show stack details
        pulumi stack select "$stack_name" 2>/dev/null || true
        local stack_outputs=$(pulumi stack output --json 2>/dev/null || echo "{}")
        log_info "Stack outputs: $stack_outputs"
    else
        log_success "Pulumi stack cleaned: $stack_name"
    fi
    
    cd - >/dev/null || true
}

# Verify AWS resources
verify_aws_resources() {
    local environment="$1"
    
    log_step "Verifying AWS resources..."
    
    local remaining_resources=()
    
    # Check VPC resources
    local vpcs=$(AWS_PROFILE="$root_profile" aws ec2 describe-vpcs \
        --filters "Name=tag:Name,Values=*hipaa*" \
        --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo "")
    
    if [[ -n "$vpcs" ]]; then
        remaining_resources+=("VPCs: $vpcs")
        log_error "VPCs still exist: $vpcs"
    fi
    
    # Check EC2 instances
    local instances=$(AWS_PROFILE="$root_profile" aws ec2 describe-instances \
        --filters "Name=tag:Name,Values=*hipaa*" \
        --query 'Reservations[].Instances[].InstanceId' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$instances" ]]; then
        remaining_resources+=("EC2 Instances: $instances")
        log_error "EC2 instances still exist: $instances"
    fi
    
    # Check RDS instances
    local rds_instances=$(AWS_PROFILE="$root_profile" aws rds describe-db-instances \
        --query 'DBInstances[?contains(DBInstanceIdentifier, `hipaa`) || contains(DBInstanceIdentifier, `'"$environment"'`)].DBInstanceIdentifier' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$rds_instances" ]]; then
        remaining_resources+=("RDS Instances: $rds_instances")
        log_error "RDS instances still exist: $rds_instances"
    fi
    
    # Check S3 buckets
    local buckets=$(AWS_PROFILE="$root_profile" aws s3api list-buckets \
        --query 'Buckets[?contains(Name, `hipaa`) && contains(Name, `'"$environment"'`)].Name' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$buckets" ]]; then
        remaining_resources+=("S3 Buckets: $buckets")
        log_error "S3 buckets still exist: $buckets"
    fi
    
    # Check ECS clusters
    local clusters=$(AWS_PROFILE="$root_profile" aws ecs list-clusters \
        --query 'clusterArns[?contains(@, `hipaa`) || contains(@, `'"$environment"'`)]' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$clusters" ]]; then
        remaining_resources+=("ECS Clusters: $clusters")
        log_error "ECS clusters still exist: $clusters"
    fi
    
    # Check load balancers
    local lbs=$(AWS_PROFILE="$root_profile" aws elbv2 describe-load-balancers \
        --query 'LoadBalancers[?contains(LoadBalancerName, `hipaa`) || contains(LoadBalancerName, `'"$environment"'`)].LoadBalancerArn' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$lbs" ]]; then
        local lb_names=$(echo "$lbs" | sed 's/.*loadbalancer\///g')
        remaining_resources+=("Load Balancers: $lb_names")
        log_error "Load balancers still exist: $lb_names"
    fi
    
    # Check ECR repositories
    local repos=$(AWS_PROFILE="$root_profile" aws ecr describe-repositories \
        --query 'repositories[?contains(repositoryName, `hipaa`) || contains(repositoryName, `'"$environment"'`)].repositoryName' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$repos" ]]; then
        remaining_resources+=("ECR Repositories: $repos")
        log_error "ECR repositories still exist: $repos"
    fi
    
    # Check CloudWatch log groups
    local log_groups=$(AWS_PROFILE="$root_profile" aws logs describe-log-groups \
        --query 'logGroups[?contains(logGroupName, `hipaa`) || contains(logGroupName, `'"$environment"'`)].logGroupName' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$log_groups" ]]; then
        remaining_resources+=("CloudWatch Log Groups: $log_groups")
        log_error "CloudWatch log groups still exist: $log_groups"
    fi
    
    # Check NAT gateways
    local nat_gateways=$(AWS_PROFILE="$root_profile" aws ec2 describe-nat-gateways \
        --query 'NatGateways[?contains(Tags[?Key==`Name`].Value, `hipaa`) || contains(Tags[?Key==`Name`].Value, `'"$environment"'`)].NatGatewayId' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$nat_gateways" ]]; then
        remaining_resources+=("NAT Gateways: $nat_gateways")
        log_error "NAT gateways still exist: $nat_gateways"
    fi
    
    # Check security groups
    local security_groups=$(AWS_PROFILE="$root_profile" aws ec2 describe-security-groups \
        --query 'SecurityGroups[?contains(GroupName, `hipaa`) || contains(GroupName, `'"$environment"'`)].GroupId' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$security_groups" ]]; then
        remaining_resources+=("Security Groups: $security_groups")
        log_error "Security groups still exist: $security_groups"
    fi
    
    # Check subnets
    local subnets=$(AWS_PROFILE="$root_profile" aws ec2 describe-subnets \
        --query 'Subnets[?contains(Tags[?Key==`Name`].Value, `hipaa`) || contains(Tags[?Key==`Name`].Value, `'"$environment"'`)].SubnetId' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$subnets" ]]; then
        remaining_resources+=("Subnets: $subnets")
        log_error "Subnets still exist: $subnets"
    fi
    
    # Return verification results
    if [[ ${#remaining_resources[@]} -eq 0 ]]; then
        log_success "All AWS resources have been successfully cleaned up"
        echo "AWS_RESOURCES_CLEANED: true"
    else
        log_error "Found ${#remaining_resources[@]} types of remaining AWS resources"
        for resource in "${remaining_resources[@]}"; do
            echo "REMAINING_AWS_RESOURCE: $resource"
        done
    fi
}

# Verify billing resources
verify_billing_resources() {
    local environment="$1"
    
    log_step "Verifying billing-related resources..."
    
    # Check for any active services that might incur charges
    local active_services=()
    
    # Check for active RDS instances (billing)
    local rds_active=$(AWS_PROFILE="$root_profile" aws rds describe-db-instances \
        --query 'length(DBInstances[?DBInstanceStatus!=`deleted`])' \
        --output text 2>/dev/null || echo "0")
    
    if [[ "$rds_active" != "0" ]]; then
        active_services+=("Active RDS instances: $rds_active")
    fi
    
    # Check for active load balancers (billing)
    local lb_active=$(AWS_PROFILE="$root_profile" aws elbv2 describe-load-balancers \
        --query 'length(LoadBalancers[?State.Code!=`deleted`])' \
        --output text 2>/dev/null || echo "0")
    
    if [[ "$lb_active" != "0" ]]; then
        active_services+=("Active Load Balancers: $lb_active")
    fi
    
    # Check for active NAT gateways (billing)
    local nat_active=$(AWS_PROFILE="$root_profile" aws ec2 describe-nat-gateways \
        --query 'length(NatGateways[?State==`available`])' \
        --output text 2>/dev/null || echo "0")
    
    if [[ "$nat_active" != "0" ]]; then
        active_services+=("Active NAT Gateways: $nat_active")
    fi
    
    if [[ ${#active_services[@]} -eq 0 ]]; then
        log_success "No active billing resources found"
        echo "BILLING_RESOURCES_CLEANED: true"
    else
        log_warning "Found ${#active_services[@]} types of active billing resources"
        for service in "${active_services[@]}"; do
            echo "ACTIVE_BILLING_SERVICE: $service"
        done
    fi
}

# Verify IAM resources
verify_iam_resources() {
    local environment="$1"
    
    log_step "Verifying IAM resources..."
    
    local account_id=$(AWS_PROFILE="$root_profile" aws sts get-caller-identity \
        --query Account --output text 2>/dev/null || echo "")
    
    if [[ -z "$account_id" ]]; then
        log_error "Cannot determine AWS account ID"
        return 1
    fi
    
    local iam_resources=()
    
    # Check for HIPAA-related IAM roles
    local roles=$(AWS_PROFILE="$root_profile" aws iam list-roles \
        --query 'Roles[?contains(RoleName, `hipaa`) || contains(RoleName, `'"$environment"'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$roles" != "[]" ]]; then
        local role_names=$(echo "$roles" | jq -r '.[].RoleName')
        iam_resources+=("IAM Roles: $role_names")
    fi
    
    # Check for HIPAA-related IAM policies
    local policies=$(AWS_PROFILE="$root_profile" aws iam list-policies \
        --scope Local \
        --query 'Policies[?contains(PolicyName, `hipaa`) || contains(PolicyName, `'"$environment"'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$policies" != "[]" ]]; then
        local policy_names=$(echo "$policies" | jq -r '.[].PolicyName')
        iam_resources+=("IAM Policies: $policy_names")
    fi
    
    # Check for HIPAA-related IAM users
    local users=$(AWS_PROFILE="$root_profile" aws iam list-users \
        --query 'Users[?contains(UserName, `hipaa`) || contains(UserName, `'"$environment"'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$users" != "[]" ]]; then
        local user_names=$(echo "$users" | jq -r '.[].UserName')
        iam_resources+=("IAM Users: $user_names")
    fi
    
    if [[ ${#iam_resources[@]} -eq 0 ]]; then
        log_success "No HIPAA-related IAM resources found"
        echo "IAM_RESOURCES_CLEANED: true"
    else
        log_warning "Found ${#iam_resources[@]} types of remaining IAM resources"
        for resource in "${iam_resources[@]}"; do
            echo "REMAINING_IAM_RESOURCE: $resource"
        done
    fi
}

# Generate comprehensive verification report
generate_verification_report() {
    local environment="$1"
    local verification_results="$2"
    
    log_step "Generating verification report..."
    
    local report_file="$PROJECT_DIR/outputs/cleanup-verification-$environment-$(date +%Y%m%d-%H%M%S).txt"
    
    # Ensure output directory exists
    mkdir -p "$(dirname "$report_file")"
    
    cat > "$report_file" <<EOF
HIPAA Infrastructure Cleanup Verification Report
===============================================

Environment: $environment
Verification Date: $(date)
Account: $(AWS_PROFILE="$root_profile" aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "Unknown")
Region: $region

Summary:
--------
$(echo "$verification_results" | grep -E "^(AWS_RESOURCES_CLEANED|BILLING_RESOURCES_CLEANED|IAM_RESOURCES_CLEANED|PULUMI_STACK_EXISTS|REMAINING_|ACTIVE_)" || echo "No verification results found")

Detailed Resource Check:
------------------------

$(verify_aws_resources "$environment")

$(verify_billing_resources "$environment")

$(verify_iam_resources "$environment")

$(verify_pulumi_stacks "$environment")

EOF
    
    log_info "Verification report generated: $report_file"
    
    # Display summary
    echo ""
    echo "=== VERIFICATION SUMMARY ==="
    echo "Environment: $environment"
    echo "Report: $report_file"
    echo ""
    
    # Count remaining resources
    local remaining_count=$(echo "$verification_results" | grep -c "REMAINING_" || echo 0)
    local active_count=$(echo "$verification_results" | grep -c "ACTIVE_" || echo 0)
    
    if [[ $remaining_count -eq 0 ]] && [[ $active_count -eq 0 ]]; then
        log_success "✅ CLEANUP VERIFICATION PASSED - All resources successfully cleaned up"
        echo "SUCCESS: true"
    else
        log_error "❌ CLEANUP VERIFICATION FAILED - Found $((remaining_count + active_count)) remaining resources"
        echo "SUCCESS: false"
    fi
}

# Hook function for phase execution
phase_verify_hook() {
    local environment="$1"
    local options="$2"
    
    log_info "Executing verification phase for: $environment"
    
    verify_cleanup "$environment"
}

# Allow direct execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 \u003cenvironment\u003e [options]"
        echo "  environment: dev, staging, prod"
        echo "  options: --dry-run, --force"
        exit 1
    fi
    
    source "$(dirname "$0")/../lib/utils.sh"
    verify_cleanup "$1"
fi