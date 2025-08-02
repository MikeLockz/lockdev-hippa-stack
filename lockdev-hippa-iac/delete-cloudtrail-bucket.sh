#!/bin/bash

# Specialized CloudTrail bucket deletion script
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

export AWS_PROFILE=dev-root
export AWS_DEFAULT_REGION=us-east-1

log "Starting CloudTrail bucket deletion..."

# Find and delete CloudTrail buckets
BUCKETS=$(aws s3api list-buckets --query 'Buckets[?contains(Name, `cloudtrail`) || contains(Name, `hipaa`)]' --output json | jq -r '.[].Name')

for bucket in $BUCKETS; do
    if [ -n "$bucket" ]; then
        log "Processing CloudTrail bucket: $bucket"
        
        # Check if bucket exists
        if aws s3api head-bucket --bucket "$bucket" 2>/dev/null; then
            log "Bucket exists, proceeding with deletion..."
            
            # Disable CloudTrail first
            log "Disabling CloudTrail logging..."
            aws cloudtrail describe-trails --query 'trailList[?S3BucketName==`'$bucket'`]' --output json | jq -r '.[].Name' | while read trail; do
                if [ -n "$trail" ]; then
                    log "Stopping CloudTrail: $trail"
                    aws cloudtrail stop-logging --name "$trail" 2>/dev/null || true
                    aws cloudtrail delete-trail --name "$trail" 2>/dev/null || true
                fi
            done
            
            # Suspend versioning
            log "Suspending versioning..."
            aws s3api put-bucket-versioning --bucket "$bucket" --versioning-configuration Status=Suspended 2>/dev/null || true
            
            # Delete all objects and versions
            log "Deleting all objects and versions..."
            
            # Create a lifecycle policy to delete all objects
            aws s3api put-bucket-lifecycle-configuration --bucket "$bucket" --lifecycle-configuration '{
                "Rules": [{
                    "ID": "DeleteAllObjects",
                    "Status": "Enabled",
                    "Prefix": "",
                    "Expiration": {"Days": 1},
                    "NoncurrentVersionExpiration": {"NoncurrentDays": 1}
                }]
            }' 2>/dev/null || true
            
            # Force delete everything
            log "Force deleting all objects..."
            
            # Delete all versions
            while true; do
                VERSIONS=$(aws s3api list-object-versions --bucket "$bucket" --max-keys 1000 --output json 2>/dev/null || echo '{"Versions": [], "DeleteMarkers": []}')
                OBJECT_COUNT=$(echo "$VERSIONS" | jq '[.Versions[], .DeleteMarkers[]] | length')
                
                if [ "$OBJECT_COUNT" -eq 0 ]; then
                    break
                fi
                
                log "Deleting $OBJECT_COUNT objects..."
                
                # Delete in batches
                echo "$VERSIONS" | jq -r '[.Versions[], .DeleteMarkers[]] | map({Key: .Key, VersionId: .VersionId}) | .[0:1000] | @json' | while read batch; do
                    if [ "$batch" != "[]" ] && [ "$batch" != "null" ]; then
                        aws s3api delete-objects --bucket "$bucket" --delete "{\"Objects\": $batch}" --no-cli-pager 2>/dev/null || true
                    fi
                done
                
                sleep 2
            done
            
            # Final deletion
            log "Final bucket deletion..."
            aws s3 rb "s3://$bucket" --force --no-cli-pager 2>/dev/null || \
            aws s3api delete-bucket --bucket "$bucket" --no-cli-pager 2>/dev/null || \
            error "Could not delete bucket: $bucket"
            
            log "Successfully deleted bucket: $bucket"
        else
            warn "Bucket $bucket does not exist"
        fi
    done

log "CloudTrail bucket deletion completed"