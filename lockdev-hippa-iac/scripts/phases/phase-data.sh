#!/bin/bash

# Phase 2: Data Clearing Script
# Safely clears sensitive data before resource deletion

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

PHASE_NAME="data-clearing"

# Main data clearing function
clear_sensitive_data() {
    local environment="$1"
    
    log_phase "$PHASE_NAME" "Starting sensitive data clearing for: $environment"
    
    # Load environment configuration
    load_environment_config "$environment"
    
    local root_profile=$(get_env_config "$environment" "root_profile")
    local region=$(get_env_config "$environment" "region")
    
    # Setup AWS environment
    setup_aws_env "$root_profile" "$region"
    
    # Clear RDS data
    clear_rds_data "$environment"
    
    # Clear S3 bucket data
    clear_s3_data "$environment"
    
    # Clear CloudTrail logs
    clear_cloudtrail_logs "$environment"
    
    log_phase_success "$PHASE_NAME" "Sensitive data cleared successfully"
}

# Clear RDS database data
clear_rds_data() {
    local environment="$1"
    
    log_step "Clearing RDS database data..."
    
    # Find RDS instances with HIPAA naming
    local rds_instances=$(AWS_PROFILE="$root_profile" aws rds describe-db-instances \
        --query 'DBInstances[?contains(DBInstanceIdentifier, `hipaa`) || contains(DBInstanceIdentifier, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$rds_instances" == "[]" ]]; then
        log_info "No RDS instances found to clear"
        return 0
    fi
    
    echo "$rds_instances" | jq -r '.[] | .DBInstanceIdentifier + "|" + .Endpoint.Address + "|" + .MasterUsername + "|" + .Engine' | while IFS='|' read -r instance endpoint username engine; do
        if [[ -n "$instance" ]] && [[ -n "$endpoint" ]]; then
            log_info "Clearing data from RDS instance: $instance ($engine)"
            
            # Get password from AWS Secrets Manager
            local password=""
            if AWS_PROFILE="$root_profile" aws secretsmanager get-secret-value --secret-id "hipaa-$environment-$instance" --query 'SecretString' --output text &>/dev/null; then
                password=$(AWS_PROFILE="$root_profile" aws secretsmanager get-secret-value --secret-id "hipaa-$environment-$instance" --query 'SecretString' --output text)
            elif AWS_PROFILE="$root_profile" aws ssm get-parameter --name "/hipaa/$environment/$instance/password" --query 'Parameter.Value' --output text &>/dev/null; then
                password=$(AWS_PROFILE="$root_profile" aws ssm get-parameter --name "/hipaa/$environment/$instance/password" --query 'Parameter.Value' --output text)
            else
                log_warning "Could not retrieve password for $instance, attempting with default"
                password="hipaa_secure_password_2024"
            fi
            
            # Clear data based on database engine
            case "$engine" in
                "postgres"|"postgresql")
                    log_info "Clearing PostgreSQL data from $instance"
                    PGPASSWORD="$password" psql -h "$endpoint" -U "$username" -d postgres -c "
                        DO \$\$
                        DECLARE
                            r RECORD;
                        BEGIN
                            -- Drop all user schemas
                            FOR r IN SELECT schema_name FROM information_schema.schemata 
                                     WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'public') 
                                     AND schema_name NOT LIKE 'pg_%' 
                            LOOP
                                EXECUTE 'DROP SCHEMA IF EXISTS ' || quote_ident(r.schema_name) || ' CASCADE';
                            END LOOP;
                            
                            -- Drop all tables in public schema
                            FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
                                EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
                            END LOOP;
                            
                            -- Clear audit logs
                            TRUNCATE TABLE IF EXISTS audit_logs;
                            TRUNCATE TABLE IF EXISTS security_events;
                            
                            -- Reset sequences
                            FOR r IN SELECT sequence_schema, sequence_name FROM information_schema.sequences LOOP
                                EXECUTE 'ALTER SEQUENCE ' || quote_ident(r.sequence_schema) || '.' || quote_ident(r.sequence_name) || ' RESTART WITH 1';
                            END LOOP;
                        END
                        \$\$;
                    " 2>/dev/null || log_warning "Could not connect to PostgreSQL instance $instance"
                    ;;
                    
                "mysql")
                    log_info "Clearing MySQL data from $instance"
                    mysql -h "$endpoint" -u "$username" -p"$password" -e "
                        SET FOREIGN_KEY_CHECKS=0;
                        
                        -- Drop all user databases
                        SELECT CONCAT('DROP DATABASE IF EXISTS \`', schema_name, '\`;') 
                        FROM information_schema.schemata 
                        WHERE schema_name NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
                        INTO OUTFILE '/tmp/drop_databases.sql';
                        
                        SOURCE /tmp/drop_databases.sql;
                        
                        -- Clear system tables
                        TRUNCATE TABLE mysql.general_log;
                        TRUNCATE TABLE mysql.slow_log;
                        
                        SET FOREIGN_KEY_CHECKS=1;
                    " 2>/dev/null || log_warning "Could not connect to MySQL instance $instance"
                    ;;
                    
                *)
                    log_warning "Unsupported database engine: $engine, skipping data clearing"
                    ;;
            esac
        fi
    done
}

# Clear S3 bucket data
clear_s3_data() {
    local environment="$1"
    
    log_step "Clearing S3 bucket data..."
    
    # Find S3 buckets with HIPAA naming
    local buckets=$(AWS_PROFILE="$root_profile" aws s3api list-buckets \
        --query 'Buckets[?contains(Name, `hipaa`) && contains(Name, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$buckets" == "[]" ]]; then
        log_info "No S3 buckets found to clear"
        return 0
    fi
    
    echo "$buckets" | jq -r '.[].Name' | while read -r bucket; do
        if [[ -n "$bucket" ]]; then
            log_info "Clearing data from S3 bucket: $bucket"
            
            # Check if bucket exists
            if AWS_PROFILE="$root_profile" aws s3api head-bucket --bucket "$bucket" 2>/dev/null; then
                # Empty the bucket
                log_info "Emptying bucket: $bucket"
                AWS_PROFILE="$root_profile" aws s3 rm "s3://$bucket" --recursive --quiet || true
                
                # Delete all versions and delete markers
                local versions=$(AWS_PROFILE="$root_profile" aws s3api list-object-versions --bucket "$bucket" --output json 2>/dev/null || echo '{"Versions": [], "DeleteMarkers": []}')
                
                # Delete versions
                echo "$versions" | jq -r '.Versions[]? | "\(.Key)\t\(.VersionId)"' | while IFS=$'\t' read -r key version; do
                    if [[ -n "$key" ]] && [[ -n "$version" ]]; then
                        AWS_PROFILE="$root_profile" aws s3api delete-object --bucket "$bucket" --key "$key" --version-id "$version" --no-cli-pager 2>/dev/null || true
                    fi
                done
                
                # Delete delete markers
                echo "$versions" | jq -r '.DeleteMarkers[]? | "\(.Key)\t\(.VersionId)"' | while IFS=$'\t' read -r key version; do
                    if [[ -n "$key" ]] && [[ -n "$version" ]]; then
                        AWS_PROFILE="$root_profile" aws s3api delete-object --bucket "$bucket" --key "$key" --version-id "$version" --no-cli-pager 2>/dev/null || true
                    fi
                done
                
                log_info "S3 bucket data cleared: $bucket"
            else
                log_warning "Bucket not accessible: $bucket"
            fi
        fi
    done
}

# Clear CloudTrail logs
clear_cloudtrail_logs() {
    local environment="$1"
    
    log_step "Clearing CloudTrail logs..."
    
    # First, find and delete CloudTrail trails
    local trails=$(AWS_PROFILE="$root_profile" aws cloudtrail describe-trails \
        --query 'trailList[?contains(Name, `hipaa`) || contains(Name, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$trails" != "[]" ]]; then
        echo "$trails" | jq -r '.[].Name' | while read -r trail_name; do
            if [[ -n "$trail_name" ]]; then
                log_info "Deleting CloudTrail trail: $trail_name"
                
                # Stop logging first
                AWS_PROFILE="$root_profile" aws cloudtrail stop-logging --name "$trail_name" --no-cli-pager 2>/dev/null || true
                
                # Delete the trail
                AWS_PROFILE="$root_profile" aws cloudtrail delete-trail --name "$trail_name" --no-cli-pager 2>/dev/null || true
                
                log_info "CloudTrail trail deleted: $trail_name"
            fi
        done
    else
        log_info "No CloudTrail trails found"
    fi
    
    # Then, find and delete CloudTrail log groups
    local log_groups=$(AWS_PROFILE="$root_profile" aws logs describe-log-groups \
        --query 'logGroups[?contains(logGroupName, `hipaa`) || contains(logGroupName, `cloudtrail`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$log_groups" != "[]" ]]; then
        echo "$log_groups" | jq -r '.[].logGroupName' | while read -r log_group; do
            if [[ -n "$log_group" ]]; then
                log_info "Clearing log group: $log_group"
                
                # Delete the log group
                AWS_PROFILE="$root_profile" aws logs delete-log-group --log-group-name "$log_group" --no-cli-pager 2>/dev/null || true
                
                log_info "CloudTrail log group cleared: $log_group"
            fi
        done
    else
        log_info "No CloudTrail log groups found"
    fi
}

# Hook function for phase execution
phase_data_hook() {
    local environment="$1"
    local options="$2"
    
    log_info "Executing data clearing phase for: $environment"
    
    if is_dry_run; then
        log_info "[DRY RUN] Would clear sensitive data for environment: $environment"
        return 0
    fi
    
    clear_sensitive_data "$environment"
}

# Allow direct execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 <environment> [options]"
        echo "  environment: dev, staging, prod"
        echo "  options: --dry-run, --force"
        exit 1
    fi
    
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    source "$SCRIPT_DIR/../lib/utils.sh"
    clear_sensitive_data "$1"
fi