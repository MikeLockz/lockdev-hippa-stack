#!/bin/bash

# Phase 1: Pre-cleanup preparation
# Disables protections, creates snapshots, and prepares for safe cleanup

source "${LIB_DIR:-./lib}/utils.sh"

execute_phase_prepare() {
    phase "Starting preparation phase"
    
    # Configure AWS
    configure_aws "$ENVIRONMENT" || exit 1
    
    # Check prerequisites
    check_prerequisites || exit 1
    
    # Create state backup
    create_state_backup
    
    # Disable load balancer deletion protection
    disable_lb_protection
    
    # Disable RDS deletion protection
    disable_rds_protection
    
    # Create resource snapshots
    create_snapshots
    
    # Unprotect Pulumi resources
    unprotect_pulumi_resources
    
    phase "Preparation phase completed"
}

# Create state backup
create_state_backup() {
    log "Creating state backup before cleanup"
    
    local backup_dir=$(create_backup_dir "./backups/pre-cleanup")
    
    # Backup current AWS state
    {
        echo "# AWS Resource State - $(date)"
        echo "Environment: $ENVIRONMENT"
        echo ""
        
        echo "## VPCs"
        aws ec2 describe-vpcs --filters "Name=tag:Name,Values=*hipaa*" --query 'Vpcs[*].{ID:VpcId,Name:Tags[?Key==`Name`]|[0].Value}' --output table 2>/dev/null || echo "No VPCs found"
        
        echo "## RDS Instances"
        aws rds describe-db-instances --query 'DBInstances[?starts_with(DBInstanceIdentifier, `hipaa`)].{ID:DBInstanceIdentifier,Engine:Engine,Status:DBInstanceStatus}' --output table 2>/dev/null || echo "No RDS instances"
        
        echo "## Load Balancers"
        aws elbv2 describe-load-balancers --query 'LoadBalancers[?contains(LoadBalancerName, `hipaa`)].{Name:LoadBalancerName,Type:Type,State:State.Code}' --output table 2>/dev/null || echo "No load balancers"
        
        echo "## Security Groups"
        aws ec2 describe-security-groups --filters "Name=group-name,Values=hipaa-*" --query 'SecurityGroups[*].{ID:GroupId,Name:GroupName}' --output table 2>/dev/null || echo "No security groups"
        
        echo "## S3 Buckets"
        aws s3api list-buckets --query 'Buckets[?contains(Name, `hipaa`)].Name' --output table 2>/dev/null || echo "No S3 buckets"
        
    } > "$backup_dir/state-backup.txt"
    
    log "State backup created: $backup_dir/state-backup.txt"
}

# Disable load balancer deletion protection
disable_lb_protection() {
    log "Disabling load balancer deletion protection"
    
    local lbs=$(aws elbv2 describe-load-balancers --query 'LoadBalancers[*].[LoadBalancerArn,LoadBalancerName]' --output text | grep -i "hipaa\|$ENVIRONMENT" || echo "")
    
    if [[ -z "$lbs" ]]; then
        log "No load balancers found with hipaa/$ENVIRONMENT naming"
        return 0
    fi
    
    echo "$lbs" | while read arn name; do
        if [[ -n "$arn" && -n "$name" ]]; then
            info "Disabling deletion protection for: $name"
            
            if [[ "$DRY_RUN" == "true" ]]; then
                log "DRY RUN: Would disable deletion protection for $name"
                continue
            fi
            
            aws elbv2 modify-load-balancer-attributes \
                --load-balancer-arn "$arn" \
                --attributes Key=deletion_protection.enabled,Value=false \
                2>/dev/null || warn "Could not disable protection for $name"
        fi
    done
    
    sleep 3
}

# Disable RDS deletion protection
disable_rds_protection() {
    log "Disabling RDS deletion protection"
    
    local rds_instances=$(aws rds describe-db-instances --query 'DBInstances[?starts_with(DBInstanceIdentifier, `hipaa`)]' --output json)
    
    if [[ "$rds_instances" == "[]" ]]; then
        log "No RDS instances found"
        return 0
    fi
    
    echo "$rds_instances" | jq -r '.[].DBInstanceIdentifier' | while read -r instance; do
        if [[ -n "$instance" ]]; then
            info "Disabling deletion protection for RDS: $instance"
            
            if [[ "$DRY_RUN" == "true" ]]; then
                log "DRY RUN: Would disable deletion protection for $instance"
                continue
            fi
            
            aws rds modify-db-instance \
                --db-instance-identifier "$instance" \
                --deletion-protection=false \
                --apply-immediately \
                2>/dev/null || warn "Could not disable deletion protection for $instance"
        fi
    done
    
    sleep 5
}

# Create resource snapshots
create_snapshots() {
    log "Creating resource snapshots"
    
    # Create RDS snapshots
    create_rds_snapshots
    
    # Create EBS snapshots
    create_ebs_snapshots
    
    log "Snapshots created successfully"
}

# Create RDS snapshots
create_rds_snapshots() {
    log "Creating RDS snapshots"
    
    local rds_instances=$(aws rds describe-db-instances --query 'DBInstances[?starts_with(DBInstanceIdentifier, `hipaa`)].DBInstanceIdentifier' --output text)
    
    if [[ -z "$rds_instances" ]]; then
        log "No RDS instances to snapshot"
        return 0
    fi
    
    for instance in $rds_instances; do
        local snapshot_name="${instance}-cleanup-$(date +%Y%m%d-%H%M%S)"
        
        if [[ "$DRY_RUN" == "true" ]]; then
            log "DRY RUN: Would create snapshot: $snapshot_name"
            continue
        fi
        
        info "Creating snapshot: $snapshot_name"
        aws rds create-db-snapshot \
            --db-snapshot-identifier "$snapshot_name" \
            --db-instance-identifier "$instance" \
            2>/dev/null || warn "Could not create snapshot for $instance"
    done
}

# Create EBS snapshots
create_ebs_snapshots() {
    log "Creating EBS snapshots"
    
    local volumes=$(aws ec2 describe-volumes --filters "Name=tag:Environment,Values=$ENVIRONMENT" --query 'Volumes[*].VolumeId' --output text)
    
    if [[ -z "$volumes" ]]; then
        log "No EBS volumes to snapshot"
        return 0
    fi
    
    for volume in $volumes; do
        local snapshot_name="${volume}-cleanup-$(date +%Y%m%d-%H%M%S)"
        
        if [[ "$DRY_RUN" == "true" ]]; then
            log "DRY RUN: Would create EBS snapshot: $snapshot_name"
            continue
        fi
        
        info "Creating EBS snapshot: $snapshot_name"
        aws ec2 create-snapshot \
            --volume-id "$volume" \
            --description "Cleanup backup for $volume" \
            --tag-specifications "ResourceType=snapshot,Tags=[{Key=Name,Value=$snapshot_name},{Key=Environment,Value=$ENVIRONMENT},{Key=Purpose,Value=cleanup-backup}]" \
            2>/dev/null || warn "Could not create snapshot for $volume"
    done
}

# Unprotect Pulumi resources
unprotect_pulumi_resources() {
    log "Unprotecting Pulumi resources"
    
    local stack_name="hipaa-$ENVIRONMENT"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "DRY RUN: Would unprotect Pulumi resources in stack: $stack_name"
        return 0
    fi
    
    if ! pulumi stack ls 2>/dev/null | grep -q "$stack_name"; then
        log "Pulumi stack $stack_name not found, skipping"
        return 0
    fi
    
    pulumi stack select "$stack_name" 2>/dev/null || return 0
    
    local protected_resources=$(pulumi stack export 2>/dev/null | jq -r '.deployment.resources[] | select(.protect == true) | .urn' 2>/dev/null || echo "")
    
    if [[ -n "$protected_resources" ]]; then
        local count=$(echo "$protected_resources" | wc -l)
        info "Unprotecting $count protected resources"
        
        echo "$protected_resources" | while read urn; do
            if [[ -n "$urn" ]]; then
                pulumi state unprotect --yes "$urn" 2>/dev/null || warn "Could not unprotect: $urn"
            fi
        done
    else
        log "No protected resources found"
    fi
}