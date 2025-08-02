"""Status monitoring data structures for the TUI."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, List, Any
from datetime import datetime


class StatusType(Enum):
    """Types of status indicators."""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"
    UNKNOWN = "unknown"


@dataclass
class ComponentStatus:
    """Status of a system component."""
    
    name: str
    status: StatusType
    message: str
    details: Optional[str] = None
    last_checked: Optional[datetime] = None
    
    @property
    def icon(self) -> str:
        """Get status icon."""
        icons = {
            StatusType.SUCCESS: "✅",
            StatusType.WARNING: "⚠️",
            StatusType.ERROR: "❌",
            StatusType.INFO: "ℹ️",
            StatusType.UNKNOWN: "❓",
        }
        return icons.get(self.status, "❓")
    
    @property
    def color(self) -> str:
        """Get status color."""
        colors = {
            StatusType.SUCCESS: "#48bb78",
            StatusType.WARNING: "#ed8936",
            StatusType.ERROR: "#f56565",
            StatusType.INFO: "#4299e1",
            StatusType.UNKNOWN: "#718096",
        }
        return colors.get(self.status, "#718096")
    
    @property
    def display_text(self) -> str:
        """Get formatted display text."""
        return f"{self.icon} {self.name}: {self.message}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComponentStatus":
        """Create from dictionary."""
        last_checked = None
        if data.get("last_checked"):
            last_checked = datetime.fromisoformat(data["last_checked"])
        
        return cls(
            name=data["name"],
            status=StatusType(data["status"]),
            message=data["message"],
            details=data.get("details"),
            last_checked=last_checked,
        )


@dataclass
class SystemStatus:
    """Overall system status information."""
    
    # Core components
    repository: ComponentStatus
    aws: ComponentStatus
    pulumi: ComponentStatus
    docker: ComponentStatus
    
    # Additional components
    components: Dict[str, ComponentStatus]
    
    # Metadata
    last_updated: datetime
    refresh_interval: int = 30  # seconds
    
    def __post_init__(self):
        """Initialize default values."""
        if self.components is None:
            self.components = {}
    
    @property
    def overall_status(self) -> StatusType:
        """Get overall system status."""
        all_statuses = [
            self.repository.status,
            self.aws.status,
            self.pulumi.status,
            self.docker.status,
        ] + [comp.status for comp in self.components.values()]
        
        # If any component has an error, overall is error
        if StatusType.ERROR in all_statuses:
            return StatusType.ERROR
        
        # If any component has a warning, overall is warning
        if StatusType.WARNING in all_statuses:
            return StatusType.WARNING
        
        # If any component is unknown, overall is unknown
        if StatusType.UNKNOWN in all_statuses:
            return StatusType.UNKNOWN
        
        # Otherwise, overall is success
        return StatusType.SUCCESS
    
    @property
    def status_summary(self) -> str:
        """Get status summary text."""
        core_components = [
            self.repository,
            self.aws,
            self.pulumi,
            self.docker,
        ]
        
        status_parts = []
        for comp in core_components:
            status_parts.append(f"{comp.name} {comp.icon}")
        
        # Add timestamp
        time_str = self.last_updated.strftime("%H:%M")
        status_parts.append(time_str)
        
        return " | ".join(status_parts)
    
    def get_component(self, name: str) -> Optional[ComponentStatus]:
        """Get component status by name."""
        core_components = {
            "repository": self.repository,
            "aws": self.aws,
            "pulumi": self.pulumi,
            "docker": self.docker,
        }
        
        return core_components.get(name) or self.components.get(name)
    
    def add_component(self, name: str, component: ComponentStatus) -> None:
        """Add or update a component status."""
        self.components[name] = component
    
    def remove_component(self, name: str) -> None:
        """Remove a component status."""
        if name in self.components:
            del self.components[name]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "repository": self.repository.to_dict(),
            "aws": self.aws.to_dict(),
            "pulumi": self.pulumi.to_dict(),
            "docker": self.docker.to_dict(),
            "components": {name: comp.to_dict() for name, comp in self.components.items()},
            "last_updated": self.last_updated.isoformat(),
            "refresh_interval": self.refresh_interval,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemStatus":
        """Create from dictionary."""
        return cls(
            repository=ComponentStatus.from_dict(data["repository"]),
            aws=ComponentStatus.from_dict(data["aws"]),
            pulumi=ComponentStatus.from_dict(data["pulumi"]),
            docker=ComponentStatus.from_dict(data["docker"]),
            components={
                name: ComponentStatus.from_dict(comp_data)
                for name, comp_data in data.get("components", {}).items()
            },
            last_updated=datetime.fromisoformat(data["last_updated"]),
            refresh_interval=data.get("refresh_interval", 30),
        )
    
    @classmethod
    def create_default(cls) -> "SystemStatus":
        """Create default status with unknown states."""
        now = datetime.now()
        
        return cls(
            repository=ComponentStatus(
                name="Repo",
                status=StatusType.UNKNOWN,
                message="Checking...",
                last_checked=now,
            ),
            aws=ComponentStatus(
                name="AWS",
                status=StatusType.UNKNOWN,
                message="Checking...",
                last_checked=now,
            ),
            pulumi=ComponentStatus(
                name="Pulumi",
                status=StatusType.UNKNOWN,
                message="Checking...",
                last_checked=now,
            ),
            docker=ComponentStatus(
                name="Docker",
                status=StatusType.UNKNOWN,
                message="Checking...",
                last_checked=now,
            ),
            components={},
            last_updated=now,
        )