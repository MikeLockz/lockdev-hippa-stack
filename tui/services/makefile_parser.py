"""Makefile parser service for extracting commands and descriptions."""

import re
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from ..models.command import Command, CommandCategory


class MakefileParser:
    """Parser for Makefile commands and descriptions."""
    
    def __init__(self, makefile_path: Optional[str] = None):
        """Initialize parser with optional Makefile path."""
        self.makefile_path = makefile_path or self._find_makefile()
        self._commands_cache: Optional[List[Command]] = None
        
        # Category mapping based on command name patterns
        self.category_patterns = {
            CommandCategory.DEVELOPMENT: [
                r"dev-.*", r".*-dev$", r"install.*", r"setup.*", r"verify.*"
            ],
            CommandCategory.INFRASTRUCTURE: [
                r"deploy-.*", r".*-deploy$", r"setup-env.*", r"preview-.*"
            ],
            CommandCategory.TESTING: [
                r"test.*", r"lint.*", r"format.*", r".*-test$"
            ],
            CommandCategory.DEPLOYMENT: [
                r"deploy.*", r".*-deploy$", r"quick-start.*"
            ],
            CommandCategory.MONITORING: [
                r"status.*", r"show-.*", r"list-.*", r"generate-.*", r"validate-.*"
            ],
            CommandCategory.UTILITIES: [
                r"edit-.*", r"create-.*", r"login-.*", r"help.*", r"verify-.*"
            ],
            CommandCategory.CLEANUP: [
                r"clean.*", r".*-clean$", r".*-cleanup$"
            ],
            CommandCategory.EMERGENCY: [
                r"emergency-.*", r"rotate-.*", r"force-.*"
            ],
        }
        
        # Environment detection patterns
        self.environment_patterns = {
            "dev": [r".*-dev$", r"dev-.*"],
            "staging": [r".*-staging$", r"staging-.*"],
            "prod": [r".*-prod$", r"prod-.*", r"production-.*"],
        }
        
        # Dangerous command patterns
        self.dangerous_patterns = [
            r"clean-.*-complete$",
            r"emergency-.*",
            r".*-prod$",
            r"rotate-.*",
            r"force-.*",
        ]
        
        # Command icons based on category and patterns
        self.command_icons = {
            CommandCategory.DEVELOPMENT: "🔧",
            CommandCategory.INFRASTRUCTURE: "🏗️",
            CommandCategory.TESTING: "🧪",
            CommandCategory.DEPLOYMENT: "🚀",
            CommandCategory.MONITORING: "📊",
            CommandCategory.UTILITIES: "🔧",
            CommandCategory.CLEANUP: "🧹",
            CommandCategory.EMERGENCY: "🚨",
        }
    
    def _find_makefile(self) -> str:
        """Find Makefile in current directory or parent directories."""
        current_dir = Path.cwd()
        
        # Look for Makefile in current directory and parents
        for path in [current_dir] + list(current_dir.parents):
            makefile_path = path / "Makefile"
            if makefile_path.exists():
                return str(makefile_path)
        
        raise FileNotFoundError("Makefile not found in current directory or parents")
    
    def parse(self, force_refresh: bool = False) -> List[Command]:
        """Parse Makefile and return list of commands."""
        if self._commands_cache is not None and not force_refresh:
            return self._commands_cache
        
        if not os.path.exists(self.makefile_path):
            return []
        
        commands = []
        
        try:
            with open(self.makefile_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract target definitions with descriptions
            targets = self._extract_targets(content)
            
            for target_name, description in targets.items():
                # Skip internal/special targets
                if self._should_skip_target(target_name):
                    continue
                
                command = self._create_command(target_name, description)
                commands.append(command)
            
            # Sort commands by priority and name
            commands.sort(key=lambda cmd: (-cmd.priority, cmd.name))
            
        except Exception as e:
            print(f"Error parsing Makefile: {e}")
        
        self._commands_cache = commands
        return commands
    
    def _extract_targets(self, content: str) -> Dict[str, str]:
        """Extract target names and descriptions from Makefile content."""
        targets = {}
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            # Look for lines with ## comments (descriptions)
            if '##' in line and ':' in line:
                # Extract target and description
                parts = line.split('##', 1)
                if len(parts) == 2:
                    target_part = parts[0].strip()
                    description = parts[1].strip()
                    
                    # Extract target name (before colon)
                    if ':' in target_part:
                        target_name = target_part.split(':')[0].strip()
                        if target_name and not target_name.startswith('#'):
                            targets[target_name] = description
            
            # Also look for targets followed by comment lines
            elif line.strip().endswith(':') and not line.strip().startswith('#'):
                target_name = line.strip()[:-1].strip()
                description = ""
                
                # Look for comment in next few lines
                for j in range(i + 1, min(i + 3, len(lines))):
                    next_line = lines[j].strip()
                    if next_line.startswith('#') and not next_line.startswith('##'):
                        description = next_line[1:].strip()
                        break
                    elif next_line and not next_line.startswith('\t') and not next_line.startswith(' '):
                        break
                
                if target_name and target_name not in targets:
                    targets[target_name] = description or f"Run {target_name}"
        
        return targets
    
    def _should_skip_target(self, target_name: str) -> bool:
        """Check if target should be skipped."""
        skip_patterns = [
            r"^\..*",  # Hidden targets
            r".*\$\(.*\).*",  # Targets with variables
            r"^_.*",  # Private targets
            r"^PHONY$",  # .PHONY
            r"^default$",  # Default target
            r"^all$",  # All target
        ]
        
        for pattern in skip_patterns:
            if re.match(pattern, target_name):
                return True
        
        return False
    
    def _create_command(self, target_name: str, description: str) -> Command:
        """Create Command object from target information."""
        # Determine category
        category = self._determine_category(target_name)
        
        # Determine environment
        environment = self._determine_environment(target_name)
        
        # Check if dangerous
        is_dangerous = self._is_dangerous_command(target_name)
        
        # Set priority based on patterns
        priority = self._calculate_priority(target_name, category)
        
        # Get icon
        icon = self.command_icons.get(category, "•")
        
        # Set color based on environment or category
        color = self._get_command_color(environment, category)
        
        # Generate tags
        tags = self._generate_tags(target_name, category, environment)
        
        return Command(
            name=target_name.replace('-', ' ').title(),
            description=description,
            target=target_name,
            category=category,
            is_dangerous=is_dangerous,
            requires_confirmation=is_dangerous,
            priority=priority,
            environment=environment,
            icon=icon,
            color=color,
            tags=tags,
        )
    
    def _determine_category(self, target_name: str) -> CommandCategory:
        """Determine command category based on target name."""
        for category, patterns in self.category_patterns.items():
            for pattern in patterns:
                if re.match(pattern, target_name):
                    return category
        
        return CommandCategory.UTILITIES
    
    def _determine_environment(self, target_name: str) -> Optional[str]:
        """Determine environment from target name."""
        for env, patterns in self.environment_patterns.items():
            for pattern in patterns:
                if re.match(pattern, target_name):
                    return env
        
        return None
    
    def _is_dangerous_command(self, target_name: str) -> bool:
        """Check if command is dangerous."""
        for pattern in self.dangerous_patterns:
            if re.match(pattern, target_name):
                return True
        
        return False
    
    def _calculate_priority(self, target_name: str, category: CommandCategory) -> int:
        """Calculate command priority."""
        base_priority = {
            CommandCategory.DEVELOPMENT: 90,
            CommandCategory.INFRASTRUCTURE: 80,
            CommandCategory.TESTING: 70,
            CommandCategory.DEPLOYMENT: 85,
            CommandCategory.MONITORING: 60,
            CommandCategory.UTILITIES: 50,
            CommandCategory.CLEANUP: 40,
            CommandCategory.EMERGENCY: 95,
        }.get(category, 50)
        
        # Boost priority for common commands
        high_priority_patterns = [
            r"help", r"install", r"dev-app", r"test", r"deploy-dev",
            r"status", r"quick-start", r"verify"
        ]
        
        for pattern in high_priority_patterns:
            if re.search(pattern, target_name):
                base_priority += 10
                break
        
        return base_priority
    
    def _get_command_color(self, environment: Optional[str], category: CommandCategory) -> str:
        """Get command color based on environment or category."""
        if environment:
            env_colors = {
                "dev": "#4299e1",
                "staging": "#ed8936",
                "prod": "#e53e3e",
            }
            return env_colors.get(environment, "#ffffff")
        
        category_colors = {
            CommandCategory.DEVELOPMENT: "#4299e1",
            CommandCategory.INFRASTRUCTURE: "#ed8936",
            CommandCategory.TESTING: "#48bb78",
            CommandCategory.DEPLOYMENT: "#9f7aea",
            CommandCategory.MONITORING: "#38b2ac",
            CommandCategory.UTILITIES: "#718096",
            CommandCategory.CLEANUP: "#f56565",
            CommandCategory.EMERGENCY: "#e53e3e",
        }
        
        return category_colors.get(category, "#ffffff")
    
    def _generate_tags(self, target_name: str, category: CommandCategory, environment: Optional[str]) -> List[str]:
        """Generate tags for command."""
        tags = []
        
        # Add category tag
        tags.append(category.value)
        
        # Add environment tag
        if environment:
            tags.append(environment)
        
        # Add special tags based on patterns
        if re.search(r"install|setup", target_name):
            tags.append("setup")
        
        if re.search(r"clean|delete|destroy", target_name):
            tags.append("destructive")
        
        if re.search(r"test", target_name):
            tags.append("testing")
        
        if re.search(r"deploy", target_name):
            tags.append("deployment")
        
        if re.search(r"quick|fast|rapid", target_name):
            tags.append("quick")
        
        return tags
    
    def get_commands_by_category(self, force_refresh: bool = False) -> Dict[CommandCategory, List[Command]]:
        """Get commands organized by category."""
        commands = self.parse(force_refresh)
        
        categorized = {}
        for category in CommandCategory:
            categorized[category] = [
                cmd for cmd in commands if cmd.category == category
            ]
        
        return categorized
    
    def get_favorite_commands(self) -> List[Command]:
        """Get favorite commands."""
        commands = self.parse()
        return [cmd for cmd in commands if cmd.is_favorite]
    
    def search_commands(self, query: str) -> List[Command]:
        """Search commands by query."""
        commands = self.parse()
        return [cmd for cmd in commands if cmd.matches_filter(query)]
    
    def refresh(self) -> List[Command]:
        """Force refresh and return updated commands."""
        return self.parse(force_refresh=True)