#!/bin/bash

# Syntax validation script for all cleanup scripts
echo "🔍 Testing all cleanup scripts for syntax errors..."

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Test all shell scripts
ERRORS=0

for script in \
    "$SCRIPTS_DIR/hipaa-cleanup.sh" \
    "$SCRIPTS_DIR/lib/utils.sh" \
    "$SCRIPTS_DIR/phases/phase-prepare.sh" \
    "$SCRIPTS_DIR/phases/phase-data.sh" \
    "$SCRIPTS_DIR/phases/phase-resources.sh" \
    "$SCRIPTS_DIR/phases/phase-vpc.sh" \
    "$SCRIPTS_DIR/phases/phase-verify.sh" \
    "$SCRIPTS_DIR/test-cleanup.sh"
do
    if [[ -f "$script" ]]; then
        echo "Testing $script..."
        if bash -n "$script"; then
            echo "✅ $script - syntax OK"
        else
            echo "❌ $script - syntax ERROR"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo "⚠️  $script - file not found"
        ERRORS=$((ERRORS + 1))
    fi
done

# Test Python scripts
for py_script in \
    "$SCRIPTS_DIR/lib/security-groups.py"
do
    if [[ -f "$py_script" ]]; then
        echo "Testing $py_script..."
        if python3 -m py_compile "$py_script"; then
            echo "✅ $py_script - syntax OK"
        else
            echo "❌ $py_script - syntax ERROR"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo "⚠️  $py_script - file not found"
        ERRORS=$((ERRORS + 1))
    fi
done

if [[ $ERRORS -eq 0 ]]; then
    echo "🎉 All scripts passed syntax validation!"
    exit 0
else
    echo "💥 Found $ERRORS syntax errors!"
    exit 1
fi