#!/usr/bin/env python3
"""Test script for the HIPAA Infrastructure Stack TUI."""

import sys
import os
from pathlib import Path

# Add the tui directory to the Python path
tui_path = Path(__file__).parent / "tui"
sys.path.insert(0, str(tui_path))

try:
    from tui.app import HIPAATUIApp
    
    def main():
        """Run the TUI application."""
        print("🚀 Starting HIPAA Infrastructure Stack TUI...")
        print("📋 Phase 1 Framework Test")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        app = HIPAATUIApp()
        app.run()
    
    if __name__ == "__main__":
        main()

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("🔍 Checking TUI structure...")
    
    # Check if all required files exist
    required_files = [
        "tui/__init__.py",
        "tui/app.py",
        "tui/models/__init__.py",
        "tui/models/command.py",
        "tui/models/status.py",
        "tui/components/__init__.py",
        "tui/components/status_bar.py",
        "tui/components/command_tree.py",
        "tui/components/output_pane.py",
        "tui/services/__init__.py", 
        "tui/services/makefile_parser.py",
        "tui/themes/__init__.py",
        "tui/themes/dark.py",
        "tui/config/default.yaml",
        "tui/config/keybindings.yaml",
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Missing files:")
        for file_path in missing_files:
            print(f"  - {file_path}")
    else:
        print("✅ All required files exist")
        print("🔍 Checking imports...")
        
        # Try to import individual modules
        try:
            from tui.models import command, status
            print("✅ Models import successfully")
        except Exception as e:
            print(f"❌ Models import error: {e}")
        
        try:
            from tui.services import makefile_parser
            print("✅ Services import successfully")
        except Exception as e:
            print(f"❌ Services import error: {e}")
        
        try:
            from tui.components import status_bar, command_tree, output_pane
            print("✅ Components import successfully")
        except Exception as e:
            print(f"❌ Components import error: {e}")
        
        print(f"Original error: {e}")

except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()