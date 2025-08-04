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
    cleanup_cloudformation_stacks "$environment"
    cleanup_ecs_resources "$environment"
    cleanup_load_balancers "$environment"
    cleanup_rds_resources "$environment"
    cleanup_s3_buckets "$environment"
    cleanup_ecr_repositories "$environment"
    cleanup_kms_keys "$environment"
    cleanup_cloudwatch_resources "$environment"
    cleanup_iam_resources "$environment"
    
    log_phase_success "$PHASE_NAME" "AWS resources cleanup completed"
}

# Cleanup CloudFormation stacks
cleanup_cloudformation_stacks() {
    local environment="$1"
    
    log_step "Cleaning up CloudFormation stacks..."
    
    # Find CloudFormation stacks - we'll be conservative and only delete stacks that match our patterns
    local stacks=$(AWS_PROFILE="$root_profile" aws cloudformation list-stacks \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE \
        --query 'StackSummaries[?contains(StackName, `hipaa`) || contains(StackName, `'$environment'`) || contains(Tags[?Key==`Environment`].Value | [0] || ``, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$stacks" == "[]" ]]; then
        log_info "No matching CloudFormation stacks found for cleanup"
        
        # List all stacks for informational purposes in dry-run mode
        if is_dry_run; then
            log_info "All existing CloudFormation stacks:"
            AWS_PROFILE="$root_profile" aws cloudformation list-stacks \
                --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE \
                --query 'StackSummaries[].[StackName,StackStatus,CreationTime]' \
                --output table 2>/dev/null || log_warning "Could not list stacks"
        fi
        return 0
    fi
    
    # Show what stacks would be deleted
    log_info "Found CloudFormation stacks for cleanup:"
    echo "$stacks" | jq -r '.[].StackName' | while read -r stack_name; do
        if [[ -n "$stack_name" ]]; then
            log_info "  - $stack_name"
        fi
    done
    
    # Delete stacks in reverse order (newest first to handle dependencies)
    echo "$stacks" | jq -r 'sort_by(.CreationTime) | reverse | .[].StackName' | while read -r stack_name; do
        if [[ -n "$stack_name" ]]; then
            log_info "Processing CloudFormation stack: $stack_name"
            
            # Check if stack has termination protection
            local protection_enabled=$(AWS_PROFILE="$root_profile" aws cloudformation describe-stacks \
                --stack-name "$stack_name" \
                --query 'Stacks[0].EnableTerminationProtection' \
                --output text 2>/dev/null || echo "false")
            
            if [[ "$protection_enabled" == "true" ]]; then
                log_info "Disabling termination protection for stack: $stack_name"
                AWS_PROFILE="$root_profile" aws cloudformation update-termination-protection \
                    --stack-name "$stack_name" \
                    --no-enable-termination-protection \
                    --no-cli-pager 2>/dev/null || true
                
                # Wait a moment for the protection update to take effect
                sleep 5
            fi
            
            # Check for nested stacks and handle them first
            local nested_stacks=$(AWS_PROFILE="$root_profile" aws cloudformation list-stack-resources \
                --stack-name "$stack_name" \
                --query 'StackResourceSummaries[?ResourceType==`AWS::CloudFormation::Stack`].PhysicalResourceId' \
                --output text 2>/dev/null || echo "")
            
            if [[ -n "$nested_stacks" ]]; then
                log_info "Found nested stacks for $stack_name, they will be deleted automatically with parent stack"
            fi
            
            # Delete the stack
            log_info "Deleting CloudFormation stack: $stack_name"
            if AWS_PROFILE="$root_profile" aws cloudformation delete-stack \
                --stack-name "$stack_name" \
                --no-cli-pager 2>/dev/null; then
                
                log_info "Deletion initiated for stack: $stack_name"
                
                # Wait for deletion to complete (with timeout)
                log_info "Waiting for stack deletion to complete: $stack_name"
                local wait_timeout=300  # 5 minutes timeout
                local wait_interval=15
                local elapsed=0
                
                while [[ $elapsed -lt $wait_timeout ]]; do
                    local stack_status=$(AWS_PROFILE="$root_profile" aws cloudformation describe-stacks \
                        --stack-name "$stack_name" \
                        --query 'Stacks[0].StackStatus' \
                        --output text 2>/dev/null || echo "DELETE_COMPLETE")
                    
                    if [[ "$stack_status" == "DELETE_COMPLETE" ]] || [[ "$stack_status" == "DELETE_COMPLETE" ]]; then
                        log_info "Stack deletion completed: $stack_name"
                        break
                    elif [[ "$stack_status" == "DELETE_FAILED" ]]; then
                        log_warning "Stack deletion failed: $stack_name - Status: $stack_status"
                        
                        # Get failure reason
                        local failure_reason=$(AWS_PROFILE="$root_profile" aws cloudformation describe-stack-events \
                            --stack-name "$stack_name" \
                            --query 'StackEvents[?ResourceStatus==`DELETE_FAILED`] | [0].ResourceStatusReason' \
                            --output text 2>/dev/null || echo "Unknown failure reason")
                        log_warning "Failure reason: $failure_reason"
                        break
                    elif [[ "$stack_status" =~ DELETE_IN_PROGRESS ]]; then
                        log_info "Stack deletion in progress: $stack_name (${elapsed}s elapsed)"
                        sleep $wait_interval
                        elapsed=$((elapsed + wait_interval))
                    else
                        log_warning "Unexpected stack status: $stack_name - $stack_status"
                        break
                    fi
                done
                
                if [[ $elapsed -ge $wait_timeout ]]; then
                    log_warning "Timeout waiting for stack deletion: $stack_name"
                    log_info "You may need to check the stack status manually"
                fi
            else
                log_error "Failed to initiate deletion of stack: $stack_name"
            fi
        fi
    done
    
    log_info "CloudFormation stacks cleanup completed"
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
    
    # Find ALL ALBs (not just those with HIPAA naming, as they might be created by Pulumi with different names)
    local albs=$(AWS_PROFILE="$root_profile" aws elbv2 describe-load-balancers \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$albs" == "[]" ]]; then
        log_info "No load balancers found"
        return 0
    fi
    
    # Filter ALBs by tags or name patterns
    echo "$albs" | jq -r '.LoadBalancers[] | select(.LoadBalancerName | contains("hipaa") or contains("'$environment'") or contains("pulumi")) | .LoadBalancerArn' | while read -r alb_arn; do
        if [[ -n "$alb_arn" ]]; then
            local alb_name=$(AWS_PROFILE="$root_profile" aws elbv2 describe-load-balancers \
                --load-balancer-arns "$alb_arn" --query 'LoadBalancers[0].LoadBalancerName' \
                --output text 2>/dev/null || echo "unknown")
            
            log_info "Processing load balancer: $alb_name ($alb_arn)"
            
            # Disable deletion protection first
            log_info "Disabling deletion protection for ALB: $alb_name"
            AWS_PROFILE="$root_profile" aws elbv2 modify-load-balancer-attributes \
                --load-balancer-arn "$alb_arn" \
                --attributes Key=deletion_protection.enabled,Value=false \
                --no-cli-pager 2>/dev/null || true
            
            # Wait a moment for the attribute change to take effect
            sleep 5
            
            # Delete all listeners first
            local listeners=$(AWS_PROFILE="$root_profile" aws elbv2 describe-listeners \
                --load-balancer-arn "$alb_arn" --query 'Listeners[].ListenerArn' \
                --output text 2>/dev/null || echo "")
            
            if [[ -n "$listeners" ]]; then
                for listener_arn in $listeners; do
                    log_info "Deleting listener: $listener_arn"
                    AWS_PROFILE="$root_profile" aws elbv2 delete-listener \
                        --listener-arn "$listener_arn" --no-cli-pager 2>/dev/null || true
                done
            fi
            
            # Delete all target groups associated with this ALB
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
            
            # Now delete the load balancer
            log_info "Deleting load balancer: $alb_name"
            AWS_PROFILE="$root_profile" aws elbv2 delete-load-balancer \
                --load-balancer-arn "$alb_arn" --no-cli-pager 2>/dev/null || true
        fi
    done
    
    # Also clean up any orphaned target groups
    log_info "Cleaning up orphaned target groups..."
    local orphaned_tgs=$(AWS_PROFILE="$root_profile" aws elbv2 describe-target-groups \
        --query 'TargetGroups[?contains(TargetGroupName, `hipaa`) || contains(TargetGroupName, `'$environment'`) || contains(TargetGroupName, `pulumi`)].TargetGroupArn' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$orphaned_tgs" ]]; then
        for tg_arn in $orphaned_tgs; do
            local tg_name=$(AWS_PROFILE="$root_profile" aws elbv2 describe-target-groups \
                --target-group-arns "$tg_arn" --query 'TargetGroups[0].TargetGroupName' \
                --output text 2>/dev/null || echo "unknown")
            log_info "Deleting orphaned target group: $tg_name"
            AWS_PROFILE="$root_profile" aws elbv2 delete-target-group \
                --target-group-arn "$tg_arn" --no-cli-pager 2>/dev/null || true
        done
    fi
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
    
    # Find KMS keys by aliases with HIPAA naming
    local aliases=$(AWS_PROFILE="$root_profile" aws kms list-aliases \
        --query 'Aliases[?contains(AliasName, `hipaa`) || contains(AliasName, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$aliases" != "[]" ]]; then
        echo "$aliases" | jq -r '.[].TargetKeyId' | while read -r key_id; do
            if [[ -n "$key_id" ]] && [[ "$key_id" != "null" ]]; then
                log_info "Found KMS key via alias: $key_id"
                
                # Get key description to verify it's customer-managed
                local key_info=$(AWS_PROFILE="$root_profile" aws kms describe-key \
                    --key-id "$key_id" --query 'KeyMetadata.[KeyManager,KeyState,Description]' \
                    --output json 2>/dev/null || echo "[]")
                
                local key_manager=$(echo "$key_info" | jq -r '.[0]')
                local key_state=$(echo "$key_info" | jq -r '.[1]')
                local description=$(echo "$key_info" | jq -r '.[2]')
                
                if [[ "$key_manager" == "CUSTOMER" ]]; then
                    log_info "Scheduling deletion for customer-managed KMS key: $key_id"
                    log_info "  Description: $description"
                    log_info "  Current state: $key_state"
                    
                    if [[ "$key_state" == "Enabled" ]]; then
                        AWS_PROFILE="$root_profile" aws kms schedule-key-deletion \
                            --key-id "$key_id" --pending-window-in-days 7 --no-cli-pager 2>/dev/null || true
                    else
                        log_info "Key is not in enabled state, skipping: $key_state"
                    fi
                else
                    log_info "Skipping AWS-managed key: $key_id"
                fi
            fi
        done
    else
        log_info "No KMS keys found via aliases"
    fi
    
    # Also check for customer-managed keys without aliases but with HIPAA-related tags or descriptions
    local all_keys=$(AWS_PROFILE="$root_profile" aws kms list-keys \
        --query 'Keys[].KeyId' --output text 2>/dev/null || echo "")
    
    if [[ -n "$all_keys" ]]; then
        for key_id in $all_keys; do
            if [[ -n "$key_id" ]]; then
                # Check if this key has HIPAA-related description or tags
                local key_info=$(AWS_PROFILE="$root_profile" aws kms describe-key \
                    --key-id "$key_id" --query 'KeyMetadata.[KeyManager,KeyState,Description]' \
                    --output json 2>/dev/null || echo "[]")
                
                local key_manager=$(echo "$key_info" | jq -r '.[0]')
                local description=$(echo "$key_info" | jq -r '.[2]')
                
                if [[ "$key_manager" == "CUSTOMER" ]] && [[ "$description" =~ [Hh][Ii][Pp][Aa][Aa] ]]; then
                    # Check if we already processed this key via aliases
                    local already_processed=false
                    if [[ "$aliases" != "[]" ]]; then
                        while read -r alias_key_id; do
                            if [[ "$alias_key_id" == "$key_id" ]]; then
                                already_processed=true
                                break
                            fi
                        done <<< "$(echo "$aliases" | jq -r '.[].TargetKeyId')"
                    fi
                    
                    if [[ "$already_processed" == "false" ]]; then
                        log_info "Found customer-managed KMS key with HIPAA description: $key_id"
                        log_info "  Description: $description"
                        AWS_PROFILE="$root_profile" aws kms schedule-key-deletion \
                            --key-id "$key_id" --pending-window-in-days 7 --no-cli-pager 2>/dev/null || true
                    fi
                fi
            fi
        done
    fi
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

# Cleanup IAM resources
cleanup_iam_resources() {
    local environment="$1"
    
    log_step "Cleaning up IAM resources..."
    
    # Find and cleanup IAM roles with HIPAA/environment naming
    log_info "Cleaning up IAM roles..."
    local roles=$(AWS_PROFILE="$root_profile" aws iam list-roles \
        --query 'Roles[?contains(RoleName, `hipaa`) || contains(RoleName, `'$environment'`) || contains(RoleName, `pulumi`) || contains(RoleName, `cloudtrail`) || contains(RoleName, `ecs`) || contains(RoleName, `rds`) || contains(RoleName, `alb`) || contains(RoleName, `task`) || contains(RoleName, `execution`)].RoleName' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$roles" ]]; then
        for role in $roles; do
            if [[ -n "$role" ]]; then
                log_info "Deleting IAM role: $role"
                
                # Detach all managed policies
                local attached_policies=$(AWS_PROFILE="$root_profile" aws iam list-attached-role-policies \
                    --role-name "$role" --query 'AttachedPolicies[].PolicyArn' \
                    --output text 2>/dev/null || echo "")
                
                if [[ -n "$attached_policies" ]]; then
                    for policy_arn in $attached_policies; do
                        if [[ -n "$policy_arn" ]] && [[ "$policy_arn" != "None" ]]; then
                            log_info "Detaching managed policy: $policy_arn from role: $role"
                            AWS_PROFILE="$root_profile" aws iam detach-role-policy \
                                --role-name "$role" --policy-arn "$policy_arn" \
                                --no-cli-pager 2>/dev/null || true
                        fi
                    done
                fi
                
                # Delete all inline policies
                local inline_policies=$(AWS_PROFILE="$root_profile" aws iam list-role-policies \
                    --role-name "$role" --query 'PolicyNames' \
                    --output text 2>/dev/null || echo "")
                
                if [[ -n "$inline_policies" ]]; then
                    for policy in $inline_policies; do
                        if [[ -n "$policy" ]] && [[ "$policy" != "None" ]]; then
                            log_info "Deleting inline policy: $policy from role: $role"
                            AWS_PROFILE="$root_profile" aws iam delete-role-policy \
                                --role-name "$role" --policy-name "$policy" \
                                --no-cli-pager 2>/dev/null || true
                        fi
                    done
                fi
                
                # Remove role from instance profiles
                local instance_profiles=$(AWS_PROFILE="$root_profile" aws iam list-instance-profiles-for-role \
                    --role-name "$role" --query 'InstanceProfiles[].InstanceProfileName' \
                    --output text 2>/dev/null || echo "")
                
                if [[ -n "$instance_profiles" ]]; then
                    for profile in $instance_profiles; do
                        if [[ -n "$profile" ]] && [[ "$profile" != "None" ]]; then
                            log_info "Removing role $role from instance profile: $profile"
                            AWS_PROFILE="$root_profile" aws iam remove-role-from-instance-profile \
                                --instance-profile-name "$profile" --role-name "$role" \
                                --no-cli-pager 2>/dev/null || true
                        fi
                    done
                fi
                
                # Delete the role
                AWS_PROFILE="$root_profile" aws iam delete-role \
                    --role-name "$role" --no-cli-pager 2>/dev/null || true
            fi
        done
    fi
    
    # Find and cleanup IAM policies
    log_info "Cleaning up IAM policies..."
    local policies=$(AWS_PROFILE="$root_profile" aws iam list-policies \
        --scope Local \
        --query 'Policies[?contains(PolicyName, `hipaa`) || contains(PolicyName, `'$environment'`) || contains(PolicyName, `pulumi`) || contains(PolicyName, `cloudtrail`) || contains(PolicyName, `ecs`) || contains(PolicyName, `rds`) || contains(PolicyName, `alb`)].Arn' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$policies" ]]; then
        for policy_arn in $policies; do
            if [[ -n "$policy_arn" ]]; then
                log_info "Deleting IAM policy: $policy_arn"
                
                # Detach from all users, groups, and roles first
                local entities=$(AWS_PROFILE="$root_profile" aws iam list-entities-for-policy \
                    --policy-arn "$policy_arn" 2>/dev/null || echo "")
                
                if [[ -n "$entities" ]]; then
                    # Detach from users
                    local users=$(echo "$entities" | jq -r '.PolicyUsers[]?.UserName?' 2>/dev/null || echo "")
                    if [[ -n "$users" ]]; then
                        for user in $users; do
                            if [[ -n "$user" ]] && [[ "$user" != "null" ]]; then
                                log_info "Detaching policy from user: $user"
                                AWS_PROFILE="$root_profile" aws iam detach-user-policy \
                                    --user-name "$user" --policy-arn "$policy_arn" \
                                    --no-cli-pager 2>/dev/null || true
                            fi
                        done
                    fi
                    
                    # Detach from groups
                    local groups=$(echo "$entities" | jq -r '.PolicyGroups[]?.GroupName?' 2>/dev/null || echo "")
                    if [[ -n "$groups" ]]; then
                        for group in $groups; do
                            if [[ -n "$group" ]] && [[ "$group" != "null" ]]; then
                                log_info "Detaching policy from group: $group"
                                AWS_PROFILE="$root_profile" aws iam detach-group-policy \
                                    --group-name "$group" --policy-arn "$policy_arn" \
                                    --no-cli-pager 2>/dev/null || true
                            fi
                        done
                    fi
                    
                    # Detach from roles
                    local policy_roles=$(echo "$entities" | jq -r '.PolicyRoles[]?.RoleName?' 2>/dev/null || echo "")
                    if [[ -n "$policy_roles" ]]; then
                        for role in $policy_roles; do
                            if [[ -n "$role" ]] && [[ "$role" != "null" ]]; then
                                log_info "Detaching policy from role: $role"
                                AWS_PROFILE="$root_profile" aws iam detach-role-policy \
                                    --role-name "$role" --policy-arn "$policy_arn" \
                                    --no-cli-pager 2>/dev/null || true
                            fi
                        done
                    fi
                fi
                
                # Delete all policy versions except the default
                local versions=$(AWS_PROFILE="$root_profile" aws iam list-policy-versions \
                    --policy-arn "$policy_arn" \
                    --query 'Versions[?IsDefaultVersion==`false`].VersionId' \
                    --output text 2>/dev/null || echo "")
                
                if [[ -n "$versions" ]]; then
                    for version in $versions; do
                        if [[ -n "$version" ]] && [[ "$version" != "None" ]]; then
                            log_info "Deleting policy version: $version"
                            AWS_PROFILE="$root_profile" aws iam delete-policy-version \
                                --policy-arn "$policy_arn" --version-id "$version" \
                                --no-cli-pager 2>/dev/null || true
                        fi
                    done
                fi
                
                # Delete the policy
                AWS_PROFILE="$root_profile" aws iam delete-policy \
                    --policy-arn "$policy_arn" --no-cli-pager 2>/dev/null || true
            fi
        done
    fi
    
    # Find and cleanup IAM users
    log_info "Cleaning up IAM users..."
    local users=$(AWS_PROFILE="$root_profile" aws iam list-users \
        --query 'Users[?contains(UserName, `hipaa`) || contains(UserName, `'$environment'`) || contains(UserName, `pulumi`) || contains(UserName, `deploy`)].UserName' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$users" ]]; then
        for user in $users; do
            if [[ -n "$user" ]]; then
                log_info "Deleting IAM user: $user"
                
                # Delete access keys
                local access_keys=$(AWS_PROFILE="$root_profile" aws iam list-access-keys \
                    --user-name "$user" --query 'AccessKeyMetadata[].AccessKeyId' \
                    --output text 2>/dev/null || echo "")
                
                if [[ -n "$access_keys" ]]; then
                    for key in $access_keys; do
                        if [[ -n "$key" ]] && [[ "$key" != "None" ]]; then
                            log_info "Deleting access key: $key for user: $user"
                            AWS_PROFILE="$root_profile" aws iam delete-access-key \
                                --user-name "$user" --access-key-id "$key" \
                                --no-cli-pager 2>/dev/null || true
                        fi
                    done
                fi
                
                # Detach managed policies
                local user_attached_policies=$(AWS_PROFILE="$root_profile" aws iam list-attached-user-policies \
                    --user-name "$user" --query 'AttachedPolicies[].PolicyArn' \
                    --output text 2>/dev/null || echo "")
                
                if [[ -n "$user_attached_policies" ]]; then
                    for policy_arn in $user_attached_policies; do
                        if [[ -n "$policy_arn" ]] && [[ "$policy_arn" != "None" ]]; then
                            log_info "Detaching policy: $policy_arn from user: $user"
                            AWS_PROFILE="$root_profile" aws iam detach-user-policy \
                                --user-name "$user" --policy-arn "$policy_arn" \
                                --no-cli-pager 2>/dev/null || true
                        fi
                    done
                fi
                
                # Delete inline policies
                local user_inline_policies=$(AWS_PROFILE="$root_profile" aws iam list-user-policies \
                    --user-name "$user" --query 'PolicyNames' \
                    --output text 2>/dev/null || echo "")
                
                if [[ -n "$user_inline_policies" ]]; then
                    for policy in $user_inline_policies; do
                        if [[ -n "$policy" ]] && [[ "$policy" != "None" ]]; then
                            log_info "Deleting inline policy: $policy from user: $user"
                            AWS_PROFILE="$root_profile" aws iam delete-user-policy \
                                --user-name "$user" --policy-name "$policy" \
                                --no-cli-pager 2>/dev/null || true
                        fi
                    done
                fi
                
                # Remove from groups
                local user_groups=$(AWS_PROFILE="$root_profile" aws iam get-groups-for-user \
                    --user-name "$user" --query 'Groups[].GroupName' \
                    --output text 2>/dev/null || echo "")
                
                if [[ -n "$user_groups" ]]; then
                    for group in $user_groups; do
                        if [[ -n "$group" ]] && [[ "$group" != "None" ]]; then
                            log_info "Removing user $user from group: $group"
                            AWS_PROFILE="$root_profile" aws iam remove-user-from-group \
                                --user-name "$user" --group-name "$group" \
                                --no-cli-pager 2>/dev/null || true
                        fi
                    done
                fi
                
                # Delete login profile if exists
                AWS_PROFILE="$root_profile" aws iam delete-login-profile \
                    --user-name "$user" --no-cli-pager 2>/dev/null || true
                
                # Delete the user
                AWS_PROFILE="$root_profile" aws iam delete-user \
                    --user-name "$user" --no-cli-pager 2>/dev/null || true
            fi
        done
    fi
    
    # Find and cleanup instance profiles
    log_info "Cleaning up instance profiles..."
    local instance_profiles=$(AWS_PROFILE="$root_profile" aws iam list-instance-profiles \
        --query 'InstanceProfiles[?contains(InstanceProfileName, `hipaa`) || contains(InstanceProfileName, `'$environment'`) || contains(InstanceProfileName, `pulumi`) || contains(InstanceProfileName, `ecs`)].InstanceProfileName' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$instance_profiles" ]]; then
        for profile in $instance_profiles; do
            if [[ -n "$profile" ]]; then
                log_info "Deleting instance profile: $profile"
                
                # Remove all roles from instance profile first
                local profile_roles=$(AWS_PROFILE="$root_profile" aws iam get-instance-profile \
                    --instance-profile-name "$profile" \
                    --query 'InstanceProfile.Roles[].RoleName' \
                    --output text 2>/dev/null || echo "")
                
                if [[ -n "$profile_roles" ]]; then
                    for role in $profile_roles; do
                        if [[ -n "$role" ]] && [[ "$role" != "None" ]]; then
                            log_info "Removing role $role from instance profile: $profile"
                            AWS_PROFILE="$root_profile" aws iam remove-role-from-instance-profile \
                                --instance-profile-name "$profile" --role-name "$role" \
                                --no-cli-pager 2>/dev/null || true
                        fi
                    done
                fi
                
                # Delete the instance profile
                AWS_PROFILE="$root_profile" aws iam delete-instance-profile \
                    --instance-profile-name "$profile" --no-cli-pager 2>/dev/null || true
            fi
        done
    fi
    
    log_info "IAM resources cleanup completed"
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