#!/usr/bin/env python3
"""
HIPAA Infrastructure Stack TUI
A comprehensive Textual-based terminal interface for managing make commands
"""

import asyncio
import subprocess
import sys
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header, Footer, Button, Static, TabbedContent, TabPane,
    Input, ListView, ListItem, Label, RichLog, ProgressBar
)
from textual.binding import Binding
from textual.reactive import reactive
from textual.message import Message


@dataclass
class MakeCommand:
    """Structure for make commands with metadata"""
    name: str
    description: str
    category: str
    priority: str = "medium"
    estimated_time: str = "1-2 minutes"
    risk_level: str = "low"
    requires_confirmation: bool = False
    parameters: List[str] = None
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = []


class CommandDatabase:
    """Centralized command definitions with metadata"""
    
    COMMANDS = [
        # Quick Start Commands
        MakeCommand(
            name="quick-start",
            description="Complete setup for new users - installs everything and verifies",
            category="quickstart",
            priority="high",
            estimated_time="5-10 minutes"
        ),
        MakeCommand(
            name="install",
            description="Install all prerequisites and dependencies",
            category="quickstart",
            priority="high",
            estimated_time="10-15 minutes"
        ),
        MakeCommand(
            name="verify",
            description="Verify all installations and configurations",
            category="quickstart",
            priority="high",
            estimated_time="1-2 minutes"
        ),
        
        # Development Environment Commands
        MakeCommand(
            name="dev-app",
            description="Start containerized development environment with Docker",
            category="development",
            priority="high",
            estimated_time="2-3 minutes"
        ),
        MakeCommand(
            name="dev-status",
            description="Check development environment status",
            category="development",
            priority="medium",
            estimated_time="30 seconds"
        ),
        MakeCommand(
            name="dev-logs",
            description="View development environment logs",
            category="development",
            priority="medium",
            estimated_time="ongoing"
        ),
        MakeCommand(
            name="dev-stop",
            description="Stop development environment",
            category="development",
            priority="medium",
            estimated_time="30 seconds"
        ),
        
        # Testing Commands
        MakeCommand(
            name="test",
            description="Run comprehensive tests (CI-equivalent)",
            category="testing",
            priority="high",
            estimated_time="3-5 minutes"
        ),
        MakeCommand(
            name="test-app-quick",
            description="Run basic application tests only",
            category="testing",
            priority="medium",
            estimated_time="1-2 minutes"
        ),
        MakeCommand(
            name="test-app-security",
            description="Run security scans only",
            category="testing",
            priority="medium",
            estimated_time="2-3 minutes"
        ),
        MakeCommand(
            name="lint",
            description="Format and check code quality across all projects",
            category="testing",
            priority="medium",
            estimated_time="1-2 minutes"
        ),
        
        # Infrastructure Deployment Commands
        MakeCommand(
            name="deploy-preview",
            description="Preview infrastructure changes before deployment",
            category="deployment",
            priority="high",
            estimated_time="2-5 minutes"
        ),
        MakeCommand(
            name="deploy-dev",
            description="Deploy to development environment with smart setup",
            category="deployment",
            priority="high",
            estimated_time="5-10 minutes"
        ),
        MakeCommand(
            name="deploy-staging",
            description="Deploy to staging environment",
            category="deployment",
            priority="medium",
            estimated_time="5-10 minutes"
        ),
        MakeCommand(
            name="deploy-prod",
            description="Deploy to production environment",
            category="deployment",
            priority="medium",
            risk_level="high",
            requires_confirmation=True,
            estimated_time="5-10 minutes"
        ),
        
        # Environment Setup Commands
        MakeCommand(
            name="setup-env-dev",
            description="Setup development environment (Phase 1: Root → Service User)",
            category="setup",
            priority="high",
            estimated_time="3-5 minutes"
        ),
        MakeCommand(
            name="validate-env-dev",
            description="Validate development environment access",
            category="setup",
            priority="medium",
            estimated_time="30 seconds"
        ),
        
        # Utility Commands
        MakeCommand(
            name="show-outputs",
            description="Show deployment outputs for all accounts",
            category="utilities",
            priority="medium",
            estimated_time="30 seconds"
        ),
        MakeCommand(
            name="status",
            description="Show status of all Pulumi stacks",
            category="utilities",
            priority="medium",
            estimated_time="30 seconds"
        ),
        
        # Advanced/Emergency Commands
        MakeCommand(
            name="clean-dev",
            description="Destroy development infrastructure safely",
            category="advanced",
            priority="low",
            risk_level="medium",
            requires_confirmation=True,
            estimated_time="3-5 minutes"
        ),
        MakeCommand(
            name="emergency-clean-dev",
            description="Emergency development cleanup (no prompts)",
            category="advanced",
            priority="low",
            risk_level="high",
            requires_confirmation=True,
            estimated_time="2-3 minutes"
        ),
        MakeCommand(
            name="rotate-keys-info",
            description="Show guide for rotating AWS access keys",
            category="advanced",
            priority="low",
            estimated_time="1 minute"
        )
    ]
    
    @classmethod
    def get_commands_by_category(cls, category: str) -> List[MakeCommand]:
        return [cmd for cmd in cls.COMMANDS if cmd.category == category]
    
    @classmethod
    def get_all_categories(cls) -> List[str]:
        return list(set(cmd.category for cmd in cls.COMMANDS))
    
    @classmethod
    def search_commands(cls, query: str) -> List[MakeCommand]:
        query = query.lower()
        return [
            cmd for cmd in cls.COMMANDS
            if query in cmd.name.lower() or query in cmd.description.lower()
        ]


class CommandRunner:
    """Handles command execution with live output streaming"""
    
    def __init__(self, output_widget: RichLog):
        self.output_widget = output_widget
        self.current_process = None
    
    async def run_command(self, command: str, working_dir: str = ".") -> bool:
        """Run a make command and stream output to widget"""
        try:
            self.output_widget.clear()
            self.output_widget.write(f"[bold cyan]$ make {command}\n[/bold cyan]")
            
            # Determine working directory
            if Path("lockdev-hippa-app").exists() and Path("lockdev-hippa-iac").exists():
                # Multi-project setup - use root directory
                cwd = working_dir
            elif Path("lockdev-hippa-app").exists():
                cwd = "lockdev-hippa-app"
            elif Path("lockdev-hippa-iac").exists():
                cwd = "lockdev-hippa-iac"
            else:
                cwd = working_dir
            
            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                "make", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            
            self.current_process = process
            
            # Stream output
            async for line in process.stdout:
                self.output_widget.write(line.decode())
            
            async for line in process.stderr:
                self.output_widget.write(f"[red]{line.decode()}[/red]")
            
            await process.wait()
            
            if process.returncode == 0:
                self.output_widget.write(f"\n[bold green]✅ Command completed successfully[/bold green]")
                return True
            else:
                self.output_widget.write(f"\n[bold red]❌ Command failed with exit code {process.returncode}[/bold red]")
                return False
                
        except Exception as e:
            self.output_widget.write(f"\n[bold red]❌ Error running command: {e}[/bold red]")
            return False
        finally:
            self.current_process = None
    
    def cancel_current_command(self):
        """Cancel the currently running command"""
        if self.current_process and self.current_process.returncode is None:
            self.current_process.terminate()
            self.output_widget.write("\n[yellow]🛑 Command cancelled by user[/yellow]")


class CommandListWidget(Container):
    """Widget for displaying and selecting commands"""
    
    def __init__(self, commands: List[MakeCommand], **kwargs):
        super().__init__(**kwargs)
        self.commands = commands
        self.selected_command = reactive(None)
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            for cmd in self.commands:
                risk_color = {
                    "low": "green",
                    "medium": "yellow", 
                    "high": "red"
                }.get(cmd.risk_level, "white")
                
                button_text = f"{cmd.name}"
                if cmd.risk_level != "low":
                    button_text += f" ⚠️"
                
                button = Button(button_text, id=f"cmd_{cmd.name}", classes="command-button")
                yield button
                
                desc = Label(f"  {cmd.description}", classes="command-desc")
                yield desc
                
                meta = Label(
                    f"  ⏱️ {cmd.estimated_time} | Risk: {cmd.risk_level}",
                    classes="command-meta"
                )
                yield meta
                yield Static()


class CommandDetailsWidget(Container):
    """Widget for displaying command details"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.command = reactive(None)
    
    def watch_command(self, command: Optional[MakeCommand]):
        """Update display when command changes"""
        self.remove_children()
        
        if command:
            with VerticalScroll():
                yield Static(f"[bold]{command.name}[/bold]", classes="detail-title")
                yield Static(f"[dim]{command.description}[/dim]")
                yield Static()
                
                with Horizontal():
                    yield Static(f"⏱️ [bold]Time:[/bold] {command.estimated_time}")
                    yield Static(f"🔒 [bold]Risk:[/bold] {command.risk_level}")
                
                if command.requires_confirmation:
                    yield Static("⚠️ [red]Requires confirmation[/red]")
                
                if command.parameters:
                    yield Static("[bold]Parameters:[/bold]")
                    for param in command.parameters:
                        yield Static(f"  • {param}")
                
                yield Static("[dim]💡 Click the button below to execute this command[/dim]")
                yield Button("Run Command", id="run_selected", classes="run-button")
        else:
            yield Static("[dim]💡 Select a command from the left to view details[/dim]", classes="detail-placeholder")


class HipaaTuiApp(App):
    """Main TUI application"""
    
    CSS = """
    .command-button {
        width: 100%;
        margin: 1;
    }
    
    .command-desc {
        margin-left: 2;
        color: $text-muted;
    }
    
    .command-meta {
        margin-left: 2;
        color: $text-muted;
        text-style: dim;
    }
    
    .detail-title {
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
    }
    
    .detail-placeholder {
        color: $text-muted;
        text-align: center;
        margin-top: 1;
    }
    
    .run-button {
        width: 100%;
        margin-top: 2;
        background: $success;
        text-style: bold;
        height: 3;
    }
    
    TabbedContent {
        height: 1fr;
    }
    
    RichLog {
        height: 1fr;
        border: solid $primary;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+k", "cancel_command", "Cancel"),
    ]
    
    def __init__(self):
        super().__init__()
        self.runner = None
        self.current_command = None
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        with TabbedContent():
            # Quick Start Tab
            with TabPane("🚀 Quick Start", id="quickstart"):
                commands = CommandDatabase.get_commands_by_category("quickstart")
                with Container():
                    yield Horizontal(
                        Vertical(
                            CommandListWidget(commands, id="command_list_quick"),
                            id="left_panel_quick"
                        ),
                        Vertical(
                            CommandDetailsWidget(id="command_details_quick"),
                            id="right_panel_quick"
                        )
                    )
                    yield Vertical(
                        Static("Output:", classes="output-header"),
                        RichLog(id="output_log_quick", highlight=True, markup=True),
                        id="output_panel_quick"
                    )
            
            # Development Tab
            with TabPane("💻 Development", id="development"):
                commands = CommandDatabase.get_commands_by_category("development")
                with Container():
                    yield Horizontal(
                        Vertical(
                            CommandListWidget(commands, id="command_list_dev"),
                            id="left_panel_dev"
                        ),
                        Vertical(
                            CommandDetailsWidget(id="command_details_dev"),
                            id="right_panel_dev"
                        )
                    )
                    yield Vertical(
                        Static("Output:", classes="output-header"),
                        RichLog(id="output_log_dev", highlight=True, markup=True),
                        id="output_panel_dev"
                    )
            
            # Testing Tab
            with TabPane("🧪 Testing", id="testing"):
                commands = CommandDatabase.get_commands_by_category("testing")
                with Container():
                    yield Horizontal(
                        Vertical(
                            CommandListWidget(commands, id="command_list_test"),
                            id="left_panel_test"
                        ),
                        Vertical(
                            CommandDetailsWidget(id="command_details_test"),
                            id="right_panel_test"
                        )
                    )
                    yield Vertical(
                        Static("Output:", classes="output-header"),
                        RichLog(id="output_log_test", highlight=True, markup=True),
                        id="output_panel_test"
                    )
            
            # Deployment Tab
            with TabPane("🚀 Deployment", id="deployment"):
                commands = CommandDatabase.get_commands_by_category("deployment") + \
                          CommandDatabase.get_commands_by_category("setup")
                with Container():
                    yield Horizontal(
                        Vertical(
                            CommandListWidget(commands, id="command_list_deploy"),
                            id="left_panel_deploy"
                        ),
                        Vertical(
                            CommandDetailsWidget(id="command_details_deploy"),
                            id="right_panel_deploy"
                        )
                    )
                    yield Vertical(
                        Static("Output:", classes="output-header"),
                        RichLog(id="output_log_deploy", highlight=True, markup=True),
                        id="output_panel_deploy"
                    )
            
            # Advanced Tab
            with TabPane("⚙️ Advanced", id="advanced"):
                commands = CommandDatabase.get_commands_by_category("utilities") + \
                          CommandDatabase.get_commands_by_category("advanced")
                with Container():
                    yield Horizontal(
                        Vertical(
                            CommandListWidget(commands, id="command_list_advanced"),
                            id="left_panel_advanced"
                        ),
                        Vertical(
                            CommandDetailsWidget(id="command_details_advanced"),
                            id="right_panel_advanced"
                        )
                    )
                    yield Vertical(
                        Static("Output:", classes="output-header"),
                        RichLog(id="output_log_advanced", highlight=True, markup=True),
                        id="output_panel_advanced"
                    )
        
        yield Footer()
    
    def create_command_view(self, commands: List[MakeCommand]) -> Container:
        """Create a view for a set of commands"""
        return Container(
            Horizontal(
                Vertical(
                    CommandListWidget(commands, id="command_list"),
                    id="left_panel"
                ),
                Vertical(
                    CommandDetailsWidget(id="command_details"),
                    id="right_panel"
                )
            ),
            Vertical(
                Static("Output:", classes="output-header"),
                RichLog(id="output_log", highlight=True, markup=True),
                id="output_panel"
            )
        )
    
    def on_mount(self):
        """Initialize the app"""
        self.title = "HIPAA Infrastructure Stack TUI"
        self.sub_title = "Interactive Make Command Interface"
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id and event.button.id.startswith("cmd_"):
            command_name = event.button.id.replace("cmd_", "")
            command = next((cmd for cmd in CommandDatabase.COMMANDS if cmd.name == command_name), None)
            if command:
                self.current_command = command
                # Find the appropriate command_details widget
                details_widget = None
                for tab_id in ["quickstart", "development", "testing", "deployment", "advanced"]:
                    try:
                        details_widget = self.query_one(f"#command_details_{tab_id[:4]}")
                        if details_widget:
                            details_widget.command = command
                            break
                    except:
                        continue
                if not details_widget:
                    try:
                        details_widget = self.query_one("#command_details")
                        details_widget.command = command
                    except:
                        pass
                
                # Also show feedback in output log
                output_log = self.get_active_output_log()
                if output_log:
                    output_log.write(f"[bold yellow]🔍 Selected: {command.name}[/bold yellow] - [dim]Click 'Run Command' to execute[/dim]")
        
        elif event.button.id == "run_selected":
            if self.current_command:
                self.run_command(self.current_command)
            else:
                output_log = self.get_active_output_log()
                if output_log:
                    output_log.write("[bold red]⚠️ No command selected[/bold red]")
    
    def get_active_output_log(self):
        """Get the active output log widget"""
        # Get current tab
        tabbed_content = self.query_one(TabbedContent)
        active_tab = tabbed_content.active
        
        log_map = {
            "quickstart": "#output_log_quick",
            "development": "#output_log_dev", 
            "testing": "#output_log_test",
            "deployment": "#output_log_deploy",
            "advanced": "#output_log_advanced"
        }
        
        try:
            return self.query_one(log_map.get(active_tab, "#output_log_quick"))
        except:
            try:
                return self.query_one("#output_log")
            except:
                return None

    async def run_command(self, command: MakeCommand):
        """Run the selected command"""
        output_log = self.get_active_output_log()
        if not output_log:
            return
            
        # Create runner for this output log
        runner = CommandRunner(output_log)
        
        if command.requires_confirmation:
            # Simple confirmation for now - could be enhanced with modal
            output_log.write(
                f"[yellow]⚠️  This command ({command.name}) requires confirmation. Press Ctrl+C to cancel.\n[/yellow]"
            )
        
        output_log.write(
            f"[bold cyan]🚀 Running: make {command.name}\n[/bold cyan]"
        )
        
        await runner.run_command(command.name)
    
    def action_cancel_command(self):
        """Cancel the current command"""
        pass
    
    def action_quit(self):
        """Quit the application"""
        self.exit()


if __name__ == "__main__":
    app = HipaaTuiApp()
    app.run()