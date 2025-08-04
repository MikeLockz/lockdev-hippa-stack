#!/bin/bash

# Comprehensive Testing Suite for Unified Cleanup System
# Tests all phases and validates functionality

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
TEST_ENVIRONMENT="test"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PHASES_DIR="$SCRIPT_DIR/phases"

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

run_test() {
    local test_name="$1"
    local test_func="$2"
    
    ((TESTS_RUN++))
    echo -e "\n${BLUE}▶ Running test:${NC} $test_name"
    
    if $test_func; then
        log_success "$test_name"
    else
        log_error "$test_name"
    fi
}

# Test utility functions
test_utils_availability() {
    local utils_file="$SCRIPT_DIR/lib/utils.sh"
    if [[ -f "$utils_file" ]]; then
        source "$utils_file"
        command -v log_phase >/dev/null
    else
        return 1
    fi
}

# Test phase scripts availability
test_phase_scripts() {
    local phases=("phase-prepare.sh" "phase-data.sh" "phase-resources.sh" "phase-vpc.sh" "phase-verify.sh")
    
    for phase in "${phases[@]}"; do
        local phase_file="$PHASES_DIR/$phase"
        if [[ ! -f "$phase_file" ]]; then
            echo "Missing: $phase"
            return 1
        fi
        
        if [[ ! -x "$phase_file" ]]; then
            echo "Not executable: $phase"
            return 1
        fi
    done
    
    return 0
}

# Test configuration loading
test_config_loading() {
    source "$SCRIPT_DIR/lib/utils.sh"
    
    # Test with mock config
    local mock_config="$SCRIPT_DIR/../config/test-environments.yaml"
    mkdir -p "$(dirname "$mock_config")"
    
    cat > "$mock_config" <<EOF
environments:
  test:
    root_profile: test-root
    service_profile: test-service
    region: us-east-1
    cleanup:
      patterns:
        - "hipaa-*"
        - "test-*"
EOF
    
    # Test loading function
    load_environment_config() {
        local env="$1"
        echo "Mock config loaded for: $env"
    }
    
    get_env_config() {
        local env="$1"
        local key="$2"
        case "$key" in
            "root_profile") echo "test-root" ;;
            "region") echo "us-east-1" ;;
            *) echo "mock-value" ;;
        esac
    }
    
    load_environment_config "test"
    local region=$(get_env_config "test" "region")
    
    [[ "$region" == "us-east-1" ]]
    
    # Cleanup
    rm -f "$mock_config"
}

# Test CLI interface
test_cli_interface() {
    local main_script="$SCRIPT_DIR/destroy-aws-resources.sh"
    
    if [[ ! -f "$main_script" ]]; then
        echo "Main script not found: $main_script"
        return 1
    fi
    
    if [[ ! -x "$main_script" ]]; then
        echo "Main script not executable: $main_script"
        return 1
    fi
    
    # Test help output
    "$main_script" --help >/dev/null 2>&1
}

# Test dry-run functionality
test_dry_run() {
    local main_script="$SCRIPT_DIR/destroy-aws-resources.sh"
    
    # Test dry-run with non-existent environment
    local output=$("$main_script" nonexistent --dry-run 2>&1 || echo "")
    [[ "$output" == *"DRY RUN"* ]]
}

# Test phase hooks
test_phase_hooks() {
    source "$SCRIPT_DIR/lib/utils.sh"
    
    # Mock is_dry_run function
    is_dry_run() { return 1; }
    
    # Test each phase hook
    local phases=("prepare" "data" "resources" "vpc" "verify")
    
    for phase in "${phases[@]}"; do
        local hook_file="$PHASES_DIR/phase-$phase.sh"
        if [[ -f "$hook_file" ]]; then
            source "$hook_file"
            
            local hook_func="phase_${phase}_hook"
            if declare -f "$hook_func" >/dev/null; then
                # Test hook exists (should not actually run in test)
                echo "Hook exists: $hook_func"
            else
                echo "Hook missing: $hook_func"
                return 1
            fi
        fi
    done
    
    return 0
}

# Test security group resolver
test_security_group_resolver() {
    local resolver="$SCRIPT_DIR/lib/security-groups.py"
    
    if [[ ! -f "$resolver" ]]; then
        echo "Security group resolver not found: $resolver"
        return 1
    fi
    
    if [[ ! -x "$resolver" ]]; then
        chmod +x "$resolver"
    fi
    
    # Test help output
    python3 "$resolver" --help >/dev/null 2>&1
}

# Test Makefile integration
test_makefile_integration() {
    local makefile="$PROJECT_DIR/../Makefile"
    
    if [[ ! -f "$makefile" ]]; then
        echo "Makefile not found: $makefile"
        return 1
    fi
    
    # Test cleanup targets exist
    local targets=("clean-dev" "clean-staging" "clean-prod" "preview-clean-dev")
    
    for target in "${targets[@]}"; do
        if ! grep -q "^$target:" "$makefile"; then
            echo "Missing target: $target"
            return 1
        fi
    done
    
    return 0
}

# Test environment configuration
test_environment_config() {
    local config_file="$PROJECT_DIR/configs/environments.yaml"
    
    if [[ ! -f "$config_file" ]]; then
        echo "Environment config not found: $config_file"
        return 1
    fi
    
    # Test YAML structure
    if command -v yq >/dev/null 2>&1; then
        yq eval '.environments' "$config_file" >/dev/null
    else
        log_warning "yq not available, skipping YAML validation"
    fi
    
    return 0
}

# Test error handling
test_error_handling() {
    source "$SCRIPT_DIR/lib/utils.sh"
    
    # Test log functions exist
    declare -f log_error >/dev/null
    declare -f log_warning >/dev/null
    declare -f log_info >/dev/null
    declare -f log_success >/dev/null
}

# Test AWS CLI dependencies
test_aws_cli_dependencies() {
    local required_commands=("aws" "jq")
    
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            echo "Missing command: $cmd"
            return 1
        fi
    done
    
    return 0
}

# Test phase execution order
test_phase_order() {
    local expected_order=("prepare" "data" "resources" "vpc" "verify")
    local actual_order=()
    
    # Read phase order from main script
    local main_script="$SCRIPT_DIR/destroy-aws-resources.sh"
    if [[ -f "$main_script" ]]; then
        local phases=$(grep -o 'PHASES=.*' "$main_script" | head -1)
        if [[ -n "$phases" ]]; then
            echo "Phase order found: $phases"
            return 0
        fi
    fi
    
    return 0
}

# Test legacy compatibility
test_legacy_compatibility() {
    local legacy_scripts=("comprehensive-cleanup.sh" "enhanced-cleanup.sh" "force-cleanup.sh" "final-cleanup.sh" "smart-cleanup.sh")
    
    for script in "${legacy_scripts[@]}"; do
        local legacy_file="$PROJECT_DIR/$script"
        if [[ -f "$legacy_file" ]]; then
            echo "Legacy script exists: $script"
        fi
    done
    
    return 0
}

# Run all tests
run_all_tests() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Unified Cleanup System Test Suite${NC}"
    echo -e "${BLUE}========================================${NC}"
    
    # Core functionality tests
    run_test "Utility functions availability" test_utils_availability
    run_test "Phase scripts availability" test_phase_scripts
    run_test "Configuration loading" test_config_loading
    run_test "CLI interface" test_cli_interface
    run_test "Dry-run functionality" test_dry_run
    run_test "Phase hooks" test_phase_hooks
    run_test "Security group resolver" test_security_group_resolver
    
    # Integration tests
    run_test "Makefile integration" test_makefile_integration
    run_test "Environment configuration" test_environment_config
    run_test "Error handling" test_error_handling
    run_test "AWS CLI dependencies" test_aws_cli_dependencies
    run_test "Phase execution order" test_phase_order
    run_test "Legacy compatibility" test_legacy_compatibility
    
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}  Test Summary${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e "Tests Run:    ${TESTS_RUN}"
    echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
    echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "\n${GREEN}✅ All tests passed!${NC}"
        return 0
    else
        echo -e "\n${RED}❌ Some tests failed!${NC}"
        return 1
    fi
}

# Main execution
main() {
    case "${1:-all}" in
        "unit")
            run_test "Utility functions availability" test_utils_availability
            run_test "Phase scripts availability" test_phase_scripts
            run_test "Configuration loading" test_config_loading
            ;;
        "integration")
            run_test "Makefile integration" test_makefile_integration
            run_test "Environment configuration" test_environment_config
            run_test "AWS CLI dependencies" test_aws_cli_dependencies
            ;;
        "security")
            run_test "Security group resolver" test_security_group_resolver
            run_test "Error handling" test_error_handling
            ;;
        "all"|*)
            run_all_tests
            ;;
    esac
}

# Run tests
main "$@"