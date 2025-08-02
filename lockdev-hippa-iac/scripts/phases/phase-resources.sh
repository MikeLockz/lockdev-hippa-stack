#!/bin/bash

# Phase 3: AWS Resources Cleanup Script
# Systematically destroys AWS resources in correct dependency order

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

PHASE_NAME="resources-cleanup"

# Main resource cleanup function
cleanup_aws_resources() {
    local environment="$1"
    
    log_phase "$PHASE_NAME" "Starting AWS resources cleanup for: $environment"
    
    # Load environment configuration
    load_environment_config "$environment"
    
    local root_profile=$(get_env_config "$environment" "root_profile")
    local region=$(get_env_config "$environment" "region")
    
    # Setup AWS environment
    setup_aws_env "$root_profile" "$region"
    
    # Cleanup resources in dependency order
    cleanup_ecs_resources "$environment"
    cleanup_load_balancers "$environment"
    cleanup_rds_resources "$environment"
    cleanup_s3_buckets "$environment"
    cleanup_ecr_repositories "$environment"
    cleanup_kms_keys "$environment"
    cleanup_cloudwatch_resources "$environment"
    
    log_phase_success "$PHASE_NAME" "AWS resources cleanup completed"
}

# Cleanup ECS resources
cleanup_ecs_resources() {
    local environment="$1"
    
    log_step "Cleaning up ECS resources..."
    
    # Find ECS clusters with HIPAA naming
    local clusters=$(AWS_PROFILE="$root_profile" aws ecs list-clusters \
        --query 'clusterArns[?contains(@, `hipaa`) || contains(@, `'$environment'`)]' \
        --output text 2>/dev/null || echo "")
    
    if [[ -z "$clusters" ]]; then
        log_info "No ECS clusters found"
        return 0
    fi
    
    for cluster_arn in $clusters; do
        local cluster_name=$(basename "$cluster_arn")
        log_info "Processing ECS cluster: $cluster_name"
        
        # List and delete services
        local services=$(AWS_PROFILE="$root_profile" aws ecs list-services \
            --cluster "$cluster_arn" --query 'serviceArns' \
            --output text 2>/dev/null || echo "")
        
        if [[ -n "$services" ]]; then
            for service_arn in $services; do
                local service_name=$(basename "$service_arn")
                log_info "Stopping and deleting ECS service: $service_name"
                
                # Update service to 0 desired count first
                AWS_PROFILE="$root_profile" aws ecs update-service \
                    --cluster "$cluster_arn" --service "$service_arn" \
                    --desired-count 0 --no-cli-pager 2>/dev/null || true
                
                # Wait for service to scale down
                sleep 10
                
                # Delete the service
                AWS_PROFILE="$root_profile" aws ecs delete-service \
                    --cluster "$cluster_arn" --service "$service_arn" \
                    --force --no-cli-pager 2>/dev/null || true
            done
        fi
        
        # List and stop tasks
        local tasks=$(AWS_PROFILE="$root_profile" aws ecs list-tasks \
            --cluster "$cluster_arn" --query 'taskArns' \
            --output text 2>/dev/null || echo "")
        
        if [[ -n "$tasks" ]]; then
            for task_arn in $tasks; do
                log_info "Stopping ECS task: $task_arn"
                AWS_PROFILE="$root_profile" aws ecs stop-task \
                    --cluster "$cluster_arn" --task "$task_arn" \
                    --no-cli-pager 2>/dev/null || true
            done
        fi
        
        # Delete the cluster
        log_info "Deleting ECS cluster: $cluster_name"
        AWS_PROFILE="$root_profile" aws ecs delete-cluster \
            --cluster "$cluster_arn" --no-cli-pager 2>/dev/null || true
    done
    
    # Clean up ECS task definitions
    local task_definitions=$(AWS_PROFILE="$root_profile" aws ecs list-task-definitions \
        --family-prefix "hipaa" --query 'taskDefinitionArns[]' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$task_definitions" ]]; then
        for td_arn in $task_definitions; do
            log_info "Deregistering ECS task definition: $td_arn"
            AWS_PROFILE="$root_profile" aws ecs deregister-task-definition \
                --task-definition "$td_arn" --no-cli-pager 2>/dev/null || true
        done
    fi
}

# Cleanup load balancers
cleanup_load_balancers() {
    local environment="$1"
    
    log_step "Cleaning up load balancers..."
    
    # Find ALBs with HIPAA naming
    local albs=$(AWS_PROFILE="$root_profile" aws elbv2 describe-load-balancers \
        --query 'LoadBalancers[?contains(LoadBalancerName, `hipaa`) || contains(LoadBalancerName, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$albs" == "[]" ]]; then
        log_info "No load balancers found"
        return 0
    fi
    
    echo "$albs" | jq -r '.[].LoadBalancerArn' | while read -r alb_arn; do
        local alb_name=$(AWS_PROFILE="$root_profile" aws elbv2 describe-load-balancers \
            --load-balancer-arns "$alb_arn" --query 'LoadBalancers[0].LoadBalancerName' \
            --output text 2>/dev/null || echo "unknown")
        
        log_info "Deleting load balancer: $alb_name"
        
        # First, delete all target groups associated with this ALB
        local target_groups=$(AWS_PROFILE="$root_profile" aws elbv2 describe-target-groups \
            --load-balancer-arn "$alb_arn" --query 'TargetGroups[].TargetGroupArn' \
            --output text 2>/dev/null || echo "")
        
        if [[ -n "$target_groups" ]]; then
            for tg_arn in $target_groups; do
                local tg_name=$(AWS_PROFILE="$root_profile" aws elbv2 describe-target-groups \
                    --target-group-arns "$tg_arn" --query 'TargetGroups[0].TargetGroupName' \
                    --output text 2>/dev/null || echo "unknown")
                log_info "Deleting target group: $tg_name"
                AWS_PROFILE="$root_profile" aws elbv2 delete-target-group \
                    --target-group-arn "$tg_arn" --no-cli-pager 2>/dev/null || true
            done
        fi
        
        # Delete the load balancer
        AWS_PROFILE="$root_profile" aws elbv2 delete-load-balancer \
            --load-balancer-arn "$alb_arn" --no-cli-pager 2>/dev/null || true
    done
}

# Cleanup RDS resources
cleanup_rds_resources() {
    local environment="$1"
    
    log_step "Cleaning up RDS resources..."
    
    # Find RDS instances with HIPAA naming
    local rds_instances=$(AWS_PROFILE="$root_profile" aws rds describe-db-instances \
        --query 'DBInstances[?contains(DBInstanceIdentifier, `hipaa`) || contains(DBInstanceIdentifier, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$rds_instances" == "[]" ]]; then
        log_info "No RDS instances found"
        return 0
    fi
    
    echo "$rds_instances" | jq -r '.[].DBInstanceIdentifier' | while read -r instance; do
        log_info "Deleting RDS instance: $instance"
        
        # Disable deletion protection
        AWS_PROFILE="$root_profile" aws rds modify-db-instance \
            --db-instance-identifier "$instance" --deletion-protection false \
            --apply-immediately --no-cli-pager 2>/dev/null || true
        
        # Wait for modification to complete
        sleep 10
        
        # Delete the instance
        AWS_PROFILE="$root_profile" aws rds delete-db-instance \
            --db-instance-identifier "$instance" \
            --skip-final-snapshot \
            --delete-automated-backups \
            --no-cli-pager 2>/dev/null || true
    done
    
    # Find and delete RDS subnet groups
    local subnet_groups=$(AWS_PROFILE="$root_profile" aws rds describe-db-subnet-groups \
        --query 'DBSubnetGroups[?contains(DBSubnetGroupName, `hipaa`) || contains(DBSubnetGroupName, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$subnet_groups" != "[]" ]]; then
        echo "$subnet_groups" | jq -r '.[].DBSubnetGroupName' | while read -r subnet_group; do
            log_info "Deleting RDS subnet group: $subnet_group"
            AWS_PROFILE="$root_profile" aws rds delete-db-subnet-group \
                --db-subnet-group-name "$subnet_group" --no-cli-pager 2>/dev/null || true
        done
    fi
}

# Cleanup S3 buckets
cleanup_s3_buckets() {
    local environment="$1"
    
    log_step "Cleaning up S3 buckets..."
    
    # Find S3 buckets with HIPAA naming
    local buckets=$(AWS_PROFILE="$root_profile" aws s3api list-buckets \
        --query 'Buckets[?contains(Name, `hipaa`) && contains(Name, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$buckets" == "[]" ]]; then
        log_info "No S3 buckets found"
        return 0
    fi
    
    echo "$buckets" | jq -r '.[].Name' | while read -r bucket; do
        if [[ -n "$bucket" ]]; then
            log_info "Processing S3 bucket: $bucket"
            
            # Check if bucket exists
            if AWS_PROFILE="$root_profile" aws s3api head-bucket --bucket "$bucket" 2>/dev/null; then
                # Empty the bucket completely
                log_info "Emptying bucket: $bucket"
                AWS_PROFILE="$root_profile" aws s3 rm "s3://$bucket" --recursive --quiet 2>/dev/null || true
                
                # Delete all versions and delete markers
                local versions=$(AWS_PROFILE="$root_profile" aws s3api list-object-versions --bucket "$bucket" --output json 2>/dev/null || echo '{"Versions": [], "DeleteMarkers": []}')
                
                # Batch delete versions
                local delete_objects=$(echo "$versions" | jq -c '{Objects: (.Versions + .DeleteMarkers) | map({Key: .Key, VersionId: .VersionId})}')
                if [[ "$delete_objects" != '{"Objects":[]}' ]] && [[ "$delete_objects" != '{"Objects":null}' ]]; then
                    AWS_PROFILE="$root_profile" aws s3api delete-objects --bucket "$bucket" --delete "$delete_objects" --no-cli-pager 2>/dev/null || true
                fi
                
                # Delete the bucket
                log_info "Deleting S3 bucket: $bucket"
                AWS_PROFILE="$root_profile" aws s3 rb "s3://$bucket" --force --no-cli-pager 2>/dev/null || true
            else
                log_warning "Bucket not accessible: $bucket"
            fi
        fi
    done
}

# Cleanup ECR repositories
cleanup_ecr_repositories() {
    local environment="$1"
    
    log_step "Cleaning up ECR repositories..."
    
    # Find ECR repositories with HIPAA naming
    local repos=$(AWS_PROFILE="$root_profile" aws ecr describe-repositories \
        --query 'repositories[?contains(repositoryName, `hipaa`) || contains(repositoryName, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$repos" == "[]" ]]; then
        log_info "No ECR repositories found"
        return 0
    fi
    
    echo "$repos" | jq -r '.[].repositoryName' | while read -r repo_name; do
        log_info "Deleting ECR repository: $repo_name"
        AWS_PROFILE="$root_profile" aws ecr delete-repository \
            --repository-name "$repo_name" --force --no-cli-pager 2>/dev/null || true
    done
}

# Cleanup KMS keys
cleanup_kms_keys() {
    local environment="$1"
    
    log_step "Cleaning up KMS keys..."
    
    # Find KMS keys with HIPAA naming
    local keys=$(AWS_PROFILE="$root_profile" aws kms list-keys \
        --query 'Keys[?contains(KeyArn, `hipaa`) || contains(KeyArn, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$keys" == "[]" ]]; then
        log_info "No KMS keys found"
        return 0
    fi
    
    echo "$keys" | jq -r '.[].KeyId' | while read -r key_id; do
        log_info "Scheduling deletion for KMS key: $key_id"
        AWS_PROFILE="$root_profile" aws kms schedule-key-deletion \
            --key-id "$key_id" --pending-window-in-days 7 --no-cli-pager 2>/dev/null || true
    done
}

# Cleanup CloudWatch resources
cleanup_cloudwatch_resources() {
    local environment="$1"
    
    log_step "Cleaning up CloudWatch resources..."
    
    # Find CloudWatch log groups with HIPAA naming
    local log_groups=$(AWS_PROFILE="$root_profile" aws logs describe-log-groups \
        --query 'logGroups[?contains(logGroupName, `hipaa`) || contains(logGroupName, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$log_groups" == "[]" ]]; then
        log_info "No CloudWatch log groups found"
        return 0
    fi
    
    echo "$log_groups" | jq -r '.[].logGroupName' | while read -r log_group; do
        log_info "Deleting CloudWatch log group: $log_group"
        AWS_PROFILE="$root_profile" aws logs delete-log-group \
            --log-group-name "$log_group" --no-cli-pager 2>/dev/null || true
    done
    
    # Find CloudWatch alarms
    local alarms=$(AWS_PROFILE="$root_profile" aws cloudwatch describe-alarms \
        --query 'MetricAlarms[?contains(AlarmName, `hipaa`) || contains(AlarmName, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$alarms" != "[]" ]]; then
        echo "$alarms" | jq -r '.[].AlarmName' | while read -r alarm_name; do
            log_info "Deleting CloudWatch alarm: $alarm_name"
            AWS_PROFILE="$root_profile" aws cloudwatch delete-alarms \
                --alarm-names "$alarm_name" --no-cli-pager 2>/dev/null || true
        done
    fi
}

# Hook function for phase execution
phase_resources_hook() {
    local environment="$1"
    local options="$2"
    
    log_info "Executing AWS resources cleanup phase for: $environment"
    
    if is_dry_run; then
        log_info "[DRY RUN] Would cleanup AWS resources for environment: $environment"
        return 0
    fi
    
    cleanup_aws_resources "$environment"
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
    cleanup_aws_resources "$1"
fi