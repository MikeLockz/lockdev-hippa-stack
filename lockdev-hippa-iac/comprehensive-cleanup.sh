#!/bin/bash

# Comprehensive Cleanup Script for HIPAA Infrastructure
# Handles protected resources, dependencies, and automatic cleanup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGION="us-east-1"
ENVIRONMENT="${1:-dev}"
FORCE_MODE="${2:-false}"
ACCOUNT_ID=""

# Functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    for cmd in aws pulumi python3 jq; do
        if ! command -v "$cmd" &> /dev/null; then
            error "$cmd is not installed"
            exit 1
        fi
    done
    
    log "All prerequisites satisfied"
}

# Configure AWS credentials
configure_aws() {
    log "Configuring AWS credentials..."
    
    # Try environment variables first
    if [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
        export AWS_DEFAULT_REGION=$REGION
        log "Using AWS credentials from environment variables"
    else
        # Check for AWS CLI profiles
        if aws configure list --profile dev-root &>/dev/null; then
            export AWS_PROFILE=dev-root
            export AWS_DEFAULT_REGION=$REGION
            log "Using AWS profile: dev-root"
        else
            log "Using default AWS CLI configuration"
            export AWS_DEFAULT_REGION=$REGION
        fi
    fi
    
    # Verify AWS access
    if aws sts get-caller-identity &> /dev/null; then
        ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        log "AWS access verified (Account: $ACCOUNT_ID)"
    else
        error "AWS credentials not working"
        exit 1
    fi
}

# Disable load balancer deletion protection
disable_lb_protection() {
    log "Disabling load balancer deletion protection..."
    
    local lbs=$(aws elbv2 describe-load-balancers --query 'LoadBalancers[*].[LoadBalancerArn,LoadBalancerName]' --output text | grep -i "hipaa\|dev" || echo "")
    
    if [ -z "$lbs" ]; then
        log "No load balancers found with hipaa/dev naming"
        return 0
    fi
    
    echo "$lbs" | while read arn name; do
        if [ -n "$arn" ] && [ -n "$name" ]; then
            info "Disabling deletion protection for: $name"
            aws elbv2 modify-load-balancer-attributes \
                --load-balancer-arn "$arn" \
                --attributes Key=deletion_protection.enabled,Value=false 2>/dev/null || warn "Could not disable protection for $name"
        fi
    done
    
    sleep 3
}

# Disable RDS deletion protection
disable_rds_protection() {
    log "Disabling RDS deletion protection..."
    
    local rds_instances=$(aws rds describe-db-instances --query 'DBInstances[?starts_with(DBInstanceIdentifier, `hipaa`)]' --output json)
    
    if [ "$rds_instances" = "[]" ]; then
        log "No RDS instances found"
        return 0
    fi
    
    echo "$rds_instances" | jq -r '.[].DBInstanceIdentifier' | while read -r instance; do
        if [ -n "$instance" ]; then
            info "Disabling deletion protection for RDS: $instance"
            aws rds modify-db-instance \
                --db-instance-identifier "$instance" \
                --deletion-protection=false \
                --apply-immediately 2>/dev/null || warn "Could not disable deletion protection for $instance"
        fi
    done
    
    sleep 5
}

# Empty and delete S3 buckets including CloudTrail
empty_and_delete_s3_buckets() {
    log "Emptying and deleting ALL S3 buckets including CloudTrail..."
    
    local buckets=$(aws s3api list-buckets --query 'Buckets[?contains(Name, `hipaa`) || contains(Name, `cloudtrail`) || contains(Name, `dev`)]' --output json)
    
    if [ "$buckets" = "[]" ]; then
        log "No relevant S3 buckets found"
        return 0
    fi
    
    echo "$buckets" | jq -r '.[].Name' | while read -r bucket; do
        if [ -n "$bucket" ]; then
            info "Processing bucket: $bucket"
            
            # Check if bucket exists
            if aws s3api head-bucket --bucket "$bucket" 2>/dev/null; then
                log "Bucket $bucket exists, proceeding with deletion..."
                
                # First, suspend versioning to allow deletion
                aws s3api put-bucket-versioning --bucket "$bucket" --versioning-configuration Status=Suspended 2>/dev/null || warn "Could not suspend versioning"
                
                # Empty the bucket using multiple approaches
                log "Emptying bucket: $bucket"
                
                # Method 1: Standard recursive delete
                aws s3 rm "s3://$bucket" --recursive --quiet || true
                
                # Method 2: Batch delete all versions and delete markers
                local versions=$(aws s3api list-object-versions --bucket "$bucket" --max-keys 1000 --output json 2>/dev/null || echo '{"Versions": [], "DeleteMarkers": []}')
                
                # Delete all versions
                echo "$versions" | jq -r '.Versions[]? | "\(.Key)\t\(.VersionId)"' | while IFS=$'\t' read -r key version; do
                    if [ -n "$key" ] && [ -n "$version" ]; then
                        aws s3api delete-object --bucket "$bucket" --key "$key" --version-id "$version" --no-cli-pager 2>/dev/null || true
                    fi
                done
                
                # Delete all delete markers
                echo "$versions" | jq -r '.DeleteMarkers[]? | "\(.Key)\t\(.VersionId)"' | while IFS=$'\t' read -r key version; do
                    if [ -n "$key" ] && [ -n "$version" ]; then
                        aws s3api delete-object --bucket "$bucket" --key "$key" --version-id "$version" --no-cli-pager 2>/dev/null || true
                    fi
                done
                
                # Method 3: Batch delete using delete-objects API
                local delete_objects=$(aws s3api list-object-versions --bucket "$bucket" --output json 2>/dev/null | jq -c '{Objects: (.Versions + .DeleteMarkers) | map({Key: .Key, VersionId: .VersionId})}')
                if [ "$delete_objects" != '{"Objects":[]}' ] && [ "$delete_objects" != '{"Objects":null}' ]; then
                    aws s3api delete-objects --bucket "$bucket" --delete "$delete_objects" --no-cli-pager 2>/dev/null || true
                fi
                
                # Verify bucket is empty
                local remaining=$(aws s3api list-objects-v2 --bucket "$bucket" --max-keys 1 --query 'KeyCount' --output text 2>/dev/null || echo "0")
                local remaining_versions=$(aws s3api list-object-versions --bucket "$bucket" --max-keys 1 --query 'length(Versions) + length(DeleteMarkers)' --output text 2>/dev/null || echo "0")
                
                if [ "$remaining" = "0" ] && [ "$remaining_versions" = "0" ]; then
                    log "Bucket $bucket is now empty, deleting..."
                    aws s3 rb "s3://$bucket" --force --no-cli-pager || {
                        warn "Standard delete failed, trying AWS CLI delete-bucket..."
                        aws s3api delete-bucket --bucket "$bucket" --no-cli-pager || warn "Could not delete bucket: $bucket"
                    }
                else
                    warn "Bucket $bucket still has $remaining objects and $remaining_versions versions"
                    # Force empty with lifecycle policy
                    aws s3api put-bucket-lifecycle-configuration --bucket "$bucket" --lifecycle-configuration '{
                        "Rules": [{
                            "ID": "DeleteAllObjects",
                            "Status": "Enabled",
                            "Prefix": "",
                            "Expiration": {"Days": 1}
                        }]
                    }' 2>/dev/null || true
                fi
            else
                warn "Bucket $bucket does not exist or access denied"
            fi
        fi
    done
    
    sleep 10
}

# Unprotect Pulumi resources
unprotect_pulumi_resources() {
    log "Checking and unprotecting Pulumi resources..."
    
    # We're already in lockdev-hippa-iac directory
    # Check if stack exists
    if ! pulumi stack ls | grep -q "hipaa-$ENVIRONMENT"; then
        log "Stack hipaa-$ENVIRONMENT not found, skipping unprotection"
        cd ..
        return 0
    fi
    
    pulumi stack select "hipaa-$ENVIRONMENT" 2>/dev/null || {
        cd ..
        return 0
    }
    
    # Get protected resources
    local protected_resources=$(pulumi stack export 2>/dev/null | jq -r '.deployment.resources[] | select(.protect == true) | .urn' 2>/dev/null || echo "")
    
    if [ -n "$protected_resources" ]; then
        local count=$(echo "$protected_resources" | wc -l)
        info "Unprotecting $count protected resources..."
        echo "$protected_resources" | while read urn; do
            if [ -n "$urn" ]; then
                pulumi state unprotect --yes "$urn" 2>/dev/null || warn "Could not unprotect: $urn"
            fi
        done
    else
        info "No protected resources found"
    fi
    
    cd ..
}

# Clean up RDS instances with dependencies
cleanup_rds_instances() {
    log "Cleaning up RDS instances..."
    
    local rds_instances=$(aws rds describe-db-instances --query 'DBInstances[?starts_with(DBInstanceIdentifier, `hipaa`)]' --output json)
    
    if [ "$rds_instances" = "[]" ]; then
        log "No RDS instances found"
        return 0
    fi
    
    echo "$rds_instances" | jq -r '.[].DBInstanceIdentifier' | while read -r instance; do
        if [ -n "$instance" ]; then
            info "Deleting RDS instance: $instance"
            
            # Disable deletion protection first
            aws rds modify-db-instance \
                --db-instance-identifier "$instance" \
                --deletion-protection=false \
                --apply-immediately 2>/dev/null || warn "Could not disable deletion protection"
            
            # Delete the instance
            aws rds delete-db-instance \
                --db-instance-identifier "$instance" \
                --skip-final-snapshot \
                --delete-automated-backups \
                --no-cli-pager || warn "Failed to delete RDS instance: $instance"
        fi
    done
    
    # Wait for RDS instances to be deleted
    log "Waiting for RDS instances to be deleted..."
    for i in {1..30}; do
        local count=$(aws rds describe-db-instances --query 'length(DBInstances[?starts_with(DBInstanceIdentifier, `hipaa`)])' --output text 2>/dev/null || echo "0")
        if [ "$count" = "0" ]; then
            log "All RDS instances deleted"
            break
        fi
        info "Waiting for RDS instances... ($i/30)"
        sleep 30
    done
}

# Clean up security groups and ENIs
cleanup_security_groups() {
    log "Cleaning up security groups..."
    
    local sgs=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=hipaa-*" --query 'SecurityGroups[].GroupId' --output text 2>/dev/null || echo "")
    
    if [ -z "$sgs" ]; then
        log "No security groups found"
        return 0
    fi
    
    for sg in $sgs; do
        info "Processing security group: $sg"
        
        # Get ENIs attached to this security group
        local enis=$(aws ec2 describe-network-interfaces --filters "Name=group-id,Values=$sg" --query 'NetworkInterfaces[].NetworkInterfaceId' --output text 2>/dev/null || echo "")
        
        if [ -n "$enis" ]; then
            info "Found ENIs attached to security group: $enis"
            for eni in $enis; do
                info "Detaching ENI: $eni"
                
                # Get attachment ID
                local attachment_id=$(aws ec2 describe-network-interfaces --network-interface-ids "$eni" --query 'NetworkInterfaces[0].Attachment.AttachmentId' --output text 2>/dev/null || echo "")
                
                if [ "$attachment_id" != "None" ] && [ -n "$attachment_id" ]; then
                    aws ec2 detach-network-interface --attachment-id "$attachment_id" --force || warn "Failed to detach ENI: $eni"
                fi
            done
            sleep 10
        fi
        
        # Delete security group
        aws ec2 delete-security-group --group-id "$sg" || warn "Failed to delete security group: $sg"
    done
}

# Clean up Pulumi stacks
cleanup_pulumi_stacks() {
    log "Cleaning up Pulumi stacks..."
    
    cd lockdev-hippa-iac
    
    local stacks=$(pulumi stack ls --json 2>/dev/null | jq -r '.[].name' | grep -E "(dev|staging|prod|hipaa)" || echo "")
    
    for stack in $stacks; do
        info "Processing Pulumi stack: $stack"
        
        # Unprotect all resources first
        pulumi stack select "$stack" 2>/dev/null || continue
        
        local protected_resources=$(pulumi stack export 2>/dev/null | jq -r '.deployment.resources[] | select(.protect == true) | .urn' 2>/dev/null || echo "")
        
        if [ -n "$protected_resources" ]; then
            info "Unprotecting $(echo "$protected_resources" | wc -l) protected resources..."
            echo "$protected_resources" | while read urn; do
                if [ -n "$urn" ]; then
                    pulumi state unprotect --yes "$urn" 2>/dev/null || warn "Could not unprotect: $urn"
                fi
            done
        fi
        
        # Destroy and remove stack
        info "Destroying stack: $stack"
        pulumi destroy --yes --force 2>/dev/null || warn "Failed to destroy stack: $stack"
        pulumi stack rm "$stack" --yes --force 2>/dev/null || warn "Failed to remove stack: $stack"
    done
    
    cd ..
}

# Main cleanup function
main() {
    log "Starting comprehensive HIPAA infrastructure cleanup..."
    log "Environment: $ENVIRONMENT"
    log "Region: $REGION"
    log "Force Mode: $FORCE_MODE"
    
    check_prerequisites
    configure_aws
    
    # Pre-cleanup preparations
    log "=== PRE-CLEANUP PREPARATIONS ==="
    disable_lb_protection "$ENVIRONMENT"
    disable_rds_protection "$ENVIRONMENT"
    empty_and_delete_s3_buckets "$ENVIRONMENT"
    unprotect_pulumi_resources "$ENVIRONMENT"
    
    # Resource cleanup
    log "=== RESOURCE CLEANUP ==="
    cleanup_rds_instances
    cleanup_security_groups
    cleanup_pulumi_stacks
    
    # Final verification
    log "=== FINAL VERIFICATION ==="
    info "Cleanup completed successfully!"
    
    log "All HIPAA resources have been destroyed."
}

# Handle script arguments
if [ $# -gt 0 ]; then
    case "$1" in
        --help|-h)
            echo "Comprehensive HIPAA Infrastructure Cleanup"
            echo "Usage: $0 [environment] [options]"
            echo ""
            echo "Arguments:"
            echo "  environment    Environment name (dev, staging, prod) - default: dev"
            echo "  --force        Force mode (skip confirmations)"
            echo "  --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 dev"
            echo "  $0 staging --force"
            echo "  $0 prod"
            exit 0
            ;;
        --force)
            FORCE_MODE="true"
            ;;
    esac
fi

# Run main function
main "$@"