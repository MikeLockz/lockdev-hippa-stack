"""Status bar component for the TUI."""

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static
from textual.reactive import reactive
from textual.containers import Horizontal
from datetime import datetime
from typing import Optional

from ..models.status import SystemStatus, StatusType


class StatusBar(Widget):
    """Top status bar showing system status."""
    
    DEFAULT_CSS = """
    StatusBar {
        dock: top;
        height: 1;
        background: #1e1e2e;
        color: #cdd6f4;
        border-bottom: tall #45475a;
    }
    
    StatusBar Horizontal {
        height: 1;
        align: center middle;
    }
    
    StatusBar .status-item {
        padding: 0 1;
        height: 1;
    }
    
    StatusBar .status-success {
        color: #a6e3a1;
    }
    
    StatusBar .status-warning {
        color: #fab387;
    }
    
    StatusBar .status-error {
        color: #f38ba8;
    }
    
    StatusBar .status-info {
        color: #89dceb;
    }
    
    StatusBar .status-unknown {
        color: #6c7086;
    }
    
    StatusBar .separator {
        color: #6c7086;
        margin: 0 1;
    }
    """
    
    # Reactive attributes
    system_status: reactive[Optional[SystemStatus]] = reactive(None)
    
    def __init__(self, **kwargs):
        """Initialize status bar."""
        super().__init__(**kwargs)
        self.refresh_timer = None
        
    def compose(self) -> ComposeResult:
        """Compose the status bar layout."""
        with Horizontal():
            yield Static("HIPAA Infrastructure Stack TUI", classes="title")
            yield Static("|", classes="separator")
            yield Static("Loading...", id="repo-status", classes="status-item status-unknown")
            yield Static("|", classes="separator")
            yield Static("Loading...", id="aws-status", classes="status-item status-unknown")
            yield Static("|", classes="separator")
            yield Static("Loading...", id="pulumi-status", classes="status-item status-unknown")
            yield Static("|", classes="separator")
            yield Static("Loading...", id="docker-status", classes="status-item status-unknown")
            yield Static("|", classes="separator")
            yield Static("--:--", id="time-status", classes="status-item")
    
    def watch_system_status(self, old_status: Optional[SystemStatus], new_status: Optional[SystemStatus]) -> None:
        """React to system status changes."""
        if new_status is None:
            self._update_loading_state()
        else:
            self._update_status_display(new_status)
    
    def _update_loading_state(self) -> None:
        """Update display to show loading state."""
        components = ["repo-status", "aws-status", "pulumi-status", "docker-status"]
        
        for comp_id in components:
            widget = self.query_one(f"#{comp_id}", Static)
            widget.update("Loading...")
            widget.remove_class("status-success", "status-warning", "status-error", "status-info")
            widget.add_class("status-unknown")
    
    def _update_status_display(self, status: SystemStatus) -> None:
        """Update status display with current system status."""
        # Update individual components
        self._update_component_display("repo-status", status.repository)
        self._update_component_display("aws-status", status.aws)
        self._update_component_display("pulumi-status", status.pulumi)
        self._update_component_display("docker-status", status.docker)
        
        # Update timestamp
        time_widget = self.query_one("#time-status", Static)
        time_str = status.last_updated.strftime("%H:%M")
        time_widget.update(time_str)
    
    def _update_component_display(self, widget_id: str, component_status) -> None:
        """Update individual component display."""
        widget = self.query_one(f"#{widget_id}", Static)
        
        # Create display text
        display_text = f"{component_status.name} {component_status.icon}"
        widget.update(display_text)
        
        # Update CSS classes
        widget.remove_class("status-success", "status-warning", "status-error", "status-info", "status-unknown")
        
        status_class = f"status-{component_status.status.value}"
        widget.add_class(status_class)
    
    def update_status(self, status: SystemStatus) -> None:
        """Update the status bar with new system status."""
        self.system_status = status
    
    def set_loading(self, component: Optional[str] = None) -> None:
        """Set loading state for specific component or all."""
        if component:
            widget = self.query_one(f"#{component}-status", Static)
            widget.update("Loading...")
            widget.remove_class("status-success", "status-warning", "status-error", "status-info")
            widget.add_class("status-unknown")
        else:
            self._update_loading_state()
    
    def set_error(self, component: str, message: str) -> None:
        """Set error state for specific component."""
        widget = self.query_one(f"#{component}-status", Static)
        widget.update(f"{component.title()} ❌")
        widget.remove_class("status-success", "status-warning", "status-info", "status-unknown")
        widget.add_class("status-error")
    
    def on_mount(self) -> None:
        """Handle mount event."""
        # Start with default loading state
        self._update_loading_state()
        
        # Update time every minute
        self.set_interval(60, self._update_time)
    
    def _update_time(self) -> None:
        """Update the time display."""
        time_widget = self.query_one("#time-status", Static)
        current_time = datetime.now().strftime("%H:%M")
        time_widget.update(current_time)