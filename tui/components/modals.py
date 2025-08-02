"""Modal dialog components for the TUI."""

from textual import on
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Grid, Horizontal, Vertical
from textual.widgets import Button, Label, Input, Static, TextArea
from textual.binding import Binding
from typing import Optional, Callable, Any

from ..models.command import Command


class ConfirmationModal(ModalScreen[bool]):
    """Modal dialog for confirming dangerous operations."""
    
    DEFAULT_CSS = """
    ConfirmationModal {
        align: center middle;
    }
    
    #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr auto;
        padding: 0 1;
        width: 60;
        height: 11;
        border: thick $background 80%;
        background: $surface;
    }
    
    #question {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
    }
    
    Button {
        width: 100%;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm"),
    ]
    
    def __init__(
        self, 
        title: str = "Confirm Action",
        message: str = "Are you sure?",
        confirm_text: str = "Yes",
        cancel_text: str = "No",
        **kwargs
    ):
        """Initialize confirmation modal."""
        super().__init__(**kwargs)
        self.title = title
        self.message = message
        self.confirm_text = confirm_text
        self.cancel_text = cancel_text
    
    def compose(self) -> ComposeResult:
        """Compose the confirmation dialog."""
        yield Grid(
            Label(self.message, id="question"),
            Button(self.confirm_text, variant="error", id="confirm"),
            Button(self.cancel_text, variant="primary", id="cancel"),
            id="dialog",
        )
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)
    
    def action_confirm(self) -> None:
        """Confirm action."""
        self.dismiss(True)
    
    def action_cancel(self) -> None:
        """Cancel action."""
        self.dismiss(False)


class CommandPreviewModal(ModalScreen[bool]):
    """Modal dialog for previewing command before execution."""
    
    DEFAULT_CSS = """
    CommandPreviewModal {
        align: center middle;
    }
    
    #dialog {
        grid-size: 1;
        grid-gutter: 1;
        grid-rows: auto 1fr auto;
        padding: 1 2;
        width: 80;
        height: 20;
        border: thick $background 80%;
        background: $surface;
    }
    
    #title {
        height: 1;
        width: 1fr;
        content-align: center middle;
        text-style: bold;
    }
    
    #command-info {
        height: 1fr;
        width: 1fr;
        border: solid $background;
        padding: 1;
    }
    
    #buttons {
        height: 3;
        width: 1fr;
    }
    
    Button {
        margin: 0 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "execute", "Execute"),
        Binding("ctrl+e", "edit", "Edit Command"),
    ]
    
    def __init__(self, command: Command, **kwargs):
        """Initialize command preview modal."""
        super().__init__(**kwargs)
        self.command = command
    
    def compose(self) -> ComposeResult:
        """Compose the command preview dialog."""
        with Grid(id="dialog"):
            yield Label(f"Execute Command: {self.command.name}", id="title")
            
            with Vertical(id="command-info"):
                yield Static(f"[bold]Target:[/bold] {self.command.target}")
                yield Static(f"[bold]Description:[/bold] {self.command.description}")
                yield Static(f"[bold]Category:[/bold] {self.command.category.value}")
                if self.command.environment:
                    yield Static(f"[bold]Environment:[/bold] {self.command.environment}")
                if self.command.is_dangerous:
                    yield Static("[bold red]⚠️  This is a dangerous operation[/bold red]")
                yield Static("")
                yield Static(f"[bold]Command to execute:[/bold] make {self.command.target}")
            
            with Horizontal(id="buttons"):
                yield Button("Execute", variant="success", id="execute")
                yield Button("Edit", variant="default", id="edit")
                yield Button("Cancel", variant="default", id="cancel")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "execute":
            self.dismiss(True)
        elif event.button.id == "edit":
            # TODO: Implement command editing in Phase 2
            self.dismiss(False)
        else:
            self.dismiss(False)
    
    def action_execute(self) -> None:
        """Execute the command."""
        self.dismiss(True)
    
    def action_edit(self) -> None:
        """Edit the command."""
        # TODO: Implement command editing in Phase 2
        self.dismiss(False)
    
    def action_cancel(self) -> None:
        """Cancel execution."""
        self.dismiss(False)


class CommandEditModal(ModalScreen[Optional[str]]):
    """Modal dialog for editing command parameters."""
    
    DEFAULT_CSS = """
    CommandEditModal {
        align: center middle;
    }
    
    #dialog {
        grid-size: 1;
        grid-gutter: 1;
        grid-rows: auto auto 1fr auto;
        padding: 1 2;
        width: 80;
        height: 15;
        border: thick $background 80%;
        background: $surface;
    }
    
    #title {
        height: 1;
        width: 1fr;
        content-align: center middle;
        text-style: bold;
    }
    
    #original-command {
        height: 1;
        width: 1fr;
        content-align: left middle;
    }
    
    #input-container {
        height: 1fr;
        width: 1fr;
        border: solid $background;
    }
    
    #command-input {
        height: 1fr;
        width: 1fr;
        padding: 0 1;
    }
    
    #buttons {
        height: 3;
        width: 1fr;
    }
    
    Button {
        margin: 0 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+enter", "execute", "Execute"),
    ]
    
    def __init__(self, command: Command, **kwargs):
        """Initialize command edit modal."""
        super().__init__(**kwargs)
        self.command = command
        self.original_command = f"make {command.target}"
    
    def compose(self) -> ComposeResult:
        """Compose the command edit dialog."""
        with Grid(id="dialog"):
            yield Label(f"Edit Command: {self.command.name}", id="title")
            yield Static(f"Original: {self.original_command}", id="original-command")
            
            with Vertical(id="input-container"):
                yield Input(
                    value=self.original_command,
                    placeholder="Enter command...",
                    id="command-input"
                )
            
            with Horizontal(id="buttons"):
                yield Button("Execute", variant="success", id="execute")
                yield Button("Cancel", variant="default", id="cancel")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "execute":
            input_widget = self.query_one("#command-input", Input)
            modified_command = input_widget.value.strip()
            if modified_command:
                self.dismiss(modified_command)
            else:
                self.dismiss(None)
        else:
            self.dismiss(None)
    
    def action_execute(self) -> None:
        """Execute the modified command."""
        input_widget = self.query_one("#command-input", Input)
        modified_command = input_widget.value.strip()
        if modified_command:
            self.dismiss(modified_command)
        else:
            self.dismiss(None)
    
    def action_cancel(self) -> None:
        """Cancel editing."""
        self.dismiss(None)


class HelpModal(ModalScreen[None]):
    """Modal dialog for showing help information."""
    
    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    
    #dialog {
        grid-size: 1;
        grid-gutter: 1;
        grid-rows: auto 1fr auto;
        padding: 1 2;
        width: 90;
        height: 30;
        border: thick $background 80%;
        background: $surface;
    }
    
    #title {
        height: 1;
        width: 1fr;
        content-align: center middle;
        text-style: bold;
    }
    
    #help-content {
        height: 1fr;
        width: 1fr;
        border: solid $background;
        padding: 1;
    }
    
    #close-button {
        height: 3;
        width: 1fr;
        content-align: center middle;
    }
    
    Button {
        width: 20;
    }
    """
    
    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("enter", "close", "Close"),
        Binding("q", "close", "Close"),
    ]
    
    def __init__(self, command: Optional[Command] = None, **kwargs):
        """Initialize help modal."""
        super().__init__(**kwargs)
        self.command = command
    
    def compose(self) -> ComposeResult:
        """Compose the help dialog."""
        title = f"Help: {self.command.name}" if self.command else "HIPAA TUI Help"
        
        with Grid(id="dialog"):
            yield Label(title, id="title")
            
            with Vertical(id="help-content"):
                if self.command:
                    yield self._compose_command_help()
                else:
                    yield self._compose_general_help()
            
            with Horizontal(id="close-button"):
                yield Button("Close", variant="primary", id="close")
    
    def _compose_command_help(self) -> ComposeResult:
        """Compose command-specific help."""
        if not self.command:
            return
        
        yield Static(f"[bold]Command:[/bold] {self.command.name}")
        yield Static(f"[bold]Target:[/bold] {self.command.target}")
        yield Static(f"[bold]Description:[/bold] {self.command.description}")
        yield Static(f"[bold]Category:[/bold] {self.command.category.value}")
        
        if self.command.environment:
            yield Static(f"[bold]Environment:[/bold] {self.command.environment}")
        
        if self.command.tags:
            yield Static(f"[bold]Tags:[/bold] {', '.join(self.command.tags)}")
        
        if self.command.is_dangerous:
            yield Static("")
            yield Static("[bold red]⚠️  WARNING: This is a dangerous operation[/bold red]")
            yield Static("[red]This command may modify or delete infrastructure.[/red]")
            yield Static("[red]Use with caution in production environments.[/red]")
        
        yield Static("")
        yield Static(f"[bold]Execute with:[/bold] make {self.command.target}")
    
    def _compose_general_help(self) -> ComposeResult:
        """Compose general application help."""
        help_text = """[bold]HIPAA Infrastructure Stack TUI[/bold]

[bold]Navigation:[/bold]
• Tab / Shift+Tab - Navigate between panels
• ↑ / ↓ - Navigate command tree
• Enter - Execute selected command
• / - Search commands
• Escape - Clear search

[bold]Command Actions:[/bold]
• Enter - Execute command (with confirmation if dangerous)
• Ctrl+H - Show command help
• Ctrl+E - Edit command before execution

[bold]Interface:[/bold]
• Ctrl+L - Clear output pane
• Ctrl+R - Refresh commands from Makefile
• Ctrl+F - Toggle fullscreen mode (Phase 2)
• F5 - Refresh status bar

[bold]Application:[/bold]
• Q / Ctrl+C - Quit application

[bold]Status Bar:[/bold]
Shows real-time status of:
• Repository setup
• AWS connection
• Pulumi state
• Docker/containers
• Current time

[bold]Command Categories:[/bold]
• 🔧 Development - Setup, install, dev environment
• 🏗️ Infrastructure - Deploy, preview, infrastructure
• 🧪 Testing - Tests, linting, quality checks
• 🚀 Deployment - Production deployments
• 📊 Monitoring - Status, diagrams, validation
• 🧹 Cleanup - Resource cleanup and destruction
• 🚨 Emergency - Emergency operations and recovery"""
        
        yield Static(help_text)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        self.dismiss()
    
    def action_close(self) -> None:
        """Close the help modal."""
        self.dismiss()


class ParameterInputModal(ModalScreen[Optional[dict]]):
    """Modal dialog for inputting command parameters."""
    
    DEFAULT_CSS = """
    ParameterInputModal {
        align: center middle;
    }
    
    #dialog {
        grid-size: 1;
        grid-gutter: 1;
        grid-rows: auto 1fr auto;
        padding: 1 2;
        width: 70;
        height: 20;
        border: thick $background 80%;
        background: $surface;
    }
    
    #title {
        height: 1;
        width: 1fr;
        content-align: center middle;
        text-style: bold;
    }
    
    #parameters {
        height: 1fr;
        width: 1fr;
        border: solid $background;
        padding: 1;
    }
    
    #buttons {
        height: 3;
        width: 1fr;
    }
    
    Button {
        margin: 0 1;
    }
    
    Input {
        margin: 1 0;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+enter", "submit", "Submit"),
    ]
    
    def __init__(self, command: Command, parameters: list, **kwargs):
        """Initialize parameter input modal."""
        super().__init__(**kwargs)
        self.command = command
        self.parameters = parameters
        self.inputs = {}
    
    def compose(self) -> ComposeResult:
        """Compose the parameter input dialog."""
        with Grid(id="dialog"):
            yield Label(f"Parameters for: {self.command.name}", id="title")
            
            with Vertical(id="parameters"):
                yield Static(f"Command: make {self.command.target}")
                yield Static("")
                
                for param in self.parameters:
                    yield Static(f"[bold]{param['name']}:[/bold] {param.get('description', '')}")
                    input_widget = Input(
                        placeholder=param.get('placeholder', f"Enter {param['name']}..."),
                        id=f"param_{param['name']}"
                    )
                    yield input_widget
                    self.inputs[param['name']] = input_widget
            
            with Horizontal(id="buttons"):
                yield Button("Execute", variant="success", id="execute")
                yield Button("Cancel", variant="default", id="cancel")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "execute":
            # Collect parameter values
            values = {}
            for name, input_widget in self.inputs.items():
                values[name] = input_widget.value.strip()
            self.dismiss(values)
        else:
            self.dismiss(None)
    
    def action_submit(self) -> None:
        """Submit the parameters."""
        values = {}
        for name, input_widget in self.inputs.items():
            values[name] = input_widget.value.strip()
        self.dismiss(values)
    
    def action_cancel(self) -> None:
        """Cancel parameter input."""
        self.dismiss(None)