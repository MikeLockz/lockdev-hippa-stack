"""Tests for command parsing and management."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from ..models.command import Command, CommandCategory
from ..services.makefile_parser import MakefileParser


class TestCommand:
    """Test Command model."""
    
    def test_command_creation(self):
        """Test creating a command."""
        command = Command(
            name="Test Command",
            description="A test command",
            target="test-target",
            category=CommandCategory.TESTING
        )
        
        assert command.name == "Test Command"
        assert command.description == "A test command"
        assert command.target == "test-target"
        assert command.category == CommandCategory.TESTING
        assert not command.is_dangerous
        assert not command.is_favorite
    
    def test_command_filtering(self):
        """Test command filtering."""
        command = Command(
            name="Deploy Development",
            description="Deploy to development environment",
            target="deploy-dev",
            category=CommandCategory.DEPLOYMENT,
            tags=["deployment", "dev"]
        )
        
        # Test name matching
        assert command.matches_filter("deploy")
        assert command.matches_filter("Development")
        assert command.matches_filter("dev")
        
        # Test description matching
        assert command.matches_filter("environment")
        
        # Test target matching
        assert command.matches_filter("deploy-dev")
        
        # Test tag matching
        assert command.matches_filter("deployment")
        
        # Test no match
        assert not command.matches_filter("production")
    
    def test_dangerous_command(self):
        """Test dangerous command properties."""
        command = Command(
            name="Emergency Clean",
            description="Emergency cleanup",
            target="emergency-clean",
            category=CommandCategory.EMERGENCY,
            is_dangerous=True,
            requires_confirmation=True
        )
        
        assert command.is_dangerous
        assert command.requires_confirmation


class TestMakefileParser:
    """Test Makefile parser functionality."""
    
    def create_test_makefile(self, content: str) -> str:
        """Create a temporary Makefile with given content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='Makefile', delete=False) as f:
            f.write(content)
            return f.name
    
    def test_basic_parsing(self):
        """Test basic Makefile parsing."""
        makefile_content = """
# Basic Makefile for testing

install: ## Install all dependencies
\techo "Installing dependencies"

test: ## Run comprehensive tests
\techo "Running tests"

deploy-dev: ## Deploy to development environment
\techo "Deploying to dev"

clean: ## Clean up temporary files
\techo "Cleaning up"
"""
        
        makefile_path = self.create_test_makefile(makefile_content)
        
        try:
            parser = MakefileParser(makefile_path)
            commands = parser.parse()
            
            # Should have 4 commands
            assert len(commands) >= 4
            
            # Check specific commands
            command_targets = [cmd.target for cmd in commands]
            assert "install" in command_targets
            assert "test" in command_targets
            assert "deploy-dev" in command_targets
            assert "clean" in command_targets
            
            # Check command details
            install_cmd = next(cmd for cmd in commands if cmd.target == "install")
            assert install_cmd.description == "Install all dependencies"
            assert install_cmd.category == CommandCategory.DEVELOPMENT
            
            deploy_cmd = next(cmd for cmd in commands if cmd.target == "deploy-dev")
            assert deploy_cmd.environment == "dev"
            assert deploy_cmd.category == CommandCategory.INFRASTRUCTURE
            
        finally:
            os.unlink(makefile_path)
    
    def test_category_detection(self):
        """Test command category detection."""
        makefile_content = """
dev-app: ## Start development application
\techo "Starting dev app"

test-unit: ## Run unit tests
\techo "Running unit tests"

deploy-prod: ## Deploy to production
\techo "Deploying to production"

clean-all: ## Clean all resources
\techo "Cleaning all"

emergency-stop: ## Emergency stop all services
\techo "Emergency stop"

generate-diagrams: ## Generate architecture diagrams
\techo "Generating diagrams"
"""
        
        makefile_path = self.create_test_makefile(makefile_content)
        
        try:
            parser = MakefileParser(makefile_path)
            commands = parser.parse()
            
            # Check categories
            categories = {cmd.target: cmd.category for cmd in commands}
            
            assert categories["dev-app"] == CommandCategory.DEVELOPMENT
            assert categories["test-unit"] == CommandCategory.TESTING
            assert categories["deploy-prod"] in [CommandCategory.DEPLOYMENT, CommandCategory.INFRASTRUCTURE]
            assert categories["clean-all"] == CommandCategory.CLEANUP
            assert categories["emergency-stop"] == CommandCategory.EMERGENCY
            assert categories["generate-diagrams"] == CommandCategory.MONITORING
            
        finally:
            os.unlink(makefile_path)
    
    def test_environment_detection(self):
        """Test environment detection from command names."""
        makefile_content = """
deploy-dev: ## Deploy development
\techo "Deploy dev"

deploy-staging: ## Deploy staging
\techo "Deploy staging"

deploy-prod: ## Deploy production
\techo "Deploy prod"

test-dev: ## Test development
\techo "Test dev"
"""
        
        makefile_path = self.create_test_makefile(makefile_content)
        
        try:
            parser = MakefileParser(makefile_path)
            commands = parser.parse()
            
            environments = {cmd.target: cmd.environment for cmd in commands}
            
            assert environments["deploy-dev"] == "dev"
            assert environments["deploy-staging"] == "staging"
            assert environments["deploy-prod"] == "prod"
            assert environments["test-dev"] == "dev"
            
        finally:
            os.unlink(makefile_path)
    
    def test_dangerous_command_detection(self):
        """Test dangerous command detection."""
        makefile_content = """
clean-prod: ## Clean production resources
\techo "Cleaning prod"

emergency-shutdown: ## Emergency shutdown
\techo "Emergency shutdown"

rotate-keys: ## Rotate AWS keys
\techo "Rotating keys"

force-delete: ## Force delete resources
\techo "Force deleting"

normal-command: ## Normal safe command
\techo "Safe command"
"""
        
        makefile_path = self.create_test_makefile(makefile_content)
        
        try:
            parser = MakefileParser(makefile_path)
            commands = parser.parse()
            
            dangerous_flags = {cmd.target: cmd.is_dangerous for cmd in commands}
            
            assert dangerous_flags.get("clean-prod", False)
            assert dangerous_flags.get("emergency-shutdown", False)
            assert dangerous_flags.get("rotate-keys", False)
            assert dangerous_flags.get("force-delete", False)
            assert not dangerous_flags.get("normal-command", True)
            
        finally:
            os.unlink(makefile_path)
    
    def test_command_priority(self):
        """Test command priority calculation."""
        makefile_content = """
help: ## Show help
\techo "Help"

install: ## Install dependencies
\techo "Installing"

deploy-dev: ## Deploy development
\techo "Deploy dev"

some-utility: ## Some utility command
\techo "Utility"

emergency-stop: ## Emergency stop
\techo "Emergency"
"""
        
        makefile_path = self.create_test_makefile(makefile_content)
        
        try:
            parser = MakefileParser(makefile_path)
            commands = parser.parse()
            
            # Commands should be sorted by priority (highest first)
            priorities = [cmd.priority for cmd in commands]
            assert priorities == sorted(priorities, reverse=True)
            
            # Emergency commands should have highest priority
            emergency_cmd = next(cmd for cmd in commands if cmd.target == "emergency-stop")
            assert emergency_cmd.priority >= 95
            
            # High-priority commands should have boosted priority
            help_cmd = next(cmd for cmd in commands if cmd.target == "help")
            install_cmd = next(cmd for cmd in commands if cmd.target == "install")
            deploy_cmd = next(cmd for cmd in commands if cmd.target == "deploy-dev")
            
            # These should have higher priority than utility commands
            utility_cmd = next(cmd for cmd in commands if cmd.target == "some-utility")
            assert help_cmd.priority > utility_cmd.priority
            assert install_cmd.priority > utility_cmd.priority
            assert deploy_cmd.priority > utility_cmd.priority
            
        finally:
            os.unlink(makefile_path)
    
    def test_commands_by_category(self):
        """Test organizing commands by category."""
        makefile_content = """
install: ## Install dependencies
\techo "Installing"

test: ## Run tests
\techo "Testing"

deploy-dev: ## Deploy development
\techo "Deploy"

clean: ## Clean resources
\techo "Clean"
"""
        
        makefile_path = self.create_test_makefile(makefile_content)
        
        try:
            parser = MakefileParser(makefile_path)
            categorized = parser.get_commands_by_category()
            
            # Should have commands in appropriate categories
            assert len(categorized[CommandCategory.DEVELOPMENT]) > 0
            assert len(categorized[CommandCategory.TESTING]) > 0
            assert len(categorized[CommandCategory.INFRASTRUCTURE]) > 0
            assert len(categorized[CommandCategory.CLEANUP]) > 0
            
            # Check specific commands are in right categories
            dev_targets = [cmd.target for cmd in categorized[CommandCategory.DEVELOPMENT]]
            test_targets = [cmd.target for cmd in categorized[CommandCategory.TESTING]]
            infra_targets = [cmd.target for cmd in categorized[CommandCategory.INFRASTRUCTURE]]
            cleanup_targets = [cmd.target for cmd in categorized[CommandCategory.CLEANUP]]
            
            assert "install" in dev_targets
            assert "test" in test_targets
            assert "deploy-dev" in infra_targets
            assert "clean" in cleanup_targets
            
        finally:
            os.unlink(makefile_path)
    
    def test_search_commands(self):
        """Test command search functionality."""
        makefile_content = """
install-deps: ## Install dependencies
\techo "Installing"

test-unit: ## Run unit tests
\techo "Testing"

deploy-dev: ## Deploy to development
\techo "Deploy"

deploy-prod: ## Deploy to production
\techo "Deploy prod"
"""
        
        makefile_path = self.create_test_makefile(makefile_content)
        
        try:
            parser = MakefileParser(makefile_path)
            
            # Search for deploy commands
            deploy_commands = parser.search_commands("deploy")
            deploy_targets = [cmd.target for cmd in deploy_commands]
            assert "deploy-dev" in deploy_targets
            assert "deploy-prod" in deploy_targets
            assert "install-deps" not in deploy_targets
            
            # Search for test commands
            test_commands = parser.search_commands("test")
            test_targets = [cmd.target for cmd in test_commands]
            assert "test-unit" in test_targets
            assert "deploy-dev" not in test_targets
            
            # Search for development
            dev_commands = parser.search_commands("development")
            dev_targets = [cmd.target for cmd in dev_commands]
            assert "deploy-dev" in dev_targets
            
        finally:
            os.unlink(makefile_path)
    
    def test_malformed_makefile(self):
        """Test parsing malformed Makefile."""
        makefile_content = """
# Malformed Makefile

invalid-target-no-colon ## This is invalid
\techo "Invalid"

valid-target: ## This is valid
\techo "Valid"

another-invalid ## No colon here either
\tcommand here
"""
        
        makefile_path = self.create_test_makefile(makefile_content)
        
        try:
            parser = MakefileParser(makefile_path)
            commands = parser.parse()
            
            # Should only parse valid targets
            targets = [cmd.target for cmd in commands]
            assert "valid-target" in targets
            assert "invalid-target-no-colon" not in targets
            assert "another-invalid" not in targets
            
        finally:
            os.unlink(makefile_path)
    
    def test_nonexistent_makefile(self):
        """Test handling of nonexistent Makefile."""
        parser = MakefileParser("/nonexistent/path/Makefile")
        commands = parser.parse()
        
        # Should return empty list
        assert commands == []
    
    def test_refresh_commands(self):
        """Test command refresh functionality."""
        # Create initial Makefile
        makefile_content = """
test: ## Run tests
\techo "Testing"
"""
        
        makefile_path = self.create_test_makefile(makefile_content)
        
        try:
            parser = MakefileParser(makefile_path)
            
            # Parse initial commands
            commands1 = parser.parse()
            assert len(commands1) == 1
            assert commands1[0].target == "test"
            
            # Update Makefile
            updated_content = """
test: ## Run tests
\techo "Testing"

deploy: ## Deploy application
\techo "Deploying"
"""
            
            with open(makefile_path, 'w') as f:
                f.write(updated_content)
            
            # Refresh should pick up new commands
            commands2 = parser.refresh()
            assert len(commands2) == 2
            targets = [cmd.target for cmd in commands2]
            assert "test" in targets
            assert "deploy" in targets
            
        finally:
            os.unlink(makefile_path)


class TestCommandIntegration:
    """Integration tests for command functionality."""
    
    @patch('subprocess.run')
    def test_makefile_parser_integration(self, mock_run):
        """Test integration between parser and actual Makefile."""
        # Mock successful make -n command
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        # Use a real Makefile if available, otherwise skip
        makefile_path = Path.cwd() / "Makefile"
        if not makefile_path.exists():
            pytest.skip("No Makefile found for integration test")
        
        parser = MakefileParser(str(makefile_path))
        commands = parser.parse()
        
        # Should have some commands
        assert len(commands) > 0
        
        # All commands should have required fields
        for command in commands:
            assert command.name
            assert command.target
            assert command.category
            assert isinstance(command.is_dangerous, bool)
            assert isinstance(command.priority, int)
    
    def test_command_categories_complete(self):
        """Test that all command categories are handled."""
        # Ensure all categories have icons
        parser = MakefileParser()
        
        for category in CommandCategory:
            assert category in parser.command_icons
            assert parser.command_icons[category]  # Should not be empty
    
    def test_environment_patterns_complete(self):
        """Test that environment patterns are comprehensive."""
        parser = MakefileParser()
        
        # Test known environment patterns
        test_cases = [
            ("deploy-dev", "dev"),
            ("dev-app", "dev"),
            ("staging-deploy", "staging"),
            ("deploy-staging", "staging"),
            ("prod-clean", "prod"),
            ("deploy-prod", "prod"),
            ("production-deploy", "prod"),
        ]
        
        for target, expected_env in test_cases:
            detected_env = parser._determine_environment(target)
            assert detected_env == expected_env, f"Failed for {target}: expected {expected_env}, got {detected_env}"