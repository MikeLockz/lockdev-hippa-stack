"""Main TUI application for HIPAA Infrastructure Stack."""

from textual.app import App, ComposeResult
from textual.widgets import Footer
from textual.containers import Container
from textual.binding import Binding
from textual.screen import Screen
from textual import events
from typing import Optional
import asyncio

from .components.status_bar import StatusBar
from .components.command_tree import CommandTree
from .components.output_pane import OutputPane
from .models.command import Command
from .models.status import SystemStatus
from .services.makefile_parser import MakefileParser
from .themes.dark import DarkTheme


class TUIScreen(Screen):
    """Main TUI screen with three-panel layout."""
    
    CSS = """
    Container {
        layout: grid;
        grid-size: 2 3;
        grid-rows: auto 1fr auto;
        grid-columns: 30% 1fr;
    }
    
    StatusBar {
        column-span: 2;
        row-span: 1;
    }
    
    CommandTree {
        row-span: 1;
        column-span: 1;
    }
    
    OutputPane {
        row-span: 1;
        column-span: 1;
    }
    
    Footer {
        column-span: 2;
        row-span: 1;
    }
    """
    
    def __init__(self, makefile_parser: Optional[MakefileParser] = None, **kwargs):
        """Initialize TUI screen."""
        super().__init__(**kwargs)
        self.parser = makefile_parser or MakefileParser()
        self.status_bar: Optional[StatusBar] = None
        self.command_tree: Optional[CommandTree] = None
        self.output_pane: Optional[OutputPane] = None
        
    def compose(self) -> ComposeResult:
        """Compose the main layout."""
        with Container():
            self.status_bar = StatusBar()
            yield self.status_bar
            
            self.command_tree = CommandTree(makefile_parser=self.parser)
            yield self.command_tree
            
            self.output_pane = OutputPane()
            yield self.output_pane
            
            yield Footer()
    
    def on_mount(self) -> None:
        """Handle screen mount."""
        # Initialize with default status
        default_status = SystemStatus.create_default()
        if self.status_bar:
            self.status_bar.update_status(default_status)
    
    def on_command_tree_command_selected(self, event: CommandTree.CommandSelected) -> None:
        """Handle command selection from tree."""
        if self.output_pane:
            self.output_pane.set_command(event.command)
    
    def on_command_tree_command_execute(self, event: CommandTree.CommandExecute) -> None:
        """Handle command execution request."""
        if self.output_pane:
            # For now, just show that we would execute the command
            self.output_pane.write_command_start(event.command)
            self.output_pane.write_info("Command execution not implemented in Phase 1")
            self.output_pane.write_info(f"Would execute: make {event.command.target}")
            self.output_pane.write_command_end(event.command, 0, 0.1)


class HIPAATUIApp(App):
    """Main HIPAA Infrastructure Stack TUI Application."""
    
    TITLE = "HIPAA Infrastructure Stack TUI"
    SUB_TITLE = "Terminal User Interface for Infrastructure Management"
    
    # Key bindings
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("tab", "focus_next", "Next Panel"),
        Binding("shift+tab", "focus_previous", "Previous Panel"),
        Binding("ctrl+l", "clear_output", "Clear Output"),
        Binding("ctrl+r", "refresh_commands", "Refresh Commands"),
        Binding("ctrl+f", "toggle_fullscreen", "Toggle Fullscreen"),
        Binding("/", "focus_search", "Search Commands"),
        Binding("escape", "clear_search", "Clear Search"),
        Binding("f5", "refresh_status", "Refresh Status"),
    ]
    
    CSS_PATH = None  # We'll use inline CSS for now
    
    # App CSS
    CSS = """
    App {
        background: #1e1e2e;
        color: #cdd6f4;
    }
    
    Footer {
        background: #11111b;
        color: #6c7086;
    }
    
    /* Status indicators */
    .status-success {
        color: #a6e3a1;
    }
    
    .status-warning {
        color: #fab387;
    }
    
    .status-error {
        color: #f38ba8;
    }
    
    .status-info {
        color: #89dceb;
    }
    
    .status-unknown {
        color: #6c7086;
    }
    """
    
    def __init__(self, makefile_path: Optional[str] = None, **kwargs):
        """Initialize the TUI application."""
        super().__init__(**kwargs)
        self.parser = MakefileParser(makefile_path) if makefile_path else MakefileParser()
        self.main_screen: Optional[TUIScreen] = None
        
    def compose(self) -> ComposeResult:
        """Compose the main application."""
        # Return empty compose since we use screens for layout
        return []
    
    def on_mount(self) -> None:
        """Handle app mount."""
        # Install and switch to main screen
        self.main_screen = TUIScreen(makefile_parser=self.parser)
        self.install_screen(self.main_screen, name="main")
        self.push_screen("main")
    
    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()
    
    def action_focus_next(self) -> None:
        """Focus next widget (Tab)."""
        self.focus_next()
    
    def action_focus_previous(self) -> None:
        """Focus previous widget (Shift+Tab)."""
        self.focus_previous()
    
    def action_clear_output(self) -> None:
        """Clear the output pane."""
        if self.main_screen and self.main_screen.output_pane:
            self.main_screen.output_pane.clear_output()
    
    def action_refresh_commands(self) -> None:
        """Refresh commands from Makefile."""
        if self.main_screen and self.main_screen.command_tree:
            self.main_screen.command_tree.refresh_commands()
            if self.main_screen.output_pane:
                self.main_screen.output_pane.write_info("Commands refreshed from Makefile")
    
    def action_toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode for output pane."""
        # This would be implemented in Phase 2
        if self.main_screen and self.main_screen.output_pane:
            self.main_screen.output_pane.write_info("Fullscreen mode not implemented in Phase 1")
    
    def action_focus_search(self) -> None:
        """Focus the search input."""
        if self.main_screen and self.main_screen.command_tree:
            self.main_screen.command_tree.focus_search()
    
    def action_clear_search(self) -> None:
        """Clear search filter."""
        if self.main_screen and self.main_screen.command_tree:
            self.main_screen.command_tree.clear_filter()
    
    def action_refresh_status(self) -> None:
        """Refresh status bar."""
        if self.main_screen and self.main_screen.status_bar:
            # Create a new default status (in Phase 3 this would check real systems)
            default_status = SystemStatus.create_default()
            self.main_screen.status_bar.update_status(default_status)
            if self.main_screen.output_pane:
                self.main_screen.output_pane.write_info("Status refreshed")
    
    def on_key(self, event: events.Key) -> None:
        """Handle global key events."""
        # Handle special keys that might need custom behavior
        if event.key == "enter":
            # Enter key should execute command if command tree is focused
            if self.main_screen and self.main_screen.command_tree:
                focused = self.focused
                if focused and hasattr(focused, 'id') and 'command-tree' in str(focused.id):
                    # Let the tree handle it
                    pass
        
    def run_command(self, command: Command) -> None:
        """Run a make command (placeholder for Phase 2)."""
        if self.main_screen and self.main_screen.output_pane:
            self.main_screen.output_pane.write_command_start(command)
            self.main_screen.output_pane.write_info("Command execution will be implemented in Phase 2")
            self.main_screen.output_pane.write_info(f"Command: make {command.target}")
            self.main_screen.output_pane.write_command_end(command, 0, 0.1)


def main():
    """Main entry point for the TUI application."""
    app = HIPAATUIApp()
    app.run()


if __name__ == "__main__":
    main()