#!/bin/bash

# Final comprehensive cleanup script
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

export AWS_PROFILE=dev-root
export AWS_DEFAULT_REGION=us-east-1

log "Starting final comprehensive cleanup..."

# Delete all CloudTrail buckets
BUCKETS=$(aws s3api list-buckets --query 'Buckets[?contains(Name, `cloudtrail`) || contains(Name, `hipaa`)]' --output json)

# Check if we have buckets to clean
HAS_BUCKETS=$(echo "$BUCKETS" | jq -r '. | length')

if [ "$HAS_BUCKETS" -gt 0 ]; then
    log "Found buckets to clean..."
    echo "$BUCKETS" | jq -r '.[].Name' | while read bucket; do
        log "Processing bucket: $bucket"
        
        # List all objects and versions
        log "Listing objects in $bucket..."
        
        # Empty the bucket completely
        log "Emptying bucket: $bucket"
        aws s3 rm "s3://$bucket" --recursive --quiet || warn "Could not empty bucket with s3 rm"
        
        # Delete all versions
        log "Deleting all versions in $bucket..."
        aws s3api delete-objects --bucket "$bucket" --delete "$(aws s3api list-object-versions --bucket "$bucket" --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' --output json 2>/dev/null || echo '{"Objects":[]}')" --no-cli-pager 2>/dev/null || true
        
        # Delete all delete markers
        log "Deleting all delete markers in $bucket..."
        aws s3api delete-objects --bucket "$bucket" --delete "$(aws s3api list-object-versions --bucket "$bucket" --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' --output json 2>/dev/null || echo '{"Objects":[]}')" --no-cli-pager 2>/dev/null || true
        
        # Final empty check
        OBJECTS=$(aws s3api list-objects-v2 --bucket "$bucket" --max-keys 1 --query 'KeyCount' --output text 2>/dev/null || echo "0")
        if [ "$OBJECTS" = "0" ]; then
            log "Bucket $bucket is now empty, deleting..."
            aws s3 rb "s3://$bucket" --force --no-cli-pager || warn "Could not delete bucket: $bucket"
        else
            warn "Bucket $bucket still has objects"
        fi
    done
else
    log "No buckets found to clean"
fi

# Final verification
log "=== FINAL VERIFICATION ==="
echo "Pulumi stacks:"
pulumi stack ls || echo "No stacks found"

echo ""
echo "AWS Resources:"
echo "RDS instances: $(aws rds describe-db-instances --query 'DBInstances[?starts_with(DBInstanceIdentifier, `hipaa`)]' --output json 2>/dev/null | jq length)"
echo "Load balancers: $(aws elbv2 describe-load-balancers --query 'length(LoadBalancers[?contains(LoadBalancerName, `hipaa`)])' --output text 2>/dev/null || echo 0)"
echo "Security groups: $(aws ec2 describe-security-groups --filters "Name=group-name,Values=hipaa-*" --query 'length(SecurityGroups[])' --output text 2>/dev/null || echo 0)"
echo "S3 buckets: $(aws s3api list-buckets --query 'Buckets[?contains(Name, `hipaa`)]' --output json 2>/dev/null | jq length)"
echo "VPCs: $(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=*hipaa*" --query 'length(Vpcs[])' --output text 2>/dev/null || echo 0)"

log "=== CLEANUP COMPLETE ==="