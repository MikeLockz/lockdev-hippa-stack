#!/usr/bin/env python3
"""
HIPAA Infrastructure Stack - Make Command Browser (InquirerPy)
================================================================

A professional command-line interface for browsing and executing make commands
using the InquirerPy framework with rich features and cross-platform support.

Installation Requirements:
--------------------------
pip install InquirerPy rich pydantic

Features:
---------
- Hierarchical menu structure with categories
- Professional UI with colors and icons
- Cross-platform compatibility
- Error handling and user feedback
- Command execution with real-time output
- Command history and favorites
- Search functionality

Usage:
------
python make-browser-inquirerpy.py

Author: Claude Code
Version: 1.0
"""

import os
import sys
import subprocess
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import platform

try:
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice
    from InquirerPy.separator import Separator
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.live import Live
    from rich.layout import Layout
    from rich import box
    from pydantic import BaseModel
except ImportError as e:
    print(f"❌ Missing required dependencies: {e}")
    print("\n📦 To install dependencies, run:")
    print("pip install InquirerPy rich pydantic")
    print("\nOr using poetry:")
    print("poetry add InquirerPy rich pydantic")
    sys.exit(1)


class CommandCategory(Enum):
    """Command categories for organizing make targets."""
    DEVELOPMENT = "🚀 Development"
    TESTING = "🧪 Testing"
    DEPLOYMENT = "☁️  Deployment"
    INFRASTRUCTURE = "🏗️  Infrastructure"
    INFRASTRUCTURE_DIAGRAMS = "📊 Infrastructure > Diagrams"
    SECURITY = "🔒 Security"
    UTILITIES = "🔧 Utilities"
    CLEANUP = "🧹 Cleanup"
    MONITORING = "📊 Monitoring"
    CONFIGURATION = "⚙️  Configuration"


@dataclass
class MakeCommand:
    """Represents a make command with metadata."""
    name: str
    description: str
    category: CommandCategory
    is_dangerous: bool = False
    requires_confirmation: bool = False
    aliases: List[str] = field(default_factory=list)


class MakefileParser:
    """Parses Makefile to extract commands and descriptions."""
    
    def __init__(self, makefile_path: str = "Makefile"):
        self.makefile_path = makefile_path
        self.console = Console()
    
    def parse(self) -> Dict[str, MakeCommand]:
        """Parse the Makefile and return organized commands."""
        commands = {}
        
        if not os.path.exists(self.makefile_path):
            self.console.print(f"❌ Makefile not found at: {self.makefile_path}", style="red")
            return commands
        
        try:
            with open(self.makefile_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse targets with descriptions (## comments)
            pattern = r'^([a-zA-Z_-]+):\s*([^#\n]*)?##\s*(.+)$'
            matches = re.findall(pattern, content, re.MULTILINE)
            
            for target_name, dependencies, description in matches:
                target_name = target_name.strip()
                description = description.strip()
                
                # Skip internal/helper targets
                if target_name.startswith('_') or target_name in ['help']:
                    continue
                
                category = self._categorize_command(target_name, description)
                is_dangerous = self._is_dangerous_command(target_name, description)
                requires_confirmation = self._requires_confirmation(target_name, description)
                
                commands[target_name] = MakeCommand(
                    name=target_name,
                    description=description,
                    category=category,
                    is_dangerous=is_dangerous,
                    requires_confirmation=requires_confirmation
                )
            
            self.console.print(f"✅ Parsed {len(commands)} make commands", style="green")
            return commands
            
        except Exception as e:
            self.console.print(f"❌ Error parsing Makefile: {e}", style="red")
            return commands
    
    def _categorize_command(self, name: str, description: str) -> CommandCategory:
        """Categorize a command based on its name and description."""
        name_lower = name.lower()
        desc_lower = description.lower()
        
        # Development commands
        if any(keyword in name_lower for keyword in ['dev-', 'start', 'browser', 'quick-start']):
            return CommandCategory.DEVELOPMENT
        
        # Testing commands
        if any(keyword in name_lower for keyword in ['test', 'lint', 'format']):
            return CommandCategory.TESTING
        
        # Deployment commands
        if any(keyword in name_lower for keyword in ['deploy', 'preview-dev', 'preview-staging', 'preview-prod', 'validate-env']):
            return CommandCategory.DEPLOYMENT
        
        # Infrastructure > Diagrams commands - All diagram generation commands grouped together
        if any(keyword in name_lower for keyword in ['generate-diagrams', 'generate-network', 'generate-compute', 'generate-security', 'setup-diagrams', 'list-diagrams', 'get-current-stack']):
            return CommandCategory.INFRASTRUCTURE_DIAGRAMS
        
        # Infrastructure commands (excluding diagrams)
        if any(keyword in name_lower for keyword in ['setup-env', 'setup-credentials', 'list-aws', 'check-pulumi', 'login-pulumi']):
            return CommandCategory.INFRASTRUCTURE
        
        # Security commands
        if any(keyword in name_lower for keyword in ['security', 'rotate-keys', 'emergency']):
            return CommandCategory.SECURITY
        
        # Cleanup commands
        if any(keyword in name_lower for keyword in ['clean', 'cleanup', 'destroy', 'force-cleanup', 'preview-clean']):
            return CommandCategory.CLEANUP
        
        # Monitoring commands
        if any(keyword in name_lower for keyword in ['status', 'show-outputs', 'verify', 'install-status']):
            return CommandCategory.MONITORING
        
        # Configuration commands
        if any(keyword in name_lower for keyword in ['config', 'install', 'setup-git', 'setup-env-files', 'setup']):
            return CommandCategory.CONFIGURATION
        
        # Default to utilities
        return CommandCategory.UTILITIES
    
    def _is_dangerous_command(self, name: str, description: str) -> bool:
        """Determine if a command is potentially dangerous."""
        dangerous_keywords = [
            'destroy', 'delete', 'remove', 'clean', 'cleanup', 'emergency',
            'force', 'production', 'prod', 'complete', 'deploy-prod', 
            'cleanup-prod', 'preview-clean-prod', 'force-cleanup'
        ]
        
        name_lower = name.lower()
        desc_lower = description.lower()
        
        return any(keyword in name_lower or keyword in desc_lower 
                  for keyword in dangerous_keywords)
    
    def _requires_confirmation(self, name: str, description: str) -> bool:
        """Determine if a command requires user confirmation."""
        return self._is_dangerous_command(name, description) or 'prod' in name.lower()


class CommandHistory:
    """Manages command execution history."""
    
    def __init__(self, history_file: str = ".make_browser_history.json"):
        self.history_file = Path(history_file)
        self.history = self._load_history()
    
    def _load_history(self) -> List[Dict]:
        """Load command history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return []
    
    def _save_history(self):
        """Save command history to file."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history[-50:], f, indent=2)  # Keep last 50 commands
        except Exception:
            pass
    
    def add_command(self, command: str, success: bool, duration: float):
        """Add a command to history."""
        import datetime
        
        entry = {
            "command": command,
            "timestamp": datetime.datetime.now().isoformat(),
            "success": success,
            "duration": duration,
            "platform": platform.system()
        }
        
        self.history.append(entry)
        self._save_history()
    
    def get_recent_commands(self, limit: int = 10) -> List[str]:
        """Get recent commands."""
        return [entry["command"] for entry in self.history[-limit:]]
    
    def get_frequent_commands(self, limit: int = 5) -> List[str]:
        """Get most frequently used commands."""
        from collections import Counter
        
        commands = [entry["command"] for entry in self.history]
        counter = Counter(commands)
        return [cmd for cmd, _ in counter.most_common(limit)]


class MakeBrowser:
    """Interactive make command browser using InquirerPy."""
    
    def __init__(self, makefile_path: str = "Makefile"):
        self.console = Console()
        self.makefile_path = makefile_path
        self.parser = MakefileParser(makefile_path)
        self.commands = self.parser.parse()
        self.history = CommandHistory()
        
        # Organize commands by category
        self.categorized_commands = self._organize_by_category()
    
    def _organize_by_category(self) -> Dict[CommandCategory, List[MakeCommand]]:
        """Organize commands by category."""
        categorized = {}
        
        for category in CommandCategory:
            categorized[category] = []
        
        for command in self.commands.values():
            categorized[command.category].append(command)
        
        # Sort commands within each category
        for category in categorized:
            categorized[category].sort(key=lambda x: x.name)
        
        return categorized
    
    def _create_command_choice(self, command: MakeCommand) -> Choice:
        """Create a choice object for a command."""
        icon = "⚠️ " if command.is_dangerous else "▶️ "
        name_with_icon = f"{icon}{command.name}"
        
        # Truncate long descriptions
        description = command.description
        if len(description) > 60:
            description = description[:57] + "..."
        
        return Choice(
            value=command.name,
            name=f"{name_with_icon:<25} {description}",
            enabled=True
        )
    
    def _display_welcome(self):
        """Display welcome message."""
        welcome_text = Text()
        welcome_text.append("HIPAA Infrastructure Stack\n", style="bold blue")
        welcome_text.append("Make Command Browser", style="bold")
        
        info_text = Text()
        info_text.append(f"📁 Makefile: {self.makefile_path}\n", style="dim")
        info_text.append(f"📊 Commands: {len(self.commands)}\n", style="dim")
        info_text.append(f"💻 Platform: {platform.system()}", style="dim")
        
        panel = Panel(
            welcome_text + "\n" + info_text,
            title="🚀 Welcome",
            border_style="blue",
            padding=(1, 2)
        )
        
        self.console.print(panel)
        self.console.print()
    
    def _show_category_menu(self) -> Optional[CommandCategory]:
        """Show category selection menu."""
        choices = []
        
        # Add categories with command counts
        for category in CommandCategory:
            command_count = len(self.categorized_commands[category])
            if command_count > 0:
                choices.append(Choice(
                    value=category,
                    name=f"{category.value} ({command_count} commands)"
                ))
        
        # Add utility options
        choices.append(Separator())
        choices.append(Choice(value="recent", name="🕒 Recent Commands"))
        choices.append(Choice(value="favorites", name="⭐ Frequent Commands"))
        choices.append(Choice(value="search", name="🔍 Search Commands"))
        choices.append(Choice(value="help", name="❓ Help"))
        choices.append(Choice(value="exit", name="🚪 Exit"))
        
        try:
            result = inquirer.select(
                message="Select a category:",
                choices=choices,
                default=CommandCategory.DEVELOPMENT
            ).execute()
            
            return result
        except KeyboardInterrupt:
            return "exit"
    
    def _show_command_menu(self, category: CommandCategory) -> Optional[str]:
        """Show command selection menu for a category."""
        commands = self.categorized_commands[category]
        
        if not commands:
            self.console.print(f"No commands found in {category.value}", style="yellow")
            return None
        
        choices = []
        for command in commands:
            choices.append(self._create_command_choice(command))
        
        choices.append(Separator())
        choices.append(Choice(value="back", name="⬅️  Back to Categories"))
        
        try:
            result = inquirer.select(
                message=f"Select a {category.value} command:",
                choices=choices
            ).execute()
            
            return result
        except KeyboardInterrupt:
            return "back"
    
    def _show_recent_commands(self) -> Optional[str]:
        """Show recent commands menu."""
        recent = self.history.get_recent_commands(10)
        
        if not recent:
            self.console.print("No recent commands found", style="yellow")
            return None
        
        choices = []
        for cmd in recent:
            if cmd in self.commands:
                command_obj = self.commands[cmd]
                choices.append(self._create_command_choice(command_obj))
        
        choices.append(Separator())
        choices.append(Choice(value="back", name="⬅️  Back to Categories"))
        
        try:
            result = inquirer.select(
                message="Select a recent command:",
                choices=choices
            ).execute()
            
            return result
        except KeyboardInterrupt:
            return "back"
    
    def _show_frequent_commands(self) -> Optional[str]:
        """Show frequent commands menu."""
        frequent = self.history.get_frequent_commands(10)
        
        if not frequent:
            self.console.print("No frequent commands found", style="yellow")
            return None
        
        choices = []
        for cmd in frequent:
            if cmd in self.commands:
                command_obj = self.commands[cmd]
                choices.append(self._create_command_choice(command_obj))
        
        choices.append(Separator())
        choices.append(Choice(value="back", name="⬅️  Back to Categories"))
        
        try:
            result = inquirer.select(
                message="Select a frequent command:",
                choices=choices
            ).execute()
            
            return result
        except KeyboardInterrupt:
            return "back"
    
    def _search_commands(self) -> Optional[str]:
        """Search for commands interactively."""
        try:
            search_term = inquirer.text(
                message="Enter search term:"
            ).execute().strip()
            
            if not search_term:
                return None
            
            # Search in command names and descriptions
            matches = []
            search_lower = search_term.lower()
            
            for command in self.commands.values():
                if (search_lower in command.name.lower() or 
                    search_lower in command.description.lower()):
                    matches.append(command)
            
            if not matches:
                self.console.print(f"No commands found matching '{search_term}'", style="yellow")
                return None
            
            # Show matches
            choices = []
            for command in sorted(matches, key=lambda x: x.name):
                choices.append(self._create_command_choice(command))
            
            choices.append(Separator())
            choices.append(Choice(value="back", name="⬅️  Back to Categories"))
            
            result = inquirer.select(
                message=f"Found {len(matches)} matching commands:",
                choices=choices
            ).execute()
            
            return result
            
        except KeyboardInterrupt:
            return "back"
    
    def _show_help(self):
        """Show help information."""
        table = Table(title="Make Browser Help", box=box.ROUNDED)
        table.add_column("Feature", style="cyan", width=20)
        table.add_column("Description", style="white")
        
        table.add_row("Categories", "Browse commands organized by type")
        table.add_row("Recent Commands", "Access your recently executed commands")
        table.add_row("Frequent Commands", "Access your most used commands")
        table.add_row("Search", "Search commands by name or description")
        table.add_row("⚠️  Warning Icons", "Dangerous commands that require caution")
        table.add_row("Ctrl+C", "Cancel current operation or exit")
        table.add_row("Arrow Keys", "Navigate menus")
        table.add_row("Enter", "Select option")
        
        self.console.print(table)
        self.console.print("\n📋 Command Categories:", style="bold")
        for category in CommandCategory:
            count = len(self.categorized_commands[category])
            if count > 0:
                self.console.print(f"  {category.value}: {count} commands")
        
        self.console.print("\nPress Enter to continue...")
        input()
    
    def _confirm_dangerous_command(self, command: MakeCommand) -> bool:
        """Confirm execution of dangerous commands."""
        if not command.is_dangerous:
            return True
        
        warning_panel = Panel(
            f"⚠️  WARNING: This is a potentially dangerous command!\n\n"
            f"Command: {command.name}\n"
            f"Description: {command.description}\n\n"
            f"This command may modify or delete resources.",
            title="⚠️  Danger Zone",
            border_style="red",
            padding=(1, 2)
        )
        
        self.console.print(warning_panel)
        
        try:
            confirm = inquirer.confirm(
                message="Are you sure you want to execute this command?",
                default=False
            ).execute()
            
            return confirm
        except KeyboardInterrupt:
            return False
    
    def _execute_command(self, command_name: str) -> bool:
        """Execute a make command."""
        command = self.commands.get(command_name)
        if not command:
            self.console.print(f"❌ Command not found: {command_name}", style="red")
            return False
        
        # Show command info
        info_panel = Panel(
            f"Command: make {command.name}\n"
            f"Description: {command.description}\n"
            f"Category: {command.category.value}",
            title="🚀 Executing Command",
            border_style="blue"
        )
        self.console.print(info_panel)
        
        # Confirm dangerous commands
        if not self._confirm_dangerous_command(command):
            self.console.print("❌ Command execution cancelled", style="yellow")
            return False
        
        # Execute command
        import time
        start_time = time.time()
        
        try:
            # Cross-platform command execution
            if platform.system() == "Windows":
                # For Windows, try different approaches
                if self._check_make_available():
                    cmd = ["make", command.name]
                else:
                    # Fallback for Windows without make
                    self.console.print("❌ Make not available on Windows. Consider using WSL or install make.", style="red")
                    return False
            else:
                cmd = ["make", command.name]
            
            self.console.print(f"\n🔄 Executing: {' '.join(cmd)}\n", style="blue")
            
            # Run command with real-time output
            process = subprocess.run(
                cmd,
                cwd=os.path.dirname(os.path.abspath(self.makefile_path)) or ".",
                capture_output=False,
                text=True,
                shell=platform.system() == "Windows"  # Use shell on Windows
            )
            
            duration = time.time() - start_time
            success = process.returncode == 0
            
            # Add to history
            self.history.add_command(command.name, success, duration)
            
            if success:
                self.console.print(f"\n✅ Command completed successfully in {duration:.2f}s", style="green")
            else:
                self.console.print(f"\n❌ Command failed with return code {process.returncode}", style="red")
            
            return success
            
        except FileNotFoundError:
            self.console.print("❌ Make command not found. Please ensure make is installed.", style="red")
            self.console.print("💡 On macOS: brew install make", style="blue")
            self.console.print("💡 On Ubuntu/Debian: sudo apt-get install build-essential", style="blue")
            self.console.print("💡 On Windows: Use WSL or install make via Chocolatey", style="blue")
            return False
        except Exception as e:
            self.console.print(f"❌ Error executing command: {e}", style="red")
            return False
        finally:
            self.console.print("\nPress Enter to continue...")
            input()
    
    def _check_make_available(self) -> bool:
        """Check if make command is available."""
        try:
            subprocess.run(["make", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def run(self):
        """Run the interactive browser."""
        try:
            self._display_welcome()
            
            while True:
                selection = self._show_category_menu()
                
                if selection == "exit":
                    break
                elif selection == "help":
                    self._show_help()
                elif selection == "recent":
                    command = self._show_recent_commands()
                    if command and command != "back":
                        self._execute_command(command)
                elif selection == "favorites":
                    command = self._show_frequent_commands()
                    if command and command != "back":
                        self._execute_command(command)
                elif selection == "search":
                    command = self._search_commands()
                    if command and command != "back":
                        self._execute_command(command)
                elif isinstance(selection, CommandCategory):
                    while True:
                        command = self._show_command_menu(selection)
                        if command == "back" or command is None:
                            break
                        else:
                            self._execute_command(command)
        
        except KeyboardInterrupt:
            pass
        finally:
            self.console.print("\n👋 Thank you for using Make Browser!", style="blue")


def test_parse_only(makefile_path="Makefile"):
    """Test the makefile parsing functionality without UI."""
    try:
        if not Path(makefile_path).exists():
            print(f"❌ Error: Makefile not found at: {makefile_path}")
            print(f"📁 Current directory: {Path.cwd()}")
            return False
        
        console = Console()
        console.print("\n🏥 HIPAA Infrastructure Stack - Make Command Parser Test (InquirerPy)", style="bold blue")
        console.print("=" * 60)
        
        # Test parsing
        parser = MakefileParser(makefile_path)
        commands = parser.parse()
        
        console.print(f"✅ Successfully parsed {len(commands)} commands with descriptions", style="green")
        
        # Test categorization
        from collections import defaultdict
        categorized = defaultdict(list)
        
        for command in commands.values():
            categorized[command.category].append(command)
        
        # Display results
        console.print(f"\n📊 Categorization Results:", style="bold")
        console.print("=" * 60)
        
        for category, cmds in categorized.items():
            if cmds:
                console.print(f"\n📁 {category.value} ({len(cmds)} commands):", style="cyan")
                for cmd in sorted(cmds, key=lambda x: x.name)[:5]:  # Show first 5
                    short_desc = cmd.description[:50] + "..." if len(cmd.description) > 50 else cmd.description
                    dangerous_icon = "⚠️ " if cmd.is_dangerous else ""
                    console.print(f"  {dangerous_icon}{cmd.name:<25} | {short_desc}")
                if len(cmds) > 5:
                    console.print(f"  ... and {len(cmds) - 5} more commands")
        
        console.print(f"\n📈 Summary:", style="bold")
        console.print(f"  Total Commands: {len(commands)}")
        console.print(f"  Categories: {len([c for c in categorized.values() if c])}")
        console.print(f"  Dangerous Commands: {len([c for c in commands.values() if c.is_dangerous])}")
        console.print(f"  Parsing: ✅ SUCCESS", style="green")
        console.print(f"  Categorization: ✅ SUCCESS", style="green")
        
        console.print(f"\n💡 To use the full interactive browser, ensure you have a proper terminal:", style="blue")
        console.print(f"   poetry run python ../make-browser-inquirerpy.py")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during parsing test: {e}")
        return False


def main():
    """Main entry point."""
    try:
        # Parse command line arguments
        makefile_path = "Makefile"
        test_mode = False
        
        for i, arg in enumerate(sys.argv[1:], 1):
            if arg == "--test-parse":
                test_mode = True
            elif not arg.startswith("--") and Path(arg).exists():
                makefile_path = arg
        
        # Check for test mode
        if test_mode:
            return test_parse_only(makefile_path)
        
        # Determine Makefile path
        if not os.path.exists(makefile_path):
            # Try parent directory
            parent_makefile = os.path.join("..", "Makefile")
            if os.path.exists(parent_makefile):
                makefile_path = parent_makefile
            else:
                console = Console()
                console.print("❌ Makefile not found in current or parent directory", style="red")
                console.print("Please run this script from a directory containing a Makefile", style="yellow")
                console.print("Or use --test-parse mode for dependency-free testing", style="blue")
                sys.exit(1)
        
        # Create and run browser
        try:
            browser = MakeBrowser(makefile_path)
            browser.run()
        except Exception as e:
            if "Input is not a terminal" in str(e) or "Invalid argument" in str(e):
                console = Console()
                console.print("❌ Error: Terminal input not available for interactive mode", style="red")
                console.print("This error occurs when running in non-interactive environments", style="yellow")
                console.print("\n💡 Solutions:", style="blue")
                console.print("  1. Run in a proper terminal (Terminal.app, iTerm2, etc.)")
                console.print("  2. Use the test-parse mode: python make-browser-inquirerpy.py --test-parse")
                console.print("  3. Check if stdin is available: python -c 'import sys; print(sys.stdin.isatty())'")
                sys.exit(1)
            else:
                raise
        
    except KeyboardInterrupt:
        console = Console()
        console.print("\n\n👋 Browser interrupted by user. Goodbye!", style="blue")


if __name__ == "__main__":
    main()