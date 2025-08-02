"""Tests for status monitoring and checking."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from ..models.status import SystemStatus, ComponentStatus, StatusType
from ..services.aws_checker import AWSChecker, AWSStatus, AWSCredentials, AWSServiceStatus, AWSResourceSummary


class TestSystemStatus:
    """Test SystemStatus model."""
    
    def test_create_default_status(self):
        """Test creating default system status."""
        status = SystemStatus.create_default()
        
        assert status.repository is not None
        assert status.aws is not None
        assert status.pulumi is not None
        assert status.docker is not None
        assert isinstance(status.last_updated, datetime)
        
        # Default status should be unknown/loading
        assert status.repository.status == StatusType.UNKNOWN
        assert status.aws.status == StatusType.UNKNOWN
        assert status.pulumi.status == StatusType.UNKNOWN
        assert status.docker.status == StatusType.UNKNOWN
    
    def test_component_status_creation(self):
        """Test creating component status."""
        component = ComponentStatus(
            name="Test Component",
            status=StatusType.SUCCESS,
            message="All good",
            icon="✅"
        )
        
        assert component.name == "Test Component"
        assert component.status == StatusType.SUCCESS
        assert component.message == "All good"
        assert component.icon == "✅"
    
    def test_system_status_overall_health(self):
        """Test overall system health calculation."""
        # All components successful
        status = SystemStatus(
            repository=ComponentStatus("Repo", StatusType.SUCCESS, "OK", "✅"),
            aws=ComponentStatus("AWS", StatusType.SUCCESS, "Connected", "✅"),
            pulumi=ComponentStatus("Pulumi", StatusType.SUCCESS, "Ready", "✅"),
            docker=ComponentStatus("Docker", StatusType.SUCCESS, "Running", "✅")
        )
        
        assert status.is_healthy()
        
        # One component with error
        status.aws.status = StatusType.ERROR
        assert not status.is_healthy()
        
        # One component with warning (still considered healthy)
        status.aws.status = StatusType.WARNING
        assert status.is_healthy()
    
    def test_status_priority(self):
        """Test status priority ordering."""
        assert StatusType.ERROR.value < StatusType.WARNING.value
        assert StatusType.WARNING.value < StatusType.SUCCESS.value
        assert StatusType.SUCCESS.value < StatusType.INFO.value
        assert StatusType.INFO.value < StatusType.UNKNOWN.value


class TestAWSCredentials:
    """Test AWS credentials model."""
    
    def test_valid_credentials(self):
        """Test valid credentials creation."""
        creds = AWSCredentials(
            profile="test-profile",
            access_key_id="AKIA123456789",
            region="us-west-2",
            is_valid=True
        )
        
        assert creds.profile == "test-profile"
        assert creds.access_key_id == "AKIA123456789"
        assert creds.region == "us-west-2"
        assert creds.is_valid
        assert creds.error_message is None
    
    def test_invalid_credentials(self):
        """Test invalid credentials creation."""
        creds = AWSCredentials(
            is_valid=False,
            error_message="No credentials found"
        )
        
        assert not creds.is_valid
        assert creds.error_message == "No credentials found"


class TestAWSResourceSummary:
    """Test AWS resource summary model."""
    
    def test_resource_summary_creation(self):
        """Test creating resource summary."""
        summary = AWSResourceSummary(
            vpcs=2,
            instances=5,
            ecs_clusters=1,
            rds_instances=1,
            load_balancers=2
        )
        
        assert summary.vpcs == 2
        assert summary.instances == 5
        assert summary.ecs_clusters == 1
        assert summary.rds_instances == 1
        assert summary.load_balancers == 2
        assert summary.error_message is None
    
    def test_resource_summary_with_error(self):
        """Test resource summary with error."""
        summary = AWSResourceSummary(
            error_message="Failed to fetch resources"
        )
        
        assert summary.vpcs == 0  # Default values
        assert summary.error_message == "Failed to fetch resources"


class TestAWSStatus:
    """Test AWS status model."""
    
    def test_aws_status_creation(self):
        """Test creating AWS status."""
        credentials = AWSCredentials(is_valid=True, region="us-east-1")
        resources = AWSResourceSummary(vpcs=1, instances=2)
        
        status = AWSStatus(
            credentials=credentials,
            connectivity=True,
            services={"ec2": AWSServiceStatus.AVAILABLE},
            resources=resources,
            last_check="2023-01-01T00:00:00"
        )
        
        assert status.credentials.is_valid
        assert status.connectivity
        assert status.services["ec2"] == AWSServiceStatus.AVAILABLE
        assert status.resources.vpcs == 1
        assert status.last_check == "2023-01-01T00:00:00"
    
    def test_aws_status_with_errors(self):
        """Test AWS status with errors."""
        credentials = AWSCredentials(is_valid=False, error_message="Invalid credentials")
        
        status = AWSStatus(
            credentials=credentials,
            connectivity=False,
            error_message="AWS connection failed"
        )
        
        assert not status.credentials.is_valid
        assert not status.connectivity
        assert status.error_message == "AWS connection failed"


class TestAWSChecker:
    """Test AWS checker service."""
    
    def test_aws_checker_initialization(self):
        """Test AWS checker initialization."""
        checker = AWSChecker()
        
        assert checker.last_status is None
        assert checker.check_timeout == 30
        assert len(checker.core_services) > 0
        assert "ec2" in checker.core_services
        assert "ecs" in checker.core_services
    
    @pytest.mark.asyncio
    async def test_check_credentials_success(self):
        """Test successful credential check."""
        checker = AWSChecker()
        
        # Mock successful AWS CLI call
        mock_result = {
            "returncode": 0,
            "stdout": '{"UserId": "AIDACKCEVSQ6C2EXAMPLE", "Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/testuser"}',
            "stderr": ""
        }
        
        with patch.object(checker, '_run_aws_command', return_value=mock_result):
            credentials = await checker._check_credentials()
            
            assert credentials.is_valid
            assert credentials.access_key_id == "AIDACKCEVSQ6..."  # Truncated
            assert credentials.region == "us-east-1"  # Default
            assert credentials.error_message is None
    
    @pytest.mark.asyncio
    async def test_check_credentials_failure(self):
        """Test failed credential check."""
        checker = AWSChecker()
        
        # Mock failed AWS CLI call
        mock_result = {
            "returncode": 1,
            "stdout": "",
            "stderr": "Unable to locate credentials"
        }
        
        with patch.object(checker, '_run_aws_command', return_value=mock_result):
            credentials = await checker._check_credentials()
            
            assert not credentials.is_valid
            assert credentials.error_message == "Unable to locate credentials"
    
    @pytest.mark.asyncio
    async def test_check_services(self):
        """Test service availability checking."""
        checker = AWSChecker()
        
        # Mock service check results
        async def mock_run_command(command, timeout=30):
            service = command[0]  # First part is service name
            if service == "ec2":
                return {"returncode": 0, "stdout": "success", "stderr": ""}
            elif service == "ecs":
                return {"returncode": 1, "stdout": "", "stderr": "error"}
            else:
                return {"returncode": 0, "stdout": "success", "stderr": ""}
        
        with patch.object(checker, '_run_aws_command', side_effect=mock_run_command):
            services = await checker._check_services()
            
            assert len(services) > 0
            assert "ec2" in services
            assert services["ec2"] == AWSServiceStatus.AVAILABLE
            
            if "ecs" in services:
                assert services["ecs"] == AWSServiceStatus.UNAVAILABLE
    
    @pytest.mark.asyncio
    async def test_check_resources(self):
        """Test resource count checking."""
        checker = AWSChecker()
        
        # Mock resource count results
        async def mock_run_command(command, timeout=30):
            if "describe-vpcs" in command:
                return {"returncode": 0, "stdout": "2", "stderr": ""}
            elif "describe-instances" in command:
                return {"returncode": 0, "stdout": "5", "stderr": ""}
            elif "list-clusters" in command:
                return {"returncode": 0, "stdout": "1", "stderr": ""}
            else:
                return {"returncode": 0, "stdout": "0", "stderr": ""}
        
        with patch.object(checker, '_run_aws_command', side_effect=mock_run_command):
            resources = await checker._check_resources()
            
            assert resources.vpcs == 2
            assert resources.instances == 5
            assert resources.ecs_clusters == 1
            assert resources.error_message is None
    
    @pytest.mark.asyncio
    async def test_check_status_quick(self):
        """Test quick status check."""
        checker = AWSChecker()
        
        # Mock successful credential check
        mock_creds = AWSCredentials(is_valid=True, region="us-east-1")
        
        with patch.object(checker, '_check_credentials', return_value=mock_creds):
            status = await checker.check_status(quick_check=True)
            
            assert status.credentials.is_valid
            assert status.connectivity
            assert status.services == {}  # No services checked in quick mode
            assert status.resources is None
    
    @pytest.mark.asyncio
    async def test_check_status_full(self):
        """Test full status check."""
        checker = AWSChecker()
        
        # Mock all components
        mock_creds = AWSCredentials(is_valid=True, region="us-east-1")
        mock_services = {"ec2": AWSServiceStatus.AVAILABLE}
        mock_resources = AWSResourceSummary(vpcs=1)
        
        with patch.object(checker, '_check_credentials', return_value=mock_creds), \
             patch.object(checker, '_check_services', return_value=mock_services), \
             patch.object(checker, '_check_resources', return_value=mock_resources):
            
            status = await checker.check_status(quick_check=False)
            
            assert status.credentials.is_valid
            assert status.connectivity
            assert status.services == mock_services
            assert status.resources == mock_resources
            assert status.last_check is not None
    
    @pytest.mark.asyncio
    async def test_check_status_with_exception(self):
        """Test status check with exception."""
        checker = AWSChecker()
        
        # Mock exception during credential check
        with patch.object(checker, '_check_credentials', side_effect=Exception("Test error")):
            status = await checker.check_status()
            
            assert not status.connectivity
            assert "AWS check failed: Test error" in status.error_message
    
    def test_get_status_type(self):
        """Test status type conversion."""
        checker = AWSChecker()
        
        # Test invalid credentials
        status = AWSStatus(
            credentials=AWSCredentials(is_valid=False),
            connectivity=False
        )
        assert checker.get_status_type(status) == StatusType.ERROR
        
        # Test valid credentials, no connectivity
        status = AWSStatus(
            credentials=AWSCredentials(is_valid=True),
            connectivity=False
        )
        assert checker.get_status_type(status) == StatusType.ERROR
        
        # Test valid credentials and connectivity
        status = AWSStatus(
            credentials=AWSCredentials(is_valid=True),
            connectivity=True,
            services={"ec2": AWSServiceStatus.AVAILABLE}
        )
        assert checker.get_status_type(status) == StatusType.SUCCESS
        
        # Test with degraded services
        status = AWSStatus(
            credentials=AWSCredentials(is_valid=True),
            connectivity=True,
            services={"ec2": AWSServiceStatus.DEGRADED}
        )
        assert checker.get_status_type(status) == StatusType.WARNING
        
        # Test with unavailable services
        status = AWSStatus(
            credentials=AWSCredentials(is_valid=True),
            connectivity=True,
            services={"ec2": AWSServiceStatus.UNAVAILABLE}
        )
        assert checker.get_status_type(status) == StatusType.ERROR
    
    def test_get_status_message(self):
        """Test status message generation."""
        checker = AWSChecker()
        
        # Test error message
        status = AWSStatus(
            credentials=AWSCredentials(is_valid=False),
            connectivity=False,
            error_message="Connection failed"
        )
        assert checker.get_status_message(status) == "AWS Error"
        
        # Test invalid credentials
        status = AWSStatus(
            credentials=AWSCredentials(is_valid=False),
            connectivity=False
        )
        assert checker.get_status_message(status) == "No AWS Credentials"
        
        # Test no connectivity
        status = AWSStatus(
            credentials=AWSCredentials(is_valid=True, region="us-west-2"),
            connectivity=False
        )
        assert checker.get_status_message(status) == "AWS Unreachable"
        
        # Test successful connection
        status = AWSStatus(
            credentials=AWSCredentials(is_valid=True, region="us-west-2"),
            connectivity=True,
            services={"ec2": AWSServiceStatus.AVAILABLE, "ecs": AWSServiceStatus.AVAILABLE}
        )
        assert checker.get_status_message(status) == "AWS Connected (us-west-2)"
        
        # Test partial service availability
        status = AWSStatus(
            credentials=AWSCredentials(is_valid=True, region="us-west-2"),
            connectivity=True,
            services={"ec2": AWSServiceStatus.AVAILABLE, "ecs": AWSServiceStatus.UNAVAILABLE}
        )
        assert checker.get_status_message(status) == "AWS Partial (1/2)"
    
    def test_get_status_icon(self):
        """Test status icon generation."""
        checker = AWSChecker()
        
        # Mock get_status_type to return specific values
        with patch.object(checker, 'get_status_type') as mock_get_type:
            mock_get_type.return_value = StatusType.SUCCESS
            icon = checker.get_status_icon(MagicMock())
            assert icon == "✅"
            
            mock_get_type.return_value = StatusType.WARNING
            icon = checker.get_status_icon(MagicMock())
            assert icon == "⚠️"
            
            mock_get_type.return_value = StatusType.ERROR
            icon = checker.get_status_icon(MagicMock())
            assert icon == "❌"
            
            mock_get_type.return_value = StatusType.UNKNOWN
            icon = checker.get_status_icon(MagicMock())
            assert icon == "❓"
    
    @pytest.mark.asyncio
    async def test_check_specific_profile(self):
        """Test checking specific AWS profile."""
        checker = AWSChecker()
        
        # Mock environment and credential check
        with patch.dict('os.environ', {}, clear=True), \
             patch.object(checker, 'check_status') as mock_check:
            
            mock_status = AWSStatus(
                credentials=AWSCredentials(is_valid=True, profile="test-profile"),
                connectivity=True
            )
            mock_check.return_value = mock_status
            
            status = await checker.check_specific_profile("test-profile")
            
            # Should have called check_status with quick_check=True
            mock_check.assert_called_once_with(quick_check=True)
            assert status == mock_status
    
    def test_get_cached_status(self):
        """Test getting cached status."""
        checker = AWSChecker()
        
        # Initially no cached status
        assert checker.get_cached_status() is None
        
        # Set cached status
        mock_status = AWSStatus(
            credentials=AWSCredentials(is_valid=True),
            connectivity=True
        )
        checker.last_status = mock_status
        
        # Should return cached status
        assert checker.get_cached_status() == mock_status
    
    @pytest.mark.asyncio
    async def test_run_aws_command_success(self):
        """Test running AWS command successfully."""
        checker = AWSChecker()
        
        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"output", b"")
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await checker._run_aws_command(["sts", "get-caller-identity"])
            
            assert result["returncode"] == 0
            assert result["stdout"] == "output"
            assert result["stderr"] == ""
    
    @pytest.mark.asyncio
    async def test_run_aws_command_timeout(self):
        """Test AWS command timeout."""
        checker = AWSChecker()
        
        # Mock subprocess that times out
        mock_process = AsyncMock()
        mock_process.communicate.side_effect = asyncio.TimeoutError()
        mock_process.kill = AsyncMock()
        mock_process.wait = AsyncMock()
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with pytest.raises(asyncio.TimeoutError):
                await checker._run_aws_command(["sts", "get-caller-identity"], timeout=1)
    
    @pytest.mark.asyncio
    async def test_run_aws_command_not_found(self):
        """Test AWS command when CLI not found."""
        checker = AWSChecker()
        
        with patch('asyncio.create_subprocess_exec', side_effect=FileNotFoundError()):
            result = await checker._run_aws_command(["sts", "get-caller-identity"])
            
            assert result["returncode"] == 1
            assert "AWS CLI not found" in result["stderr"]


class TestStatusIntegration:
    """Integration tests for status monitoring."""
    
    def test_status_type_enum_values(self):
        """Test that status type enum values are properly ordered."""
        # Values should be ordered by severity (lower = more severe)
        assert StatusType.ERROR.value == "error"
        assert StatusType.WARNING.value == "warning"
        assert StatusType.SUCCESS.value == "success"
        assert StatusType.INFO.value == "info"
        assert StatusType.UNKNOWN.value == "unknown"
    
    def test_component_status_defaults(self):
        """Test component status defaults."""
        component = ComponentStatus(
            name="Test",
            status=StatusType.SUCCESS,
            message="OK"
        )
        
        # Should have default icon
        assert component.icon is not None
        assert len(component.icon) > 0
    
    @pytest.mark.asyncio
    async def test_full_system_check_simulation(self):
        """Test a full system check simulation."""
        # This would simulate a complete system check
        # In a real environment, this would check actual services
        
        # Create mock statuses
        repo_status = ComponentStatus("Repository", StatusType.SUCCESS, "Clean", "✅")
        aws_status = ComponentStatus("AWS", StatusType.SUCCESS, "Connected", "✅")
        pulumi_status = ComponentStatus("Pulumi", StatusType.SUCCESS, "Ready", "✅")
        docker_status = ComponentStatus("Docker", StatusType.SUCCESS, "Running", "✅")
        
        system_status = SystemStatus(
            repository=repo_status,
            aws=aws_status,
            pulumi=pulumi_status,
            docker=docker_status
        )
        
        assert system_status.is_healthy()
        assert all(comp.status == StatusType.SUCCESS 
                  for comp in [system_status.repository, system_status.aws, 
                              system_status.pulumi, system_status.docker])