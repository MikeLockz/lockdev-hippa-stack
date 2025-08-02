#!/bin/bash

# Phase 1: Preparation Script
# Handles state backup, protection disable, and snapshot creation

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

PHASE_NAME="prepare"

# Main preparation function
prepare_cleanup() {
    local environment="$1"
    
    log_phase "$PHASE_NAME" "Starting preparation phase for: $environment"
    
    # Load environment configuration
    load_environment_config "$environment"
    
    local root_profile=$(get_env_config "$environment" "root_profile")
    local region=$(get_env_config "$environment" "region")
    
    # Setup AWS environment
    setup_aws_env "$root_profile" "$region"
    
    # Create state backup
    create_state_backup "$environment"
    
    # Disable protections
    disable_protections "$environment"
    
    # Create snapshots
    create_snapshots "$environment"
    
    # Unprotect Pulumi resources
    unprotect_pulumi_resources "$environment"
    
    log_phase_success "$PHASE_NAME" "Preparation phase completed successfully"
}

# Create state backup
create_state_backup() {
    local environment="$1"
    
    log_step "Creating state backup..."
    
    local backup_dir="$PROJECT_DIR/outputs/state-backups"
    mkdir -p "$backup_dir"
    
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_file="$backup_dir/hipaa-$environment-backup-$timestamp.json"
    
    # Backup Pulumi state
    if pulumi stack ls | grep -q "hipaa-$environment"; then
        log_info "Backing up Pulumi stack: hipaa-$environment"
        cd "$PROJECT_DIR"
        pulumi stack select "hipaa-$environment" 2>/dev/null || true
        pulumi stack export --file "$backup_file" 2>/dev/null || {
            log_warning "Could not backup Pulumi state - stack might not exist"
            return 0
        }
        cd - >/dev/null || true
        log_success "Pulumi state backed up to: $backup_file"
    else
        log_info "No Pulumi stack to backup"
    fi
    
    # Backup AWS resources list
    local aws_backup="$backup_dir/aws-resources-$environment-$timestamp.json"
    backup_aws_resources "$environment" "$aws_backup"
}

# Backup AWS resources
backup_aws_resources() {
    local environment="$1"
    local backup_file="$2"
    
    log_info "Creating AWS resources backup..."
    
    local resources=()
    
    # VPCs
    local vpcs=$(AWS_PROFILE="$root_profile" aws ec2 describe-vpcs \
        --filters "Name=tag:Name,Values=*hipaa*" \
        --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo "")
    [[ -n "$vpcs" ]] && resources+=("vpcs": ["$vpcs"])
    
    # RDS instances
    local rds=$(AWS_PROFILE="$root_profile" aws rds describe-db-instances \
        --query 'DBInstances[?contains(DBInstanceIdentifier, `hipaa`) || contains(DBInstanceIdentifier, `'$environment'`)].DBInstanceIdentifier' \
        --output text 2>/dev/null || echo "")
    [[ -n "$rds" ]] && resources+=("rds_instances": ["$rds"])
    
    # S3 buckets
    local buckets=$(AWS_PROFILE="$root_profile" aws s3api list-buckets \
        --query 'Buckets[?contains(Name, `hipaa`) && contains(Name, `'$environment'`)].Name' \
        --output text 2>/dev/null || echo "")
    [[ -n "$buckets" ]] && resources+=("s3_buckets": ["$buckets"])
    
    # ECS clusters
    local clusters=$(AWS_PROFILE="$root_profile" aws ecs list-clusters \
        --query 'clusterArns[?contains(@, `hipaa`) || contains(@, `'$environment'`)]' \
        --output text 2>/dev/null || echo "")
    [[ -n "$clusters" ]] && resources+=("ecs_clusters": ["$clusters"])
    
    # Load balancers
    local lbs=$(AWS_PROFILE="$root_profile" aws elbv2 describe-load-balancers \
        --query 'LoadBalancers[?contains(LoadBalancerName, `hipaa`) || contains(LoadBalancerName, `'$environment'`)].LoadBalancerArn' \
        --output text 2>/dev/null || echo "")
    [[ -n "$lbs" ]] && resources+=("load_balancers": ["$lbs"])
    
    # Create backup JSON
    cat > "$backup_file" <<EOF
{
    "environment": "$environment",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "account": "$(AWS_PROFILE="$root_profile" aws sts get-caller-identity --query Account --output text)",
    "region": "$region",
    "resources": {
        "vpcs": "${vpcs:-}",
        "rds_instances": "${rds:-}",
        "s3_buckets": "${buckets:-}",
        "ecs_clusters": "${clusters:-}",
        "load_balancers": "${lbs:-}"
    }
}
EOF
    
    log_success "AWS resources backed up to: $backup_file"
}

# Disable protections on resources
disable_protections() {
    local environment="$1"
    
    log_step "Disabling resource protections..."
    
    # Disable load balancer deletion protection
    disable_load_balancer_protection "$environment"
    
    # Disable RDS deletion protection
    disable_rds_protection "$environment"
    
    # Disable S3 bucket protection
    disable_s3_protection "$environment"
}

# Disable load balancer protection
disable_load_balancer_protection() {
    local environment="$1"
    
    log_info "Disabling load balancer deletion protection..."
    
    local lbs=$(AWS_PROFILE="$root_profile" aws elbv2 describe-load-balancers \
        --query 'LoadBalancers[?contains(LoadBalancerName, `hipaa`) || contains(LoadBalancerName, `'$environment'`)].LoadBalancerArn' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$lbs" ]]; then
        for lb_arn in $lbs; do
            local lb_name=$(echo "$lb_arn" | sed 's/.*loadbalancer\///g')
            log_info "Disabling deletion protection for: $lb_name"
            
            AWS_PROFILE="$root_profile" aws elbv2 modify-load-balancer-attributes \
                --load-balancer-arn "$lb_arn" \
                --attributes Key=deletion_protection.enabled,Value=false \
                --no-cli-pager 2>/dev/null || {
                log_warning "Could not disable protection for: $lb_name"
            }
        done
    else
        log_info "No load balancers found to disable protection"
    fi
}

# Disable RDS deletion protection
disable_rds_protection() {
    local environment="$1"
    
    log_info "Disabling RDS deletion protection..."
    
    local db_instances=$(AWS_PROFILE="$root_profile" aws rds describe-db-instances \
        --query 'DBInstances[?contains(DBInstanceIdentifier, `hipaa`) || contains(DBInstanceIdentifier, `'$environment'`)].DBInstanceIdentifier' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$db_instances" ]]; then
        for db_id in $db_instances; do
            log_info "Disabling deletion protection for: $db_id"
            
            AWS_PROFILE="$root_profile" aws rds modify-db-instance \
                --db-instance-identifier "$db_id" \
                --deletion-protection false \
                --apply-immediately \
                --no-cli-pager 2>/dev/null || {
                log_warning "Could not disable protection for: $db_id"
            }
        done
    else
        log_info "No RDS instances found to disable protection"
    fi
}

# Disable S3 bucket protection
disable_s3_protection() {
    local environment="$1"
    
    log_info "Checking S3 bucket protections..."
    
    local buckets=$(AWS_PROFILE="$root_profile" aws s3api list-buckets \
        --query 'Buckets[?contains(Name, `hipaa`) && contains(Name, `'$environment'`)].Name' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$buckets" ]]; then
        for bucket in $buckets; do
            log_info "Checking bucket: $bucket"
            
            # Check if bucket has versioning
            local versioning=$(AWS_PROFILE="$root_profile" aws s3api get-bucket-versioning \
                --bucket "$bucket" --query 'Status' --output text 2>/dev/null || echo "")
            
            if [[ "$versioning" == "Enabled" ]]; then
                log_info "Bucket has versioning enabled: $bucket"
            fi
        done
    else
        log_info "No S3 buckets found"
    fi
}

# Create snapshots
create_snapshots() {
    local environment="$1"
    
    log_step "Creating resource snapshots..."
    
    # Create RDS snapshots
    create_rds_snapshots "$environment"
    
    # Create EBS snapshots
    create_ebs_snapshots "$environment"
}

# Create RDS snapshots
create_rds_snapshots() {
    local environment="$1"
    
    log_info "Creating RDS snapshots..."
    
    local db_instances=$(AWS_PROFILE="$root_profile" aws rds describe-db-instances \
        --query 'DBInstances[?contains(DBInstanceIdentifier, `hipaa`) || contains(DBInstanceIdentifier, `'$environment'`)].DBInstanceIdentifier' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$db_instances" ]]; then
        for db_id in $db_instances; do
            local snapshot_name="hipaa-${environment}-${db_id}-$(date +%Y%m%d-%H%M%S)"
            log_info "Creating snapshot: $snapshot_name"
            
            AWS_PROFILE="$root_profile" aws rds create-db-snapshot \
                --db-instance-identifier "$db_id" \
                --db-snapshot-identifier "$snapshot_name" \
                --no-cli-pager 2>/dev/null || {
                log_warning "Could not create snapshot for: $db_id"
            }
        done
    else
        log_info "No RDS instances found for snapshots"
    fi
}

# Create EBS snapshots
create_ebs_snapshots() {
    local environment="$1"
    
    log_info "Creating EBS snapshots..."
    
    local volumes=$(AWS_PROFILE="$root_profile" aws ec2 describe-volumes \
        --query 'Volumes[?contains(Tags[?Key==`Name`].Value, `hipaa`) || contains(Tags[?Key==`Name`].Value, `'$environment'`)].VolumeId' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$volumes" ]]; then
        for volume in $volumes; do
            local snapshot_name="hipaa-${environment}-${volume}-$(date +%Y%m%d-%H%M%S)"
            log_info "Creating EBS snapshot: $snapshot_name"
            
            AWS_PROFILE="$root_profile" aws ec2 create-snapshot \
                --volume-id "$volume" \
                --description "$snapshot_name" \
                --tag-specifications "ResourceType=snapshot,Tags=[{Key=Name,Value=$snapshot_name}]" \
                --no-cli-pager 2>/dev/null || {
                log_warning "Could not create snapshot for: $volume"
            }
        done
    else
        log_info "No EBS volumes found for snapshots"
    fi
}

# Unprotect Pulumi resources
unprotect_pulumi_resources() {
    local environment="$1"
    
    log_step "Unprotecting Pulumi resources..."
    
    # Check if Pulumi stack exists
    if ! pulumi stack ls 2>/dev/null | grep -q "hipaa-$environment"; then
        log_info "No Pulumi stack found for environment: $environment"
        return 0
    fi
    
    # Select the stack
    cd "$PROJECT_DIR"
    pulumi stack select "hipaa-$environment" 2>/dev/null || {
        log_warning "Could not select Pulumi stack: hipaa-$environment"
        return 0
    }
    
    # Get protected resources
    log_info "Checking for protected resources..."
    
    # Use Pulumi to list protected resources
    local protected_resources=$(pulumi stack --show-urns 2>/dev/null | grep -i protect | awk '{print $1}' || echo "")
    
    if [[ -n "$protected_resources" ]]; then
        log_info "Found protected resources, unprotecting..."
        
        # Create unprotection script
        local unprotect_script="$PROJECT_DIR/scripts/unprotect-resources.py"
        if [[ -f "$unprotect_script" ]]; then
            python3 "$unprotect_script" --environment "$environment" || {
                log_warning "Could not unprotect all resources"
            }
        else
            log_warning "Unprotect script not found: $unprotect_script"
        fi
    else
        log_info "No protected Pulumi resources found"
    fi
    
    cd - >/dev/null || true
}

# Hook function for phase execution
phase_prepare_hook() {
    local environment="$1"
    local options="$2"
    
    log_info "Executing preparation phase for: $environment"
    
    if is_dry_run; then
        log_info "[DRY RUN] Would prepare environment: $environment"
        log_info "[DRY RUN] Would create state backups"
        log_info "[DRY RUN] Would disable resource protections"
        log_info "[DRY RUN] Would create snapshots"
        return 0
    fi
    
    prepare_cleanup "$environment"
}

# Allow direct execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 \u003cenvironment\u003e [options]"
        echo "  environment: dev, staging, prod"
        echo "  options: --dry-run, --force"
        exit 1
    fi
    
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    prepare_cleanup "$1"
fi