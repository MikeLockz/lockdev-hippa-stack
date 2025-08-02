#!/bin/bash

# HIPAA-Compliant Unified Infrastructure Cleanup System
# Single script to replace all legacy cleanup scripts
# Supports dev/staging/prod environments with comprehensive safety features

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Source utilities
source "$SCRIPT_DIR/lib/utils.sh"

# Configuration
PHASES_DIR="$SCRIPT_DIR/phases"
CONFIG_DIR="$PROJECT_DIR/config"
ENVIRONMENTS_FILE="$CONFIG_DIR/environments.yaml"

# Phase definitions
PHASES=("prepare" "data" "resources" "vpc" "verify")

# Help documentation
show_help() {
    cat <<EOF
HIPAA Infrastructure Cleanup System
===================================

Usage: $0 [environment] [options]

Environments:
    dev      Development environment
    staging  Staging environment  
    prod     Production environment

Options:
    --dry-run          Show what would be done without executing
    --force            Skip confirmation prompts
    --phase [phase]    Run specific phase only
    --legacy-support   Enable legacy script compatibility
    --help             Show this help message

Phases:
    prepare   - Backup state and disable protections
    data      - Clear RDS/S3 data and CloudTrail logs
    resources - Cleanup ECS, RDS, ALB, ECR, KMS resources
    vpc       - Cleanup VPC, subnets, security groups, networking
    verify    - Comprehensive cleanup verification

Examples:
    $0 dev                    # Full cleanup with confirmation
    $0 staging --dry-run      # Preview staging cleanup
    $0 prod --force           # Production cleanup without confirmation
    $0 dev --phase resources  # Cleanup only resources phase

Legacy Commands (for backward compatibility):
    make clean-dev            # Uses this unified system
    make clean-staging        # Uses this unified system
    make clean-prod           # Uses this unified system

Safety Features:
    ✓ Dry-run mode for preview
    ✓ State backups before cleanup
    ✓ Protection disable handling
    ✓ Dependency resolution
    ✓ Comprehensive verification
    ✓ Billing impact warnings

EOF
}

# Main cleanup function
run_cleanup() {
    local environment="$1"
    local options="$2"
    local specific_phase="$3"
    
    log_phase "cleanup-start" "Starting HIPAA infrastructure cleanup for: $environment"
    
    # Validate environment
    validate_environment "$environment"
    
    # Load configuration
    load_environment_config "$environment"
    
    # Check if specific phase requested
    if [[ -n "$specific_phase" ]]; then
        log_info "Running specific phase: $specific_phase"
        run_specific_phase "$environment" "$specific_phase" "$options"
        return $?
    fi
    
    # Run all phases
    local success=true
    
    for phase in "${PHASES[@]}"; do
        log_phase "$phase" "Executing phase: $phase"
        
        if ! run_phase "$environment" "$phase" "$options"; then
            log_error "Phase $phase failed"
            success=false
            break
        fi
    done
    
    if $success; then
        log_phase_success "cleanup-complete" "HIPAA infrastructure cleanup completed successfully"
    else
        log_error "HIPAA infrastructure cleanup failed"
        return 1
    fi
}

# Run specific phase
run_phase() {
    local environment="$1"
    local phase="$2"
    local options="$3"
    
    local phase_script="$PHASES_DIR/phase-${phase}.sh"
    
    if [[ ! -f "$phase_script" ]]; then
        log_error "Phase script not found: $phase_script"
        return 1
    fi
    
    # Source the phase script
    source "$phase_script"
    
    # Execute phase hook
    local hook_func="phase_${phase}_hook"
    if declare -f "$hook_func" >/dev/null; then
        "$hook_func" "$environment" "$options"
    else
        log_error "Phase hook not found: $hook_func"
        return 1
    fi
}

# Run specific phase only
run_specific_phase() {
    local environment="$1"
    local phase="$2"
    local options="$3"
    
    if [[ ! " ${PHASES[@]} " =~ " $phase " ]]; then
        log_error "Invalid phase: $phase"
        log_info "Valid phases: ${PHASES[*]}"
        return 1
    fi
    
    run_phase "$environment" "$phase" "$options"
}

# Legacy script compatibility
setup_legacy_compatibility() {
    log_info "Setting up legacy script compatibility..."
    
    # Create symlinks for legacy scripts
    local legacy_scripts=("comprehensive-cleanup.sh" "enhanced-cleanup.sh" "force-cleanup.sh" "final-cleanup.sh" "smart-cleanup.sh")
    
    for script in "${legacy_scripts[@]}"; do
        local legacy_path="$PROJECT_DIR/$script"
        if [[ ! -f "$legacy_path" ]] && [[ ! -L "$legacy_path" ]]; then
            ln -sf "$0" "$legacy_path"
            log_info "Created legacy compatibility: $script"
        fi
    done
}

# Parse command line arguments
parse_arguments() {
    local environment=""
    local options=""
    local specific_phase=""
    local legacy_support=false
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            "dev"|"staging"|"prod")
                environment="$1"
                shift
                ;;
            --dry-run)
                options="$options --dry-run"
                export DRY_RUN=true
                shift
                ;;
            --force)
                options="$options --force"
                export FORCE=true
                shift
                ;;
            --phase)
                specific_phase="$2"
                shift 2
                ;;
            --legacy-support)
                legacy_support=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    if [[ -z "$environment" ]]; then
        log_error "Environment is required"
        show_help
        exit 1
    fi
    
    # Setup legacy support if requested
    if [[ "$legacy_support" == "true" ]]; then
        setup_legacy_compatibility
    fi
    
    # Run cleanup
    run_cleanup "$environment" "$options" "$specific_phase"
}

# Main execution
main() {
    # Check if running as legacy script
    local script_name=$(basename "$0")
    if [[ "$script_name" != "hipaa-cleanup.sh" ]]; then
        # Legacy script execution
        local environment="${1:-dev}"
        shift || true
        
        # Map legacy script names to modern options
        case "$script_name" in
            "comprehensive-cleanup.sh"|"final-cleanup.sh")
                set -- "$environment" --force "$@"
                ;;
            "enhanced-cleanup.sh"|"smart-cleanup.sh")
                set -- "$environment" --legacy-support "$@"
                ;;
            "force-cleanup.sh")
                set -- "$environment" --force "$@"
                ;;
        esac
    fi
    
    parse_arguments "$@"
}

# Allow direct execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi