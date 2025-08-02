"""Command data structures for the TUI."""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime


class CommandStatus(Enum):
    """Status of command execution."""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


class CommandCategory(Enum):
    """Categories for organizing commands."""
    DEVELOPMENT = "development"
    INFRASTRUCTURE = "infrastructure"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    UTILITIES = "utilities"
    CLEANUP = "cleanup"
    EMERGENCY = "emergency"


@dataclass
class Command:
    """Represents a Make command."""
    
    # Basic command information
    name: str
    description: str
    target: str
    category: CommandCategory
    
    # Command properties
    is_dangerous: bool = False
    requires_confirmation: bool = False
    is_favorite: bool = False
    priority: int = 0  # Higher numbers = higher priority
    
    # Environment-specific
    environment: Optional[str] = None  # dev, staging, prod
    
    # Execution state
    status: CommandStatus = CommandStatus.IDLE
    last_run: Optional[datetime] = None
    duration: Optional[float] = None  # seconds
    exit_code: Optional[int] = None
    
    # Visual properties
    icon: str = "•"
    color: str = "#ffffff"
    
    # Additional metadata
    tags: List[str] = None
    dependencies: List[str] = None  # Other commands that should run first
    
    def __post_init__(self):
        """Initialize default values."""
        if self.tags is None:
            self.tags = []
        if self.dependencies is None:
            self.dependencies = []
    
    @property
    def display_name(self) -> str:
        """Get formatted display name with icon."""
        return f"{self.icon} {self.name}"
    
    @property
    def status_icon(self) -> str:
        """Get status icon."""
        icons = {
            CommandStatus.IDLE: "○",
            CommandStatus.RUNNING: "●",
            CommandStatus.SUCCESS: "✓",
            CommandStatus.ERROR: "✗",
            CommandStatus.CANCELLED: "⊘",
        }
        return icons.get(self.status, "○")
    
    @property
    def full_command(self) -> str:
        """Get the full make command."""
        return f"make {self.target}"
    
    def matches_filter(self, filter_text: str) -> bool:
        """Check if command matches filter text."""
        if not filter_text:
            return True
        
        filter_text = filter_text.lower()
        
        # Search in name, description, and tags
        searchable_text = " ".join([
            self.name.lower(),
            self.description.lower(),
            " ".join(self.tags).lower(),
            self.target.lower(),
        ])
        
        return filter_text in searchable_text
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "target": self.target,
            "category": self.category.value,
            "is_dangerous": self.is_dangerous,
            "requires_confirmation": self.requires_confirmation,
            "is_favorite": self.is_favorite,
            "priority": self.priority,
            "environment": self.environment,
            "status": self.status.value,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "duration": self.duration,
            "exit_code": self.exit_code,
            "icon": self.icon,
            "color": self.color,
            "tags": self.tags,
            "dependencies": self.dependencies,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Command":
        """Create from dictionary."""
        # Handle datetime parsing
        last_run = None
        if data.get("last_run"):
            last_run = datetime.fromisoformat(data["last_run"])
        
        return cls(
            name=data["name"],
            description=data["description"],
            target=data["target"],
            category=CommandCategory(data["category"]),
            is_dangerous=data.get("is_dangerous", False),
            requires_confirmation=data.get("requires_confirmation", False),
            is_favorite=data.get("is_favorite", False),
            priority=data.get("priority", 0),
            environment=data.get("environment"),
            status=CommandStatus(data.get("status", "idle")),
            last_run=last_run,
            duration=data.get("duration"),
            exit_code=data.get("exit_code"),
            icon=data.get("icon", "•"),
            color=data.get("color", "#ffffff"),
            tags=data.get("tags", []),
            dependencies=data.get("dependencies", []),
        )


def get_category_info(category: CommandCategory) -> Dict[str, str]:
    """Get display information for a command category."""
    category_info = {
        CommandCategory.DEVELOPMENT: {
            "name": "🔧 Development",
            "description": "Development environment and tools",
            "color": "#4299e1",
        },
        CommandCategory.INFRASTRUCTURE: {
            "name": "🏗️ Infrastructure",
            "description": "Infrastructure deployment and management",
            "color": "#ed8936",
        },
        CommandCategory.TESTING: {
            "name": "🧪 Testing",
            "description": "Test execution and quality checks",
            "color": "#48bb78",
        },
        CommandCategory.DEPLOYMENT: {
            "name": "🚀 Deployment",
            "description": "Application and infrastructure deployment",
            "color": "#9f7aea",
        },
        CommandCategory.MONITORING: {
            "name": "📊 Monitoring",
            "description": "Status monitoring and diagnostics",
            "color": "#38b2ac",
        },
        CommandCategory.UTILITIES: {
            "name": "🔧 Utilities",
            "description": "Utility commands and tools",
            "color": "#718096",
        },
        CommandCategory.CLEANUP: {
            "name": "🧹 Cleanup",
            "description": "Resource cleanup and maintenance",
            "color": "#f56565",
        },
        CommandCategory.EMERGENCY: {
            "name": "🚨 Emergency",
            "description": "Emergency and recovery commands",
            "color": "#e53e3e",
        },
    }
    
    return category_info.get(category, {
        "name": category.value.title(),
        "description": f"{category.value.title()} commands",
        "color": "#ffffff",
    })