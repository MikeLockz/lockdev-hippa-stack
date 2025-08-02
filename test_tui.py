#!/usr/bin/env python3
"""
Simple test script to verify TUI functionality
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from tui_make_textual import CommandDatabase, MakeCommand
    
    print("✅ TUI Module Import Successful")
    print(f"📊 Total Commands: {len(CommandDatabase.COMMANDS)}")
    
    categories = CommandDatabase.get_all_categories()
    print(f"📂 Categories: {', '.join(categories)}")
    
    # Test command retrieval
    quickstart_commands = CommandDatabase.get_commands_by_category("quickstart")
    print(f"🚀 Quick Start Commands: {len(quickstart_commands)}")
    for cmd in quickstart_commands:
        print(f"   • {cmd.name} - {cmd.description}")
    
    # Test search functionality
    search_results = CommandDatabase.search_commands("deploy")
    print(f"🔍 'deploy' search results: {len(search_results)}")
    
    print("\n✅ All TUI tests passed!")
    
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("💡 Make sure textual is installed: pip install textual")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)