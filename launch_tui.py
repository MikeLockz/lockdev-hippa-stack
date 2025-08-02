#!/usr/bin/env python3
"""
Launch script for the HIPAA Infrastructure Stack TUI.

This script provides a simple way to launch the TUI with proper
environment setup and error handling.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_dependencies():
    """Check if required dependencies are available."""
    missing_deps = []
    
    try:
        import textual
        if textual.__version__ < "0.45.0":
            missing_deps.append("textual>=0.45.0 (current: {textual.__version__})")
    except ImportError:
        missing_deps.append("textual>=0.45.0")
    
    try:
        import rich
    except ImportError:
        missing_deps.append("rich>=13.0.0")
    
    try:
        import yaml
    except ImportError:
        missing_deps.append("pyyaml>=6.0")
    
    if missing_deps:
        print("❌ Missing required dependencies:")
        for dep in missing_deps:
            print(f"   • {dep}")
        print("\n💡 Install with:")
        print("   pip install textual>=0.45.0 rich>=13.0.0 pyyaml>=6.0")
        return False
    
    return True

def check_makefile():
    """Check if Makefile exists."""
    makefile_path = project_root / "Makefile"
    if not makefile_path.exists():
        print("⚠️  Warning: Makefile not found in current directory")
        print("   The TUI will work but won't show any commands")
        return False
    return True

def main():
    """Main entry point."""
    print("🎯 HIPAA Infrastructure Stack TUI")
    print("=" * 40)
    
    # Check dependencies
    print("🔍 Checking dependencies...")
    if not check_dependencies():
        return 1
    print("✅ All dependencies available")
    
    # Check Makefile
    print("\n🔍 Checking Makefile...")
    makefile_exists = check_makefile()
    if makefile_exists:
        print("✅ Makefile found")
    
    # Import and launch TUI
    print("\n🚀 Launching TUI...")
    try:
        from tui.app import main as tui_main
        
        print("📝 Press 'q' to quit, '/' to search, Tab to navigate")
        print("🎮 Starting TUI in 3 seconds...")
        print("   (Press Ctrl+C to cancel)")
        
        import time
        for i in range(3, 0, -1):
            print(f"   {i}...", end="", flush=True)
            time.sleep(1)
        print("\n")
        
        # Launch the TUI
        tui_main()
        
    except KeyboardInterrupt:
        print("\n\n👋 TUI launch cancelled by user")
        return 0
    except Exception as e:
        print(f"\n❌ Failed to launch TUI: {e}")
        print("\n🔧 Troubleshooting:")
        print("   • Run: python test_tui_phase1.py")
        print("   • Check terminal size (minimum 80x24)")
        print("   • Ensure terminal supports color")
        return 1
    
    print("\n👋 TUI session ended")
    return 0

if __name__ == "__main__":
    sys.exit(main())