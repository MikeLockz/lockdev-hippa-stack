"""Dark theme for the TUI."""

from typing import Dict, Any


class DarkTheme:
    """Dark theme configuration for the TUI."""
    
    # Color palette inspired by Catppuccin Mocha
    COLORS = {
        # Base colors
        "surface": "#1e1e2e",
        "background": "#181825", 
        "panel": "#11111b",
        "border": "#45475a",
        
        # Text colors
        "text": "#cdd6f4",
        "text-muted": "#6c7086",
        "text-disabled": "#45475a",
        
        # Accent colors
        "accent": "#89b4fa",
        "accent-light": "#b4befe",
        "accent-dark": "#7287fd",
        
        # Status colors
        "success": "#a6e3a1",
        "warning": "#fab387",
        "error": "#f38ba8",
        "info": "#89dceb",
        
        # Semantic colors
        "primary": "#89b4fa",
        "secondary": "#f5c2e7",
        "danger": "#f38ba8",
        
        # Environment colors
        "dev": "#4299e1",
        "staging": "#ed8936", 
        "prod": "#e53e3e",
        
        # Category colors
        "development": "#4299e1",
        "infrastructure": "#ed8936",
        "testing": "#48bb78",
        "deployment": "#9f7aea",
        "monitoring": "#38b2ac",
        "utilities": "#718096",
        "cleanup": "#f56565",
        "emergency": "#e53e3e",
    }
    
    # CSS variables for use in components
    CSS_VARIABLES = """
    /* Dark theme CSS variables */
    App {
        --surface: #1e1e2e;
        --background: #181825;
        --panel: #11111b;
        --border: #45475a;
        
        --text: #cdd6f4;
        --text-muted: #6c7086;
        --text-disabled: #45475a;
        
        --accent: #89b4fa;
        --accent-light: #b4befe;
        --accent-dark: #7287fd;
        
        --success: #a6e3a1;
        --warning: #fab387;
        --error: #f38ba8;
        --info: #89dceb;
        
        --primary: #89b4fa;
        --secondary: #f5c2e7;
        --danger: #f38ba8;
        
        --dev: #4299e1;
        --staging: #ed8936;
        --prod: #e53e3e;
        
        --development: #4299e1;
        --infrastructure: #ed8936;
        --testing: #48bb78;
        --deployment: #9f7aea;
        --monitoring: #38b2ac;
        --utilities: #718096;
        --cleanup: #f56565;
        --emergency: #e53e3e;
    }
    """
    
    # Component-specific styles
    COMPONENT_STYLES = {
        "status_bar": {
            "background": "var(--surface)",
            "color": "var(--text)",
            "border-bottom": "thick var(--border)",
        },
        
        "command_tree": {
            "background": "var(--surface)",
            "border-right": "thick var(--border)",
        },
        
        "output_pane": {
            "background": "var(--background)",
        },
        
        "input": {
            "background": "var(--panel)",
            "color": "var(--text)",
            "border": "thick var(--border)",
        },
        
        "tree": {
            "background": "var(--surface)",
            "color": "var(--text)",
        },
        
        "log": {
            "background": "var(--background)",
            "color": "var(--text)",
        },
    }
    
    @classmethod
    def get_color(cls, color_name: str) -> str:
        """Get color value by name."""
        return cls.COLORS.get(color_name, "#ffffff")
    
    @classmethod
    def get_css_variables(cls) -> str:
        """Get CSS variables string."""
        return cls.CSS_VARIABLES
    
    @classmethod
    def get_component_style(cls, component_name: str) -> Dict[str, Any]:
        """Get component-specific styles."""
        return cls.COMPONENT_STYLES.get(component_name, {})
    
    @classmethod
    def get_full_css(cls) -> str:
        """Get complete CSS for the dark theme."""
        return f"""
        {cls.CSS_VARIABLES}
        
        /* Global styles */
        App {{
            background: var(--background);
            color: var(--text);
        }}
        
        /* Status indicators */
        .status-success {{
            color: var(--success);
        }}
        
        .status-warning {{
            color: var(--warning);
        }}
        
        .status-error {{
            color: var(--error);
        }}
        
        .status-info {{
            color: var(--info);
        }}
        
        .status-unknown {{
            color: var(--text-muted);
        }}
        
        /* Environment colors */
        .env-dev {{
            color: var(--dev);
        }}
        
        .env-staging {{
            color: var(--staging);
        }}
        
        .env-prod {{
            color: var(--prod);
        }}
        
        /* Category colors */
        .cat-development {{
            color: var(--development);
        }}
        
        .cat-infrastructure {{
            color: var(--infrastructure);
        }}
        
        .cat-testing {{
            color: var(--testing);
        }}
        
        .cat-deployment {{
            color: var(--deployment);
        }}
        
        .cat-monitoring {{
            color: var(--monitoring);
        }}
        
        .cat-utilities {{
            color: var(--utilities);
        }}
        
        .cat-cleanup {{
            color: var(--cleanup);
        }}
        
        .cat-emergency {{
            color: var(--emergency);
        }}
        
        /* Interactive elements */
        Input {{
            background: var(--panel);
            color: var(--text);
            border: thick var(--border);
        }}
        
        Input:focus {{
            border: thick var(--accent);
        }}
        
        Tree {{
            background: var(--surface);
            color: var(--text);
        }}
        
        Tree > .tree--guides {{
            color: var(--border);
        }}
        
        Tree > .tree--guides-hover {{
            color: var(--accent);
        }}
        
        Tree > .tree--guides-selected {{
            color: var(--accent);
        }}
        
        RichLog {{
            background: var(--background);
            color: var(--text);
        }}
        
        Footer {{
            background: var(--panel);
            color: var(--text-muted);
        }}
        
        /* Scrollbars */
        ScrollbarCorner {{
            background: var(--surface);
        }}
        
        Scrollbar {{
            background: var(--surface);
        }}
        
        ScrollbarButton {{
            background: var(--panel);
        }}
        
        ScrollbarButton:hover {{
            background: var(--border);
        }}
        
        ScrollbarThumb {{
            background: var(--border);
        }}
        
        ScrollbarThumb:hover {{
            background: var(--accent);
        }}
        """