#!/bin/bash

# HIPAA Infrastructure Cleanup - Unified Script
# Replaces: comprehensive-cleanup.sh, enhanced-cleanup.sh, force-cleanup.sh,
#           final-cleanup.sh, smart-cleanup.sh
#
# Usage: ./hipaa-cleanup.sh [environment] [options]

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${SCRIPT_DIR}/../config"
LIB_DIR="${SCRIPT_DIR}/../scripts/lib"
PHASES_DIR="${SCRIPT_DIR}/../scripts/phases"

# Default configuration
ENVIRONMENT="${1:-dev}"
FORCE_MODE="false"
DRY_RUN="false"
VERIFY="false"
PHASE="all"
SKIP_VERIFICATION="false"
ROLLBACK=""
CONFIG_FILE=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Logging functions
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

phase() {
    echo -e "${PURPLE}[$(date +'%Y-%m-%d %H:%M:%S')] PHASE: $1${NC}"
}

# Source utility functions
source "${LIB_DIR}/utils.sh" 2>/dev/null || {
    echo "Error: Could not load utility functions"
    exit 1
}

# Parse command line arguments
parse_args() {
    shift # Remove environment argument
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force)
                FORCE_MODE="true"
                shift
                ;;
            --dry-run)
                DRY_RUN="true"
                shift
                ;;
            --verify)
                VERIFY="true"
                shift
                ;;
            --phase=*)
                PHASE="${1#*=}"
                shift
                ;;
            --skip-verification)
                SKIP_VERIFICATION="true"
                shift
                ;;
            --rollback=*)
                ROLLBACK="${1#*=}"
                shift
                ;;
            --config=*)
                CONFIG_FILE="${1#*=}"
                shift
                ;;
            --legacy-support)
                # Handle legacy script compatibility
                legacy_support "$@"
                exit 0
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Show help information
show_help() {
    cat << EOF
HIPAA Infrastructure Cleanup - Unified Script

USAGE:
    ./hipaa-cleanup.sh [environment] [options]

ENVIRONMENTS:
    dev         Development environment (default)
    staging     Staging environment
    prod        Production environment

OPTIONS:
    --phase=PHASE           Execute specific phase [prepare|data|resources|vpc|verify|all]
    --force                 Skip all confirmations (dangerous)
    --dry-run               Show what would be done without executing
    --verify                Run verification after cleanup
    --skip-verification     Skip verification steps
    --rollback=TIMESTAMP    Rollback to previous state
    --config=FILE           Use custom configuration file
    --legacy-support        Enable legacy script compatibility
    --help, -h              Show this help message

PHASES:
    prepare     Pre-cleanup preparation (disable protections, snapshots)
    data        Clear sensitive data (RDS, S3 objects)
    resources   Delete AWS resources (ALB, ECS, RDS instances)
    vpc         Clean up VPC and networking resources
    verify      Verify cleanup completion
    all         Execute all phases in sequence

EXAMPLES:
    ./hipaa-cleanup.sh dev --phase=all --verify
    ./hipaa-cleanup.sh staging --phase=data --dry-run
    ./hipaa-cleanup.sh prod --force --skip-verification
    ./hipaa-cleanup.sh dev --rollback=20240101-120000

LEGACY COMPATIBILITY:
    make cleanup-dev          # Same as: ./hipaa-cleanup.sh dev
    make cleanup-staging      # Same as: ./hipaa-cleanup.sh staging
    make cleanup-prod         # Same as: ./hipaa-cleanup.sh prod

EOF
}

# Legacy script compatibility
legacy_support() {
    local legacy_script="$1"
    case "$legacy_script" in
        "comprehensive-cleanup.sh")
            info "Legacy comprehensive cleanup detected"
            PHASE="all"
            VERIFY="true"
            ;;
        "enhanced-cleanup.sh")
            info "Legacy enhanced cleanup detected"
            PHASE="all"
            VERIFY="true"
            ;;
        "force-cleanup.sh")
            info "Legacy force cleanup detected"
            PHASE="all"
            FORCE_MODE="true"
            ;;
        "final-cleanup.sh")
            info "Legacy final cleanup detected"
            PHASE="data"
            VERIFY="true"
            ;;
        "smart-cleanup.sh")
            info "Legacy smart cleanup detected"
            PHASE="all"
            VERIFY="true"
            ;;
    esac
}

# Validate environment
validate_environment() {
    case "$ENVIRONMENT" in
        dev|staging|prod)
            info "Environment validated: $ENVIRONMENT"
            ;;
        *)
            error "Invalid environment: $ENVIRONMENT"
            error "Valid environments: dev, staging, prod"
            exit 1
            ;;
    esac
}

# Load configuration
load_config() {
    local config_file="${CONFIG_FILE:-${CONFIG_DIR}/environments.yaml}"
    
    if [[ -f "$config_file" ]]; then
        info "Loading configuration from: $config_file"
        # Source configuration (simplified YAML parsing)
        export ENVIRONMENT="$ENVIRONMENT"
        export FORCE_MODE="$FORCE_MODE"
        export DRY_RUN="$DRY_RUN"
        export VERIFY="$VERIFY"
    else
        warn "Configuration file not found, using defaults"
    fi
}

# Create state backup
create_backup() {
    local timestamp=$(date +"%Y%m%d-%H%M%S")
    local backup_dir="${SCRIPT_DIR}/../backups/cleanup-${timestamp}"
    
    mkdir -p "$backup_dir"
    
    # Backup current state
    {
        echo "# Cleanup State Backup - $(date)"
        echo "Environment: $ENVIRONMENT"
        echo "Phase: $PHASE"
        echo "Dry Run: $DRY_RUN"
        echo ""
        echo "# AWS Resources"
        aws sts get-caller-identity --output json 2>/dev/null || echo "AWS not configured"
        aws ec2 describe-vpcs --filters "Name=tag:Name,Values=*hipaa*" --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo "No VPCs found"
        aws rds describe-db-instances --query 'DBInstances[?starts_with(DBInstanceIdentifier, `hipaa`)].DBInstanceIdentifier' --output text 2>/dev/null || echo "No RDS instances"
    } > "$backup_dir/state-backup.txt"
    
    echo "$timestamp" > "$backup_dir/timestamp"
    info "State backup created: $backup_dir"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        info "DRY RUN: Backup would be created at: $backup_dir"
    fi
}

# Execute cleanup phases
execute_phases() {
    local phases_to_run=()
    
    case "$PHASE" in
        prepare)
            phases_to_run=("prepare")
            ;;
        data)
            phases_to_run=("prepare" "data")
            ;;
        resources)
            phases_to_run=("prepare" "data" "resources")
            ;;
        vpc)
            phases_to_run=("prepare" "data" "resources" "vpc")
            ;;
        verify)
            phases_to_run=("verify")
            ;;
        all)
            phases_to_run=("prepare" "data" "resources" "vpc" "verify")
            ;;
        *)
            error "Invalid phase: $PHASE"
            exit 1
            ;;
    esac
    
    for phase in "${phases_to_run[@]}"; do
        phase "Starting $phase phase"
        
        if [[ "$DRY_RUN" == "true" ]]; then
            info "DRY RUN: Would execute $phase phase"
        else
            if [[ -f "$PHASES_DIR/phase-${phase}.sh" ]]; then
                source "$PHASES_DIR/phase-${phase}.sh"
                execute_phase_$phase
            else
                error "Phase script not found: $PHASES_DIR/phase-${phase}.sh"
                exit 1
            fi
        fi
        
        log "Completed $phase phase"
    done
}

# Main execution
main() {
    log "Starting HIPAA infrastructure cleanup"
    log "Environment: $ENVIRONMENT"
    log "Phase: $PHASE"
    log "Dry Run: $DRY_RUN"
    
    # Parse arguments
    parse_args "$@"
    
    # Validate environment
    validate_environment
    
    # Load configuration
    load_config
    
    # Create backup
    create_backup
    
    # Execute phases
    execute_phases
    
    # Final verification
    if [[ "$VERIFY" == "true" && "$SKIP_VERIFICATION" != "true" ]]; then
        phase "Final verification"
        if [[ -f "$PHASES_DIR/phase-verify.sh" ]]; then
            source "$PHASES_DIR/phase-verify.sh"
            execute_phase_verify
        fi
    fi
    
    log "Cleanup completed successfully"
    
    # Show next steps
    cat << EOF

=== NEXT STEPS ===
- Verify cleanup: ./hipaa-cleanup.sh $ENVIRONMENT --phase=verify
- Check AWS Console for any remaining resources
- Review logs in: ${SCRIPT_DIR}/../logs/

EOF
}

# Handle script interruption
trap 'error "Script interrupted by user"; exit 130' INT TERM

# Run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi