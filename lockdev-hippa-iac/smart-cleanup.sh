#!/bin/bash

# Smart cleanup script for HIPAA infrastructure
# Handles RDS dependencies properly before security group deletion

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REGION="us-east-1"
STACK_NAME="hipaa-dev"
PROJECT_NAME="lockdev-hippa-iac"

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

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    if ! command -v aws &> /dev/null; then
        error "AWS CLI is not installed"
        exit 1
    fi
    
    if ! command -v pulumi &> /dev/null; then
        error "Pulumi is not installed"
        exit 1
    fi
    
    if ! command -v python3 &> /dev/null; then
        error "Python3 is not installed"
        exit 1
    fi
    
    log "Prerequisites check passed"
}

# Configure AWS credentials with graceful fallback
configure_aws() {
    log "Configuring AWS credentials..."
    
    # Try environment variables first
    if [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
        log "AWS credentials configured via environment variables"
        export AWS_DEFAULT_REGION=$REGION
    else
        warn "AWS credentials not set as environment variables"
        warn "Will attempt to use AWS CLI configuration or instance profile"
    fi
    
    # Check for configured AWS CLI profiles
    if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
        log "Checking AWS CLI profiles..."
        
        # Check for dev-root profile (root credentials)
        if aws configure list --profile dev-root &>/dev/null; then
            export AWS_PROFILE=dev-root
            export AWS_DEFAULT_REGION=$REGION
            log "Using AWS profile: dev-root"
        # Check for default profile
        elif aws configure list &>/dev/null; then
            export AWS_DEFAULT_REGION=$REGION
            log "Using default AWS CLI configuration"
        # Check for pulumi-deploy-user-dev profile
        elif aws configure list --profile pulumi-deploy-user-dev &>/dev/null; then
            export AWS_PROFILE=pulumi-deploy-user-dev
            export AWS_DEFAULT_REGION=$REGION
            log "Using AWS profile: pulumi-deploy-user-dev"
        else
            warn "No AWS CLI profiles found, will try instance profile"
        fi
    fi
    
    # Verify AWS access with retry
    local max_attempts=3
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if aws sts get-caller-identity &> /dev/null; then
            ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
            log "AWS access verified (Account: $ACCOUNT_ID)"
            return 0
        else
            warn "AWS credentials check failed (attempt $attempt/$max_attempts)"
            if [ $attempt -lt $max_attempts ]; then
                sleep 5
            fi
        fi
        attempt=$((attempt + 1))
    done
    
    error "AWS credentials not properly configured"
    error "Please configure AWS credentials using one of these methods:"
    error "1. Environment variables: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
    error "2. AWS CLI: aws configure"
    error "3. IAM instance profile (for EC2 instances)"
    error "4. AWS CLI profile: aws configure --profile dev-root"
    return 1
}

# Fix security group dependencies
fix_security_group_dependencies() {
    log "Fixing security group dependencies..."
    
    # Run the Python script to handle RDS and security group cleanup
    if [ -f "fix-security-group-deletion.py" ]; then
        log "Running security group fix script..."
        python3 fix-security-group-deletion.py
    else
        error "Security group fix script not found"
        exit 1
    fi
}

# Clean up Pulumi resources
cleanup_pulumi() {
    log "Cleaning up Pulumi resources..."
    
    # Navigate to the correct directory
    cd "$(dirname "$0")"
    
    # Check if Pulumi stack exists
    if pulumi stack ls | grep -q "$STACK_NAME"; then
        log "Pulumi stack $STACK_NAME found"
        
        # Select the stack
        pulumi stack select "$STACK_NAME"
        
        # Try to destroy with refresh
        log "Attempting Pulumi destroy with refresh..."
        
        # First, try a gentle approach
        if pulumi destroy --yes --refresh --skip-preview; then
            log "Pulumi destroy completed successfully"
        else
            warn "Initial destroy failed, trying with force..."
            
            # Refresh the stack state
            pulumi refresh --yes
            
            # Try again with force
            if pulumi destroy --yes --force; then
                log "Pulumi destroy completed with force"
            else
                error "Pulumi destroy failed"
                return 1
            fi
        fi
        
        # Remove the stack
        pulumi stack rm "$STACK_NAME" --yes --force
        log "Pulumi stack removed"
    else
        log "Pulumi stack $STACK_NAME not found"
    fi
}

# Clean up any remaining AWS resources
cleanup_aws_resources() {
    log "Cleaning up any remaining AWS resources..."
    
    # Clean up RDS instances
    log "Checking for remaining RDS instances..."
    RDS_INSTANCES=$(aws rds describe-db-instances --query 'DBInstances[?starts_with(DBInstanceIdentifier, `hipaa`)]' --region $REGION --output json)
    
    if [ "$RDS_INSTANCES" != "[]" ]; then
        log "Found remaining RDS instances, cleaning up..."
        echo "$RDS_INSTANCES" | jq -r '.[].DBInstanceIdentifier' | while read -r instance; do
            log "Deleting RDS instance: $instance"
            aws rds delete-db-instance \
                --db-instance-identifier "$instance" \
                --skip-final-snapshot \
                --delete-automated-backups \
                --region $REGION \
                --no-cli-pager || warn "Failed to delete RDS instance: $instance"
        done
    fi
    
    # Clean up security groups
    log "Checking for remaining security groups..."
    SECURITY_GROUPS=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=hipaa-*" --region $REGION --query 'SecurityGroups[].GroupId' --output text)
    
    if [ -n "$SECURITY_GROUPS" ]; then
        log "Found remaining security groups: $SECURITY_GROUPS"
        for sg in $SECURITY_GROUPS; do
            log "Attempting to delete security group: $sg"
            
            # First, check for network interfaces
            ENIS=$(aws ec2 describe-network-interfaces --filters "Name=group-id,Values=$sg" --region $REGION --query 'NetworkInterfaces[].NetworkInterfaceId' --output text)
            
            if [ -n "$ENIS" ]; then
                log "Found network interfaces attached to security group: $ENIS"
                for eni in $ENIS; do
                    log "Detaching network interface: $eni"
                    ATTACHMENT_ID=$(aws ec2 describe-network-interfaces --network-interface-ids $eni --region $REGION --query 'NetworkInterfaces[0].Attachment.AttachmentId' --output text)
                    
                    if [ "$ATTACHMENT_ID" != "None" ] && [ -n "$ATTACHMENT_ID" ]; then
                        aws ec2 detach-network-interface --attachment-id "$ATTACHMENT_ID" --region $REGION --force || warn "Failed to detach ENI: $eni"
                        sleep 30
                    fi
                done
            fi
            
            # Now try to delete the security group
            aws ec2 delete-security-group --group-id "$sg" --region $REGION || warn "Failed to delete security group: $sg"
        done
    fi
    
    # Clean up VPC resources
    log "Checking for remaining VPC resources..."
    
    # Clean up NAT gateways
    NAT_GWS=$(aws ec2 describe-nat-gateways --filter "Name=tag:Name,Values=NAT-Gateway" --region $REGION --query 'NatGateways[].NatGatewayId' --output text)
    
    if [ -n "$NAT_GWS" ]; then
        log "Found remaining NAT gateways: $NAT_GWS"
        for nat in $NAT_GWS; do
            log "Deleting NAT gateway: $nat"
            aws ec2 delete-nat-gateway --nat-gateway-id "$nat" --region $REGION --no-cli-pager
        done
    fi
    
    # Clean up EIPs
    EIPS=$(aws ec2 describe-addresses --filters "Name=tag:Name,Values=NAT-EIP" --region $REGION --query 'Addresses[].AllocationId' --output text)
    
    if [ -n "$EIPS" ]; then
        log "Found remaining EIPs: $EIPS"
        for eip in $EIPS; do
            log "Releasing EIP: $eip"
            aws ec2 release-address --allocation-id "$eip" --region $REGION || warn "Failed to release EIP: $eip"
        done
    fi
    
    log "AWS cleanup completed"
}

# Wait for resource deletion completion
wait_for_completion() {
    log "Waiting for resource deletion to complete..."
    
    # Wait for RDS instances to be deleted
    for i in {1..30}; do
        RDS_COUNT=$(aws rds describe-db-instances --query 'length(DBInstances[?starts_with(DBInstanceIdentifier, `hipaa`)])' --region $REGION --output text 2>/dev/null || echo "0")
        
        if [ "$RDS_COUNT" = "0" ]; then
            log "All RDS instances deleted"
            break
        fi
        
        log "Waiting for RDS instances to be deleted... ($i/30)"
        sleep 30
    done
    
    # Wait for security groups to be deleted
    for i in {1..30}; do
        SG_COUNT=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=hipaa-*" --region $REGION --query 'length(SecurityGroups[])' --output text 2>/dev/null || echo "0")
        
        if [ "$SG_COUNT" = "0" ]; then
            log "All security groups deleted"
            break
        fi
        
        log "Waiting for security groups to be deleted... ($i/30)"
        sleep 10
    done
}

# Main execution
main() {
    log "Starting HIPAA infrastructure cleanup..."
    log "Stack: $STACK_NAME"
    log "Region: $REGION"
    
    check_prerequisites
    
    # Configure AWS credentials with graceful fallback
    if ! configure_aws; then
        error "=== AUTOMATED CLEANUP FAILED ==="
        error "AWS credentials are not properly configured"
        error ""
        error "Please use one of these manual cleanup approaches:"
        error ""
        error "1. Configure AWS credentials and run this script again:"
        error "   export AWS_ACCESS_KEY_ID=your_access_key"
        error "   export AWS_SECRET_ACCESS_KEY=your_secret_key"
        error "   ./smart-cleanup.sh"
        error ""
        error "2. Use the AWS Console to manually delete resources:"
        error "   - RDS instances: hipaa-postgres-db"
        error "   - Security Groups: hipaa-rds-sg, hipaa-ecs-sg, hipaa-alb-sg"
        error "   - NAT Gateways and EIPs"
        error "   - VPC resources"
        error ""
        error "3. Use AWS CLI with proper credentials:"
        error "   aws rds delete-db-instance --db-instance-identifier hipaa-postgres-db --skip-final-snapshot"
        error "   aws ec2 delete-security-group --group-id sg-xxxxxx"
        error ""
        error "4. Run Pulumi destroy with proper credentials:"
        error "   pulumi destroy --stack hipaa-dev --yes"
        return 1
    fi
    
    # Fix security group dependencies first
    if ! fix_security_group_dependencies; then
        warn "Security group dependency fix failed, proceeding with manual cleanup approach"
    fi
    
    # Clean up Pulumi resources
    if ! cleanup_pulumi; then
        warn "Pulumi cleanup failed, attempting AWS resource cleanup"
    fi
    
    # Clean up any remaining AWS resources
    cleanup_aws_resources
    
    # Wait for completion
    wait_for_completion
    
    log "=== CLEANUP COMPLETED ==="
    log "All HIPAA infrastructure resources have been cleaned up."
    log ""
    log "To verify cleanup:"
    log "  aws rds describe-db-instances"
    log "  aws ec2 describe-security-groups --filters 'Name=group-name,Values=hipaa-*'"
    log "  aws ec2 describe-vpcs --filters 'Name=tag:Name,Values=HIPAA-VPC'"
}

# Handle script interruption
trap 'error "Script interrupted"; exit 130' INT TERM

# Run main function
main "$@"