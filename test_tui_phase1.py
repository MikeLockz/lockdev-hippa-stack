#!/usr/bin/env python3
"""
Test script for TUI Phase 1 framework validation.

This script validates that all Phase 1 components are working correctly
without actually launching the interactive TUI.
"""

import sys
import asyncio
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all TUI components can be imported."""
    print("🔍 Testing imports...")
    
    try:
        from tui.app import HIPAATUIApp, TUIScreen
        from tui.components.status_bar import StatusBar
        from tui.components.command_tree import CommandTree
        from tui.components.output_pane import OutputPane
        from tui.components.modals import ConfirmationModal, CommandPreviewModal
        from tui.models.command import Command, CommandCategory
        from tui.models.status import SystemStatus, StatusType
        from tui.services.makefile_parser import MakefileParser
        from tui.services.aws_checker import AWSChecker
        from tui.services.executor import CommandExecutor
        from tui.themes.dark import DarkTheme
        from tui.themes.light import LightTheme
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_makefile_parsing():
    """Test Makefile parsing functionality."""
    print("\n🔍 Testing Makefile parsing...")
    
    try:
        from tui.services.makefile_parser import MakefileParser
        
        parser = MakefileParser()
        commands = parser.parse()
        
        if not commands:
            print("⚠️  No commands found in Makefile")
            return False
        
        # Test command structure
        first_command = commands[0]
        required_attrs = ['name', 'target', 'category', 'description']
        for attr in required_attrs:
            if not hasattr(first_command, attr):
                print(f"❌ Command missing attribute: {attr}")
                return False
        
        # Test categorization
        categorized = parser.get_commands_by_category()
        if not categorized:
            print("❌ Command categorization failed")
            return False
        
        print(f"✅ Found {len(commands)} commands in {len([c for c in categorized.values() if c])} categories")
        return True
        
    except Exception as e:
        print(f"❌ Makefile parsing failed: {e}")
        return False

def test_status_system():
    """Test status monitoring system."""
    print("\n🔍 Testing status system...")
    
    try:
        from tui.models.status import SystemStatus, ComponentStatus, StatusType
        
        # Test creating default status
        status = SystemStatus.create_default()
        
        # Check all components exist
        components = [status.repository, status.aws, status.pulumi, status.docker]
        if not all(components):
            print("❌ Missing status components")
            return False
        
        # Test status types
        for status_type in StatusType:
            assert hasattr(status_type, 'value')
        
        print("✅ Status system working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Status system failed: {e}")
        return False

def test_app_initialization():
    """Test TUI app initialization."""
    print("\n🔍 Testing app initialization...")
    
    try:
        from tui.app import HIPAATUIApp
        
        app = HIPAATUIApp()
        
        # Check basic properties
        if not app.TITLE:
            print("❌ App missing title")
            return False
        
        if not app.BINDINGS:
            print("❌ App missing key bindings")
            return False
        
        # Test with makefile path
        app_with_makefile = HIPAATUIApp(makefile_path="./Makefile")
        
        print(f"✅ App initialized with {len(app.BINDINGS)} key bindings")
        return True
        
    except Exception as e:
        print(f"❌ App initialization failed: {e}")
        return False

async def test_aws_checker():
    """Test AWS checker (without actual AWS calls)."""
    print("\n🔍 Testing AWS checker...")
    
    try:
        from tui.services.aws_checker import AWSChecker, AWSCredentials, AWSStatus
        
        checker = AWSChecker()
        
        # Test credential object creation
        creds = AWSCredentials(is_valid=True, region="us-east-1")
        if not creds.is_valid:
            print("❌ AWS credentials object creation failed")
            return False
        
        # Test status object creation
        status = AWSStatus(credentials=creds, connectivity=True)
        if not status.connectivity:
            print("❌ AWS status object creation failed")
            return False
        
        print("✅ AWS checker components working")
        return True
        
    except Exception as e:
        print(f"❌ AWS checker failed: {e}")
        return False

def test_command_executor():
    """Test command executor (without running commands)."""
    print("\n🔍 Testing command executor...")
    
    try:
        from tui.services.executor import CommandExecutor, ExecutionResult, ExecutionStatus
        from tui.models.command import Command, CommandCategory
        
        executor = CommandExecutor()
        
        # Test creating a test command
        test_command = Command(
            name="Test Command",
            description="A test command",
            target="help",
            category=CommandCategory.UTILITIES
        )
        
        # Test execution result creation with required parameters
        result = ExecutionResult(command=test_command, status=ExecutionStatus.PENDING)
        if result.command != test_command:
            print("❌ Execution result creation failed")
            return False
        
        if result.status != ExecutionStatus.PENDING:
            print("❌ Execution result status failed")
            return False
        
        print("✅ Command executor components working")
        return True
        
    except Exception as e:
        print(f"❌ Command executor failed: {e}")
        return False

def test_themes():
    """Test theme system."""
    print("\n🔍 Testing themes...")
    
    try:
        from tui.themes.dark import DarkTheme
        from tui.themes.light import LightTheme
        
        # Test theme colors
        if not DarkTheme.COLORS:
            print("❌ Dark theme has no colors")
            return False
        
        if not LightTheme.COLORS:
            print("❌ Light theme has no colors")
            return False
        
        # Test theme methods
        light_config = LightTheme.get_theme_config()
        if not light_config.get('name'):
            print("❌ Light theme config invalid")
            return False
        
        print(f"✅ Themes working: Dark ({len(DarkTheme.COLORS)} colors), Light ({len(LightTheme.COLORS)} colors)")
        return True
        
    except Exception as e:
        print(f"❌ Theme system failed: {e}")
        return False

async def main():
    """Run all tests."""
    print("🎯 HIPAA TUI Phase 1 Framework Validation")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Makefile Parsing", test_makefile_parsing),
        ("Status System", test_status_system),
        ("App Initialization", test_app_initialization),
        ("AWS Checker", test_aws_checker),
        ("Command Executor", test_command_executor),
        ("Themes", test_themes),
    ]
    
    results = []
    for test_name, test_func in tests:
        if asyncio.iscoroutinefunction(test_func):
            result = await test_func()
        else:
            result = test_func()
        results.append((test_name, result))
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name:20} {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📈 Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Phase 1 TUI Framework is complete and ready for use!")
        print("\n📋 Next Steps:")
        print("  • Phase 2: Implement command execution with streaming output")
        print("  • Phase 3: Add real-time status monitoring")
        print("  • Phase 4: Polish and optimization")
        print("\n🚀 To launch the TUI: python tui/app.py")
        return True
    else:
        print(f"\n❌ {failed} tests failed. Please fix issues before proceeding.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)