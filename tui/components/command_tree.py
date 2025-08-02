"""Command tree component for the TUI."""

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Tree, Input, Static
from textual.containers import Vertical
from textual.reactive import reactive
from textual.message import Message
from typing import List, Dict, Optional, Any
from rich.text import Text

from ..models.command import Command, CommandCategory, get_category_info
from ..services.makefile_parser import MakefileParser


class CommandTree(Widget):
    """Left panel command tree widget."""
    
    DEFAULT_CSS = """
    CommandTree {
        dock: left;
        width: 30%;
        background: #1e1e2e;
        border-right: tall #45475a;
    }
    
    CommandTree Input {
        dock: top;
        height: 3;
        margin: 1;
        border: tall #45475a;
        background: #11111b;
        color: #cdd6f4;
    }
    
    CommandTree Tree {
        scrollbar-gutter: stable;
        margin: 0 1;
        background: #1e1e2e;
        color: #cdd6f4;
    }
    
    CommandTree .tree-node {
        padding: 0 1;
    }
    
    CommandTree .category-node {
        text-style: bold;
        color: #89b4fa;
    }
    
    CommandTree .command-node {
        color: #cdd6f4;
    }
    
    CommandTree .command-dangerous {
        color: #f38ba8;
    }
    
    CommandTree .command-favorite {
        text-style: bold;
        color: #a6e3a1;
    }
    
    CommandTree .command-running {
        color: #fab387;
        text-style: bold;
    }
    """
    
    # Reactive attributes
    commands: reactive[List[Command]] = reactive([])
    filter_text: reactive[str] = reactive("")
    selected_command: reactive[Optional[Command]] = reactive(None)
    
    class CommandSelected(Message):
        """Message sent when a command is selected."""
        
        def __init__(self, command: Command) -> None:
            self.command = command
            super().__init__()
    
    class CommandExecute(Message):
        """Message sent when a command should be executed."""
        
        def __init__(self, command: Command) -> None:
            self.command = command
            super().__init__()
    
    def __init__(self, makefile_parser: Optional[MakefileParser] = None, **kwargs):
        """Initialize command tree."""
        super().__init__(**kwargs)
        self.parser = makefile_parser or MakefileParser()
        self.tree_data: Dict[str, Any] = {}
        
    def compose(self) -> ComposeResult:
        """Compose the command tree layout."""
        with Vertical():
            yield Input(placeholder="Search commands...", id="search-input")
            yield Tree("Make Commands", id="command-tree")
    
    def on_mount(self) -> None:
        """Handle mount event."""
        # Load commands from Makefile
        self.refresh_commands()
        
        # Set up tree
        tree = self.query_one("#command-tree", Tree)
        tree.show_root = False
        tree.show_guides = True
        
    def refresh_commands(self) -> None:
        """Refresh commands from Makefile."""
        try:
            commands = self.parser.parse(force_refresh=True)
            self.commands = commands
            self._rebuild_tree()
        except Exception as e:
            # Show error in tree
            tree = self.query_one("#command-tree", Tree)
            tree.clear()
            error_node = tree.root.add("❌ Error loading commands")
            error_node.add_leaf(str(e))
    
    def watch_commands(self, old_commands: List[Command], new_commands: List[Command]) -> None:
        """React to commands changes."""
        self._rebuild_tree()
    
    def watch_filter_text(self, old_filter: str, new_filter: str) -> None:
        """React to filter text changes."""
        self._rebuild_tree()
    
    def _rebuild_tree(self) -> None:
        """Rebuild the command tree."""
        tree = self.query_one("#command-tree", Tree)
        tree.clear()
        
        if not self.commands:
            no_commands_node = tree.root.add("📁 No commands found")
            no_commands_node.add_leaf("Check Makefile in current directory")
            return
        
        # Filter commands if search text exists
        filtered_commands = self.commands
        if self.filter_text:
            filtered_commands = [
                cmd for cmd in self.commands 
                if cmd.matches_filter(self.filter_text)
            ]
        
        # Group commands by category
        categorized = self._group_by_category(filtered_commands)
        
        # Add favorites first if any
        favorites = [cmd for cmd in filtered_commands if cmd.is_favorite]
        if favorites:
            fav_node = tree.root.add("⭐ Favorites")
            fav_node.data = {"type": "category", "category": "favorites"}
            for command in favorites:
                self._add_command_node(fav_node, command)
            fav_node.expand()
        
        # Add categories
        for category, commands_in_category in categorized.items():
            if not commands_in_category:
                continue
                
            category_info = get_category_info(category)
            category_node = tree.root.add(category_info["name"])
            category_node.data = {"type": "category", "category": category}
            
            # Sort commands by priority within category
            sorted_commands = sorted(commands_in_category, key=lambda c: (-c.priority, c.name))
            
            for command in sorted_commands:
                self._add_command_node(category_node, command)
            
            # Expand high-priority categories
            if category in [CommandCategory.DEVELOPMENT, CommandCategory.INFRASTRUCTURE]:
                category_node.expand()
    
    def _group_by_category(self, commands: List[Command]) -> Dict[CommandCategory, List[Command]]:
        """Group commands by category."""
        categorized = {}
        for category in CommandCategory:
            categorized[category] = [cmd for cmd in commands if cmd.category == category]
        return categorized
    
    def _add_command_node(self, parent_node, command: Command) -> None:
        """Add a command node to the tree."""
        # Create display text with status
        display_text = f"{command.icon} {command.name}"
        if command.status.value != "idle":
            display_text += f" {command.status_icon}"
        
        command_node = parent_node.add_leaf(display_text)
        command_node.data = {
            "type": "command",
            "command": command,
        }
        
        # Add description as tooltip/data
        if command.description:
            command_node.data["description"] = command.description
    
    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        if event.node.data and event.node.data.get("type") == "command":
            command = event.node.data["command"]
            self.selected_command = command
            # Send selection message
            self.post_message(self.CommandSelected(command))
    
    def on_key(self, event) -> None:
        """Handle key events for command execution."""
        if event.key == "enter":
            # Execute selected command on Enter
            if self.selected_command:
                self.post_message(self.CommandExecute(self.selected_command))
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search-input":
            self.filter_text = event.value
    
    def update_command_status(self, command_target: str, status: str) -> None:
        """Update the status of a command in the tree."""
        # Find and update the command
        for command in self.commands:
            if command.target == command_target:
                command.status = status
                break
        
        # Rebuild tree to show updated status
        self._rebuild_tree()
    
    def get_selected_command(self) -> Optional[Command]:
        """Get currently selected command."""
        return self.selected_command
    
    def select_command(self, command_target: str) -> bool:
        """Select a command by target name."""
        tree = self.query_one("#command-tree", Tree)
        
        # Find the command node
        for node in tree.walk_children():
            if (node.data and 
                node.data.get("type") == "command" and 
                node.data["command"].target == command_target):
                tree.select_node(node)
                return True
        
        return False
    
    def clear_filter(self) -> None:
        """Clear the search filter."""
        search_input = self.query_one("#search-input", Input)
        search_input.value = ""
        self.filter_text = ""
    
    def focus_search(self) -> None:
        """Focus the search input."""
        search_input = self.query_one("#search-input", Input)
        search_input.focus()