"""Light theme configuration for the TUI."""

from typing import Dict, Any


class LightTheme:
    """Light theme colors and styles for the TUI application."""
    
    # Base colors - Catppuccin Latte palette
    COLORS = {
        # Background colors
        "base": "#eff1f5",           # Main background
        "mantle": "#e6e9ef",         # Secondary background
        "crust": "#dce0e8",          # Tertiary background
        
        # Surface colors
        "surface0": "#ccd0da",       # Surface background
        "surface1": "#bcc0cc",       # Surface highlight
        "surface2": "#acb0be",       # Surface border
        
        # Text colors
        "text": "#4c4f69",           # Primary text
        "subtext1": "#5c5f77",       # Secondary text
        "subtext0": "#6c6f85",       # Tertiary text
        "overlay2": "#7c7f93",       # Overlay text
        "overlay1": "#8c8fa1",       # Disabled text
        "overlay0": "#9ca0b0",       # Subtle text
        
        # Accent colors
        "blue": "#1e66f5",           # Primary accent
        "lavender": "#7287fd",       # Secondary accent
        "sapphire": "#209fb5",       # Info accent
        "sky": "#04a5e5",            # Link accent
        "teal": "#179299",           # Success accent
        "green": "#40a02b",          # Success
        "yellow": "#df8e1d",         # Warning
        "peach": "#fe640b",          # Warning highlight
        "maroon": "#e64553",         # Error accent
        "red": "#d20f39",            # Error
        "mauve": "#8839ef",          # Special accent
        "pink": "#ea76cb",           # Highlight accent
        "flamingo": "#dd7878",       # Soft accent
        "rosewater": "#dc8a78",      # Warm accent
    }
    
    # Semantic color mappings
    SEMANTIC = {
        "primary": COLORS["blue"],
        "secondary": COLORS["lavender"],
        "success": COLORS["green"],
        "warning": COLORS["yellow"],
        "error": COLORS["red"],
        "info": COLORS["sapphire"],
        "background": COLORS["base"],
        "surface": COLORS["surface0"],
        "text": COLORS["text"],
        "muted": COLORS["subtext1"],
        "border": COLORS["surface2"],
        "accent": COLORS["mauve"],
    }
    
    # Component-specific styles
    CSS_VARIABLES = {
        "primary": COLORS["blue"],
        "secondary": COLORS["lavender"],
        "background": COLORS["base"],
        "surface": COLORS["surface0"],
        "surface-lighten-1": COLORS["surface1"],
        "surface-lighten-2": COLORS["surface2"],
        "surface-darken-1": COLORS["mantle"],
        "surface-darken-2": COLORS["crust"],
        "on-primary": COLORS["crust"],
        "on-secondary": COLORS["crust"],
        "on-background": COLORS["text"],
        "on-surface": COLORS["text"],
        "text": COLORS["text"],
        "text-muted": COLORS["subtext1"],
        "text-disabled": COLORS["overlay1"],
        "border": COLORS["surface2"],
        "border-blurred": COLORS["overlay0"],
        "success": COLORS["green"],
        "error": COLORS["red"],
        "warning": COLORS["yellow"],
        "info": COLORS["sapphire"],
    }
    
    @classmethod
    def get_app_css(cls) -> str:
        """Get main application CSS for light theme."""
        return f"""
        /* Light Theme - Main Application Styles */
        App {{
            background: {cls.COLORS["base"]};
            color: {cls.COLORS["text"]};
        }}
        
        /* Status indicators */
        .status-success {{
            color: {cls.COLORS["green"]};
        }}
        
        .status-warning {{
            color: {cls.COLORS["yellow"]};
        }}
        
        .status-error {{
            color: {cls.COLORS["red"]};
        }}
        
        .status-info {{
            color: {cls.COLORS["sapphire"]};
        }}
        
        .status-unknown {{
            color: {cls.COLORS["overlay1"]};
        }}
        
        /* Interactive elements */
        Button {{
            background: {cls.COLORS["surface0"]};
            color: {cls.COLORS["text"]};
            border: solid {cls.COLORS["surface2"]};
        }}
        
        Button:hover {{
            background: {cls.COLORS["surface1"]};
        }}
        
        Button:focus {{
            border: solid {cls.COLORS["blue"]};
        }}
        
        Button.-primary {{
            background: {cls.COLORS["blue"]};
            color: {cls.COLORS["crust"]};
        }}
        
        Button.-primary:hover {{
            background: {cls.COLORS["lavender"]};
        }}
        
        Button.-success {{
            background: {cls.COLORS["green"]};
            color: {cls.COLORS["crust"]};
        }}
        
        Button.-error {{
            background: {cls.COLORS["red"]};
            color: {cls.COLORS["crust"]};
        }}
        
        Button.-warning {{
            background: {cls.COLORS["yellow"]};
            color: {cls.COLORS["crust"]};
        }}
        
        /* Input elements */
        Input {{
            background: {cls.COLORS["surface0"]};
            color: {cls.COLORS["text"]};
            border: solid {cls.COLORS["surface2"]};
        }}
        
        Input:focus {{
            border: solid {cls.COLORS["blue"]};
        }}
        
        /* Container elements */
        Container {{
            background: {cls.COLORS["base"]};
        }}
        
        /* Tree and list elements */
        Tree {{
            background: {cls.COLORS["mantle"]};
            color: {cls.COLORS["text"]};
            scrollbar-background: {cls.COLORS["surface0"]};
            scrollbar-color: {cls.COLORS["surface2"]};
        }}
        
        Tree > .tree--cursor {{
            background: {cls.COLORS["surface1"]};
        }}
        
        Tree > .tree--highlight {{
            background: {cls.COLORS["surface0"]};
        }}
        
        /* Footer */
        Footer {{
            background: {cls.COLORS["crust"]};
            color: {cls.COLORS["subtext1"]};
        }}
        
        Footer .footer--key {{
            color: {cls.COLORS["blue"]};
            text-style: bold;
        }}
        
        Footer .footer--description {{
            color: {cls.COLORS["subtext0"]};
        }}
        """
    
    @classmethod
    def get_status_bar_css(cls) -> str:
        """Get status bar specific CSS for light theme."""
        return f"""
        /* Light Theme - Status Bar Styles */
        StatusBar {{
            dock: top;
            height: 1;
            background: {cls.COLORS["crust"]};
            color: {cls.COLORS["text"]};
            border-bottom: solid {cls.COLORS["surface2"]};
        }}
        
        StatusBar Horizontal {{
            height: 1;
            align: center middle;
        }}
        
        StatusBar .status-item {{
            padding: 0 1;
            height: 1;
        }}
        
        StatusBar .title {{
            color: {cls.COLORS["blue"]};
            text-style: bold;
        }}
        
        StatusBar .separator {{
            color: {cls.COLORS["overlay0"]};
            margin: 0 1;
        }}
        
        StatusBar .status-success {{
            color: {cls.COLORS["green"]};
        }}
        
        StatusBar .status-warning {{
            color: {cls.COLORS["yellow"]};
        }}
        
        StatusBar .status-error {{
            color: {cls.COLORS["red"]};
        }}
        
        StatusBar .status-info {{
            color: {cls.COLORS["sapphire"]};
        }}
        
        StatusBar .status-unknown {{
            color: {cls.COLORS["overlay1"]};
        }}
        """
    
    @classmethod
    def get_command_tree_css(cls) -> str:
        """Get command tree specific CSS for light theme."""
        return f"""
        /* Light Theme - Command Tree Styles */
        CommandTree {{
            background: {cls.COLORS["mantle"]};
            color: {cls.COLORS["text"]};
            border-right: solid {cls.COLORS["surface2"]};
        }}
        
        CommandTree Tree {{
            background: {cls.COLORS["mantle"]};
            scrollbar-background: {cls.COLORS["surface0"]};
            scrollbar-color: {cls.COLORS["surface2"]};
            scrollbar-color-hover: {cls.COLORS["surface1"]};
        }}
        
        CommandTree Tree:focus {{
            border: solid {cls.COLORS["blue"]};
        }}
        
        /* Tree nodes */
        CommandTree .tree--cursor {{
            background: {cls.COLORS["blue"]};
            color: {cls.COLORS["crust"]};
        }}
        
        CommandTree .tree--highlight {{
            background: {cls.COLORS["surface0"]};
        }}
        
        /* Command categories */
        .command-category {{
            color: {cls.COLORS["mauve"]};
            text-style: bold;
        }}
        
        /* Command types by environment */
        .command-dev {{
            color: {cls.COLORS["blue"]};
        }}
        
        .command-staging {{
            color: {cls.COLORS["yellow"]};
        }}
        
        .command-prod {{
            color: {cls.COLORS["red"]};
        }}
        
        .command-dangerous {{
            color: {cls.COLORS["red"]};
            text-style: bold;
        }}
        
        .command-favorite {{
            color: {cls.COLORS["pink"]};
        }}
        
        /* Search input */
        CommandTree Input {{
            background: {cls.COLORS["surface0"]};
            color: {cls.COLORS["text"]};
            border: solid {cls.COLORS["surface2"]};
            margin: 1;
        }}
        
        CommandTree Input:focus {{
            border: solid {cls.COLORS["blue"]};
        }}
        """
    
    @classmethod
    def get_output_pane_css(cls) -> str:
        """Get output pane specific CSS for light theme."""
        return f"""
        /* Light Theme - Output Pane Styles */
        OutputPane {{
            background: {cls.COLORS["base"]};
            color: {cls.COLORS["text"]};
        }}
        
        OutputPane RichLog {{
            background: {cls.COLORS["base"]};
            color: {cls.COLORS["text"]};
            scrollbar-background: {cls.COLORS["surface0"]};
            scrollbar-color: {cls.COLORS["surface2"]};
            scrollbar-color-hover: {cls.COLORS["surface1"]};
            border: solid {cls.COLORS["surface2"]};
        }}
        
        OutputPane RichLog:focus {{
            border: solid {cls.COLORS["blue"]};
        }}
        
        /* Output message types */
        .output-command {{
            color: {cls.COLORS["blue"]};
            text-style: bold;
        }}
        
        .output-success {{
            color: {cls.COLORS["green"]};
        }}
        
        .output-error {{
            color: {cls.COLORS["red"]};
        }}
        
        .output-warning {{
            color: {cls.COLORS["yellow"]};
        }}
        
        .output-info {{
            color: {cls.COLORS["sapphire"]};
        }}
        
        .output-timestamp {{
            color: {cls.COLORS["overlay1"]};
        }}
        
        .output-progress {{
            color: {cls.COLORS["mauve"]};
        }}
        
        /* Header */
        OutputPane .output-header {{
            background: {cls.COLORS["crust"]};
            color: {cls.COLORS["text"]};
            padding: 0 1;
            text-style: bold;
        }}
        """
    
    @classmethod
    def get_modal_css(cls) -> str:
        """Get modal dialog specific CSS for light theme."""
        return f"""
        /* Light Theme - Modal Dialog Styles */
        ModalScreen {{
            background: {cls.COLORS["base"]} 80%;
        }}
        
        .modal-dialog {{
            background: {cls.COLORS["surface0"]};
            color: {cls.COLORS["text"]};
            border: thick {cls.COLORS["surface2"]};
        }}
        
        .modal-title {{
            background: {cls.COLORS["blue"]};
            color: {cls.COLORS["crust"]};
            text-style: bold;
            text-align: center;
            padding: 1;
        }}
        
        .modal-content {{
            padding: 1;
            background: {cls.COLORS["surface0"]};
        }}
        
        .modal-buttons {{
            background: {cls.COLORS["mantle"]};
            padding: 1;
        }}
        
        /* Modal button overrides */
        .modal-buttons Button {{
            margin: 0 1;
        }}
        
        .modal-buttons Button.-primary {{
            background: {cls.COLORS["blue"]};
            color: {cls.COLORS["crust"]};
        }}
        
        .modal-buttons Button.-error {{
            background: {cls.COLORS["red"]};
            color: {cls.COLORS["crust"]};
        }}
        
        .modal-buttons Button.-success {{
            background: {cls.COLORS["green"]};
            color: {cls.COLORS["crust"]};
        }}
        """
    
    @classmethod
    def get_complete_css(cls) -> str:
        """Get complete CSS for light theme."""
        return "\n".join([
            cls.get_app_css(),
            cls.get_status_bar_css(),
            cls.get_command_tree_css(),
            cls.get_output_pane_css(),
            cls.get_modal_css()
        ])
    
    @classmethod
    def get_colors(cls) -> Dict[str, str]:
        """Get color palette dictionary."""
        return cls.COLORS.copy()
    
    @classmethod
    def get_semantic_colors(cls) -> Dict[str, str]:
        """Get semantic color mappings."""
        return cls.SEMANTIC.copy()
    
    @classmethod
    def get_theme_config(cls) -> Dict[str, Any]:
        """Get complete theme configuration."""
        return {
            "name": "light",
            "display_name": "Light Theme",
            "description": "Clean light theme with Catppuccin Latte colors",
            "colors": cls.get_colors(),
            "semantic": cls.get_semantic_colors(),
            "css": cls.get_complete_css(),
        }