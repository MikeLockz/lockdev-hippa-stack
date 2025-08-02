"""Output pane component for the TUI."""

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static, RichLog
from textual.containers import Vertical
from textual.reactive import reactive
from rich.text import Text
from rich.console import Console
from rich.syntax import Syntax
from typing import Optional, List
from datetime import datetime
import re

from ..models.command import Command


class OutputPane(Widget):
    """Right panel output display widget."""
    
    DEFAULT_CSS = """
    OutputPane {
        background: #181825;
    }
    
    OutputPane .header {
        dock: top;
        height: 3;
        background: #11111b;
        border-bottom: tall #45475a;
        padding: 1;
    }
    
    OutputPane .command-info {
        text-style: bold;
        color: #89b4fa;
    }
    
    OutputPane .command-description {
        color: #6c7086;
        margin-top: 1;
    }
    
    OutputPane RichLog {
        border: none;
        scrollbar-gutter: stable;
        background: #181825;
        color: #cdd6f4;
    }
    
    OutputPane .welcome {
        color: #6c7086;
        text-align: center;
        margin: 2;
    }
    """
    
    # Reactive attributes
    current_command: reactive[Optional[Command]] = reactive(None)
    is_running: reactive[bool] = reactive(False)
    
    def __init__(self, **kwargs):
        """Initialize output pane."""
        super().__init__(**kwargs)
        self.output_buffer: List[str] = []
        self.max_lines = 10000  # Maximum lines in buffer
        
    def compose(self) -> ComposeResult:
        """Compose the output pane layout."""
        with Vertical():
            with Vertical(classes="header"):
                yield Static("No command selected", id="command-header", classes="command-info")
                yield Static("Select a command from the tree to see its description", 
                           id="command-description", classes="command-description")
            yield RichLog(id="output-log", auto_scroll=True, markup=True)
    
    def on_mount(self) -> None:
        """Handle mount event."""
        self._show_welcome_message()
    
    def watch_current_command(self, old_command: Optional[Command], new_command: Optional[Command]) -> None:
        """React to current command changes."""
        self._update_header(new_command)
    
    def watch_is_running(self, old_running: bool, new_running: bool) -> None:
        """React to running state changes."""
        self._update_header(self.current_command)
    
    def _show_welcome_message(self) -> None:
        """Show welcome message in output."""
        log = self.query_one("#output-log", RichLog)
        
        welcome_text = Text()
        welcome_text.append("🖥️  HIPAA Infrastructure Stack TUI\n\n", style="bold cyan")
        welcome_text.append("Welcome to the Terminal User Interface for managing your HIPAA-compliant infrastructure.\n\n", style="dim")
        welcome_text.append("📋 Getting Started:\n", style="bold")
        welcome_text.append("• Use ", style="dim")
        welcome_text.append("Tab", style="bold yellow")
        welcome_text.append(" to navigate between panels\n", style="dim")
        welcome_text.append("• Use ", style="dim")
        welcome_text.append("↑↓", style="bold yellow")
        welcome_text.append(" arrows to navigate commands\n", style="dim")
        welcome_text.append("• Press ", style="dim")
        welcome_text.append("Enter", style="bold yellow")
        welcome_text.append(" to execute selected command\n", style="dim")
        welcome_text.append("• Press ", style="dim")
        welcome_text.append("/", style="bold yellow")
        welcome_text.append(" to search commands\n", style="dim")
        welcome_text.append("• Press ", style="dim")
        welcome_text.append("q", style="bold yellow")
        welcome_text.append(" to quit\n\n", style="dim")
        welcome_text.append("Select a command from the tree to see its description and execute it.\n", style="dim")
        
        log.write(welcome_text)
    
    def _update_header(self, command: Optional[Command]) -> None:
        """Update the header with command information."""
        header = self.query_one("#command-header", Static)
        description = self.query_one("#command-description", Static)
        
        if command is None:
            header.update("No command selected")
            description.update("Select a command from the tree to see its description")
        else:
            # Create header text with status
            header_text = f"{command.icon} {command.name}"
            if self.is_running:
                header_text += " [Running...]"
            elif command.is_dangerous:
                header_text += " [DANGEROUS]"
            
            header.update(header_text)
            
            # Update description
            desc_text = command.description
            if command.environment:
                desc_text += f" (Environment: {command.environment})"
            if command.tags:
                desc_text += f" | Tags: {', '.join(command.tags)}"
            
            description.update(desc_text)
    
    def set_command(self, command: Optional[Command]) -> None:
        """Set the current command."""
        self.current_command = command
    
    def clear_output(self) -> None:
        """Clear the output log."""
        log = self.query_one("#output-log", RichLog)
        log.clear()
        self.output_buffer.clear()
        
        if self.current_command is None:
            self._show_welcome_message()
    
    def write_output(self, text: str, style: Optional[str] = None) -> None:
        """Write text to output with optional styling."""
        log = self.query_one("#output-log", RichLog)
        
        if style:
            rich_text = Text(text, style=style)
        else:
            # Auto-detect and style common patterns
            rich_text = self._style_output_text(text)
        
        log.write(rich_text)
        
        # Add to buffer
        self.output_buffer.append(text)
        
        # Trim buffer if too large
        if len(self.output_buffer) > self.max_lines:
            self.output_buffer = self.output_buffer[-self.max_lines:]
    
    def write_command_start(self, command: Command) -> None:
        """Write command start message."""
        log = self.query_one("#output-log", RichLog)
        
        # Add timestamp and command info
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        start_text = Text()
        start_text.append(f"[{timestamp}] ", style="dim")
        start_text.append("🚀 Executing: ", style="bold green")
        start_text.append(f"make {command.target}\n", style="bold")
        
        if command.description:
            start_text.append(f"📝 {command.description}\n", style="dim")
        
        start_text.append("─" * 60 + "\n", style="dim")
        
        log.write(start_text)
        self.is_running = True
    
    def write_command_end(self, command: Command, exit_code: int, duration: float) -> None:
        """Write command completion message."""
        log = self.query_one("#output-log", RichLog)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        end_text = Text()
        end_text.append("─" * 60 + "\n", style="dim")
        end_text.append(f"[{timestamp}] ", style="dim")
        
        if exit_code == 0:
            end_text.append("✅ Command completed successfully", style="bold green")
        else:
            end_text.append(f"❌ Command failed with exit code {exit_code}", style="bold red")
        
        end_text.append(f" (Duration: {duration:.2f}s)\n\n", style="dim")
        
        log.write(end_text)
        self.is_running = False
    
    def write_error(self, error_message: str) -> None:
        """Write error message."""
        self.write_output(f"❌ Error: {error_message}\n", style="bold red")
    
    def write_warning(self, warning_message: str) -> None:
        """Write warning message."""
        self.write_output(f"⚠️ Warning: {warning_message}\n", style="bold yellow")
    
    def write_info(self, info_message: str) -> None:
        """Write info message."""
        self.write_output(f"ℹ️ {info_message}\n", style="bold blue")
    
    def _style_output_text(self, text: str) -> Text:
        """Apply automatic styling to output text."""
        rich_text = Text()
        
        # Split into lines for line-by-line styling
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            if i > 0:
                rich_text.append('\n')
            
            # Apply styling based on patterns
            if re.match(r'^(ERROR|FAILED|FATAL):', line.upper()):
                rich_text.append(line, style="bold red")
            elif re.match(r'^(WARNING|WARN):', line.upper()):
                rich_text.append(line, style="bold yellow")
            elif re.match(r'^(INFO|NOTE):', line.upper()):
                rich_text.append(line, style="bold blue")
            elif re.match(r'^(SUCCESS|COMPLETED|DONE):', line.upper()):
                rich_text.append(line, style="bold green")
            elif line.startswith('$') or line.startswith('make '):
                # Command lines
                rich_text.append(line, style="bold cyan")
            elif re.search(r'^\s*\+', line):
                # Added lines (like git diff)
                rich_text.append(line, style="green")
            elif re.search(r'^\s*\-', line):
                # Removed lines (like git diff)
                rich_text.append(line, style="red")
            elif '✅' in line or '✓' in line:
                rich_text.append(line, style="green")
            elif '❌' in line or '✗' in line:
                rich_text.append(line, style="red")
            elif '⚠️' in line or '!' in line:
                rich_text.append(line, style="yellow")
            else:
                # Default styling
                rich_text.append(line)
        
        return rich_text
    
    def get_output_buffer(self) -> List[str]:
        """Get the current output buffer."""
        return self.output_buffer.copy()
    
    def search_output(self, query: str) -> List[int]:
        """Search for query in output buffer and return line numbers."""
        matches = []
        query_lower = query.lower()
        
        for i, line in enumerate(self.output_buffer):
            if query_lower in line.lower():
                matches.append(i)
        
        return matches
    
    def scroll_to_top(self) -> None:
        """Scroll output to top."""
        log = self.query_one("#output-log", RichLog)
        log.scroll_home()
    
    def scroll_to_bottom(self) -> None:
        """Scroll output to bottom."""
        log = self.query_one("#output-log", RichLog)
        log.scroll_end()