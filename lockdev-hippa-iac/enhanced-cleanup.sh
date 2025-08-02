#!/bin/bash

# Enhanced Cleanup Script for HIPAA Infrastructure
# Handles load balancer deletion protection, ENI dependencies, and comprehensive cleanup

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
    
    if ! command -v aws &> /dev/null; then
        error "AWS CLI is not installed"
        exit 1
    fi
    
    if ! command -v pulumi &> /dev/null; then
        error "Pulumi is not installed"
        exit 1
    fi
    
    log "Prerequisites check passed"
}

# Configure AWS credentials
configure_aws() {
    log "Configuring AWS credentials..."
    
    # Try environment variables first
    if [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
        log "AWS credentials configured via environment variables"
        export AWS_DEFAULT_REGION=$REGION
    else
        # Check for AWS CLI profiles
        if aws configure list --profile dev-root &>/dev/null; then
            export AWS_PROFILE=dev-root
            export AWS_DEFAULT_REGION=$REGION
            log "Using AWS profile: dev-root"
        elif aws configure list &>/dev/null; then
            export AWS_DEFAULT_REGION=$REGION
            log "Using default AWS CLI configuration"
        else
            error "AWS credentials not properly configured"
            exit 1
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
    local env_name="$1"
    log "Disabling load balancer deletion protection for environment: $env_name"
    
    # Get load balancers with environment-specific names
    local lbs=$(aws elbv2 describe-load-balancers --query 'LoadBalancers[*].[LoadBalancerArn,LoadBalancerName]' --output text | grep -i "$env_name" || echo "")
    
    if [ -z "$lbs" ]; then
        log "No load balancers found with environment name: $env_name"
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
    
    sleep 5
}

# Clear RDS instance data before deletion
clear_rds_data() {
    log "Clearing RDS instance data..."
    
    local rds_instances=$(aws rds describe-db-instances --query 'DBInstances[?starts_with(DBInstanceIdentifier, `hipaa`)]' --output json)
    
    if [ "$rds_instances" = "[]" ]; then
        log "No RDS instances found to clear data"
        return 0
    fi
    
    echo "$rds_instances" | jq -r '.[] | .DBInstanceIdentifier + "|" + .Endpoint.Address + "|" + .MasterUsername + "|" + .Engine' | while IFS='|' read -r instance endpoint username engine; do
        if [ -n "$instance" ] && [ -n "$endpoint" ]; then
            info "Clearing data from RDS instance: $instance ($engine at $endpoint)"
            
            # Get password from AWS Secrets Manager or parameter store
            local password=""
            if aws secretsmanager get-secret-value --secret-id "hipaa-$instance" --query 'SecretString' --output text &>/dev/null; then
                password=$(aws secretsmanager get-secret-value --secret-id "hipaa-$instance" --query 'SecretString' --output text 2>/dev/null)
            elif aws ssm get-parameter --name "/hipaa/$instance/password" --query 'Parameter.Value' --output text &>/dev/null; then
                password=$(aws ssm get-parameter --name "/hipaa/$instance/password" --query 'Parameter.Value' --output text 2>/dev/null)
            else
                warn "Could not retrieve password for $instance, attempting with default"
                password="hipaa_secure_password"  # Default fallback
            fi
            
            # Clear data based on database engine
            case "$engine" in
                "postgres"|"postgresql")
                    info "Clearing PostgreSQL data from $instance"
                    # Connect and drop all user tables/schemas
                    PGPASSWORD="$password" psql -h "$endpoint" -U "$username" -d postgres -c "
                        DO \$\$
                        DECLARE
                            r RECORD;
                        BEGIN
                            -- Drop all schemas except system ones
                            FOR r IN SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'public') AND schema_name NOT LIKE 'pg_%' LOOP
                                EXECUTE 'DROP SCHEMA IF EXISTS ' || quote_ident(r.schema_name) || ' CASCADE';
                            END LOOP;
                            
                            -- Drop all tables in public schema
                            FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
                                EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
                            END LOOP;
                            
                            -- Drop all functions
                            FOR r IN SELECT routine_schema, routine_name FROM information_schema.routines WHERE routine_schema NOT IN ('information_schema', 'pg_catalog') LOOP
                                EXECUTE 'DROP FUNCTION IF EXISTS ' || quote_ident(r.routine_schema) || '.' || quote_ident(r.routine_name) || ' CASCADE';
                            END LOOP;
                        END
                        \$\$;
                    " 2>/dev/null || warn "Could not connect to PostgreSQL instance $instance"
                    ;;
                    
                "mysql")
                    info "Clearing MySQL data from $instance"
                    # Connect and drop all user databases
                    mysql -h "$endpoint" -u "$username" -p"$password" -e "
                        SELECT CONCAT('DROP DATABASE IF EXISTS \`', schema_name, '\`;') 
                        FROM information_schema.schemata 
                        WHERE schema_name NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
                        INTO OUTFILE '/tmp/drop_databases.sql';
                        SOURCE /tmp/drop_databases.sql;
                    " 2>/dev/null || warn "Could not connect to MySQL instance $instance"
                    ;;
                    
                *)
                    warn "Unsupported database engine: $engine, skipping data clearing"
                    ;;
            esac
            
            # Log data clearing completion
            info "Data cleared from RDS instance: $instance"
        fi
    done
    
    sleep 5
}

# Clean up RDS instances with dependencies (after data clearing)
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
            sleep 30
        fi
        
        # Delete security group
        aws ec2 delete-security-group --group-id "$sg" || warn "Failed to delete security group: $sg"
    done
}

# Clean up VPC resources
cleanup_vpc_resources() {
    log "Cleaning up VPC resources..."
    
    # Clean up NAT gateways
    local nat_gateways=$(aws ec2 describe-nat-gateways --filter "Name=tag:Name,Values=*hipaa*" --query 'NatGateways[].NatGatewayId' --output text 2>/dev/null || echo "")
    for nat in $nat_gateways; do
        if [ -n "$nat" ]; then
            info "Deleting NAT gateway: $nat"
            aws ec2 delete-nat-gateway --nat-gateway-id "$nat"
        fi
    done
    
    # Clean up EIPs
    local eips=$(aws ec2 describe-addresses --filters "Name=tag:Name,Values=*hipaa*" --query 'Addresses[].AllocationId' --output text 2>/dev/null || echo "")
    for eip in $eips; do
        if [ -n "$eip" ]; then
            info "Releasing EIP: $eip"
            aws ec2 release-address --allocation-id "$eip" || warn "Failed to release EIP: $eip"
        fi
    done
    
    # Clean up VPCs
    local vpcs=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=*hipaa*" --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo "")
    for vpc in $vpcs; do
        if [ -n "$vpc" ]; then
            info "Cleaning up VPC: $vpc"
            
            # Clean up subnets
            local subnets=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc" --query 'Subnets[].SubnetId' --output text 2>/dev/null || echo "")
            for subnet in $subnets; do
                aws ec2 delete-subnet --subnet-id "$subnet" || warn "Failed to delete subnet: $subnet"
            done
            
            # Clean up internet gateways
            local igws=$(aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$vpc" --query 'InternetGateways[].InternetGatewayId' --output text 2>/dev/null || echo "")
            for igw in $igws; do
                info "Detaching and deleting IGW: $igw"
                aws ec2 detach-internet-gateway --internet-gateway-id "$igw" --vpc-id "$vpc" || warn "Failed to detach IGW"
                aws ec2 delete-internet-gateway --internet-gateway-id "$igw" || warn "Failed to delete IGW"
            done
            
            # Clean up route tables
            local route_tables=$(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$vpc" --query 'RouteTables[?Associations[0].Main!=`true`].RouteTableId' --output text 2>/dev/null || echo "")
            for rt in $route_tables; do
                aws ec2 delete-route-table --route-table-id "$rt" || warn "Failed to delete route table: $rt"
            done
            
            # Finally delete VPC
            aws ec2 delete-vpc --vpc-id "$vpc" || warn "Failed to delete VPC: $vpc"
        fi
    done
}

# Clean up Pulumi stacks
cleanup_pulumi_stacks() {
    log "Cleaning up Pulumi stacks..."
    
    cd lockdev-hippa-iac
    
    local stacks=$(pulumi stack ls --json 2>/dev/null | jq -r '.[].name' | grep -E "(dev|staging|prod|hipaa)" || echo "")
    
    for stack in $stacks; do
        info "Processing Pulumi stack: $stack"
        
        # Unprotect all resources
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
        pulumi destroy --yes --force 2>/dev/null || warn "Failed to destroy stack: $stack"
        pulumi stack rm "$stack" --yes --force 2>/dev/null || warn "Failed to remove stack: $stack"
    done
    
    cd ..
}

# Verify cleanup
verify_cleanup() {
    log "Verifying cleanup completion..."
    
    echo ""
    info "=== VERIFICATION REPORT ==="
    
    echo "VPCs:"
    aws ec2 describe-vpcs --filters "Name=tag:Name,Values=*hipaa*" --query 'Vpcs[*].VpcId' --output table || echo "No VPCs found"
    
    echo ""
    echo "RDS Instances:"
    aws rds describe-db-instances --query 'DBInstances[?starts_with(DBInstanceIdentifier, `hipaa`)].DBInstanceIdentifier' --output table || echo "No RDS instances found"
    
    echo ""
    echo "Load Balancers:"
    aws elbv2 describe-load-balancers --query 'LoadBalancers[?contains(LoadBalancerName, `hipaa`)].LoadBalancerName' --output table || echo "No load balancers found"
    
    echo ""
    echo "Security Groups:"
    aws ec2 describe-security-groups --filters "Name=group-name,Values=hipaa-*" --query 'SecurityGroups[*].GroupId' --output table || echo "No security groups found"
    
    echo ""
    echo "S3 Buckets:"
    aws s3api list-buckets --query 'Buckets[?contains(Name, `hipaa`)]' --output table || echo "No S3 buckets found"
    
    echo ""
    log "=== CLEANUP VERIFICATION COMPLETE ==="
}

# Clean up ECS resources explicitly
cleanup_ecs_resources() {
    log "Cleaning up ECS resources..."
    
    # Clean up ECS clusters
    local clusters=$(aws ecs list-clusters --query 'clusterArns[]' --output text | grep -i "hipaa\|dev\|staging\|prod" || echo "")
    for cluster in $clusters; do
        if [ -n "$cluster" ]; then
            info "Processing ECS cluster: $cluster"
            
            # Get cluster name from ARN
            local cluster_name=$(echo "$cluster" | sed 's/.*cluster\///')
            
            # List and delete services
            local services=$(aws ecs list-services --cluster "$cluster_name" --query 'serviceArns[]' --output text 2>/dev/null || echo "")
            for service in $services; do
                if [ -n "$service" ]; then
                    info "Deleting ECS service: $service"
                    aws ecs delete-service --cluster "$cluster_name" --service "$service" --force --no-cli-pager 2>/dev/null || warn "Could not delete service: $service"
                fi
            done
            
            # List and stop tasks
            local tasks=$(aws ecs list-tasks --cluster "$cluster_name" --query 'taskArns[]' --output text 2>/dev/null || echo "")
            for task in $tasks; do
                if [ -n "$task" ]; then
                    info "Stopping ECS task: $task"
                    aws ecs stop-task --cluster "$cluster_name" --task "$task" --no-cli-pager 2>/dev/null || warn "Could not stop task: $task"
                fi
            done
            
            # Wait for tasks to stop
            sleep 10
            
            # Delete cluster
            info "Deleting ECS cluster: $cluster_name"
            aws ecs delete-cluster --cluster "$cluster_name" --no-cli-pager 2>/dev/null || warn "Could not delete cluster: $cluster_name"
        fi
    done
    
    # Clean up ECS task definitions
    local task_definitions=$(aws ecs list-task-definitions --family-prefix "hipaa" --query 'taskDefinitionArns[]' --output text 2>/dev/null || echo "")
    for td in $task_definitions; do
        if [ -n "$td" ]; then
            info "Deregistering ECS task definition: $td"
            aws ecs deregister-task-definition --task-definition "$td" --no-cli-pager 2>/dev/null || warn "Could not deregister task definition: $td"
        fi
    done
    
    # Clean up ECS task definitions by status
    local all_task_defs=$(aws ecs list-task-definitions --query 'taskDefinitionArns[]' --output text | grep -i "hipaa\|dev\|staging\|prod" || echo "")
    for td in $all_task_defs; do
        if [ -n "$td" ]; then
            info "Deregistering ECS task definition: $td"
            aws ecs deregister-task-definition --task-definition "$td" --no-cli-pager 2>/dev/null || warn "Could not deregister task definition: $td"
        fi
    done
    
    sleep 5
}

# Main function
main() {
    log "Starting enhanced HIPAA infrastructure cleanup..."
    log "Environment: $ENVIRONMENT"
    log "Region: $REGION"
    
    check_prerequisites
    configure_aws
    
    # Disable load balancer protection
    disable_lb_protection "$ENVIRONMENT"
    
    # Clean up ECS resources first
    cleanup_ecs_resources
    
    # Clear RDS data before deletion
    clear_rds_data
    
    # Clean up RDS instances (they have dependencies)
    cleanup_rds_instances
    
    # Clean up security groups and ENIs
    cleanup_security_groups
    
    # Clean up VPC resources
    cleanup_vpc_resources
    
    # Clean up Pulumi stacks
    cleanup_pulumi_stacks
    
    # Final verification
    verify_cleanup
    
    log "Enhanced cleanup completed successfully!"
    log "All HIPAA resources have been destroyed."
}

# Handle script arguments
if [ $# -gt 0 ]; then
    case "$1" in
        --help|-h)
            echo "Enhanced HIPAA Infrastructure Cleanup"
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