"""AWS status checker service for validating AWS connectivity and resources."""

import asyncio
import subprocess
import json
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import os

from ..models.status import StatusType


class AWSServiceStatus(Enum):
    """AWS service status types."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class AWSCredentials:
    """AWS credential information."""
    profile: Optional[str] = None
    access_key_id: Optional[str] = None
    region: str = "us-east-1"
    is_valid: bool = False
    error_message: Optional[str] = None


@dataclass
class AWSResourceSummary:
    """Summary of AWS resources."""
    vpcs: int = 0
    instances: int = 0
    ecs_clusters: int = 0
    rds_instances: int = 0
    load_balancers: int = 0
    error_message: Optional[str] = None


@dataclass
class AWSStatus:
    """Complete AWS status information."""
    credentials: AWSCredentials
    connectivity: bool = False
    services: Dict[str, AWSServiceStatus] = None
    resources: Optional[AWSResourceSummary] = None
    last_check: Optional[str] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.services is None:
            self.services = {}


class AWSChecker:
    """Service for checking AWS connectivity and status."""
    
    def __init__(self):
        """Initialize AWS checker."""
        self.last_status: Optional[AWSStatus] = None
        self.check_timeout = 30  # seconds
        
        # Core AWS services to check
        self.core_services = [
            "ec2", "ecs", "rds", "elbv2", "cloudformation", 
            "iam", "kms", "cloudtrail", "logs"
        ]
    
    async def check_status(self, quick_check: bool = False) -> AWSStatus:
        """
        Check AWS status comprehensively.
        
        Args:
            quick_check: If True, only check credentials and basic connectivity
        
        Returns:
            AWSStatus object with current status
        """
        try:
            # Check credentials first
            credentials = await self._check_credentials()
            
            # Initialize status
            status = AWSStatus(
                credentials=credentials,
                connectivity=credentials.is_valid
            )
            
            if not credentials.is_valid:
                status.error_message = credentials.error_message
                return status
            
            # If quick check, return early
            if quick_check:
                return status
            
            # Check service availability
            status.services = await self._check_services()
            
            # Check resources (if connectivity is good)
            if status.connectivity:
                status.resources = await self._check_resources()
            
            # Update timestamp
            from datetime import datetime
            status.last_check = datetime.now().isoformat()
            
            self.last_status = status
            return status
            
        except Exception as e:
            return AWSStatus(
                credentials=AWSCredentials(error_message=str(e)),
                connectivity=False,
                error_message=f"AWS check failed: {str(e)}"
            )
    
    async def _check_credentials(self) -> AWSCredentials:
        """Check AWS credentials validity."""
        try:
            # First try to get caller identity
            result = await self._run_aws_command(["sts", "get-caller-identity"])
            
            if result and result.get("returncode") == 0:
                identity_data = json.loads(result["stdout"])
                
                # Get current region
                region_result = await self._run_aws_command(["configure", "get", "region"])
                region = "us-east-1"  # default
                if region_result and region_result.get("returncode") == 0:
                    region = region_result["stdout"].strip() or "us-east-1"
                
                # Get current profile
                current_profile = os.environ.get("AWS_PROFILE", "default")
                
                return AWSCredentials(
                    profile=current_profile,
                    access_key_id=identity_data.get("UserId", "unknown")[:12] + "...",
                    region=region,
                    is_valid=True
                )
            else:
                error_msg = result.get("stderr", "Unknown AWS error") if result else "AWS CLI not available"
                return AWSCredentials(
                    is_valid=False,
                    error_message=error_msg
                )
                
        except Exception as e:
            return AWSCredentials(
                is_valid=False,
                error_message=f"Credential check failed: {str(e)}"
            )
    
    async def _check_services(self) -> Dict[str, AWSServiceStatus]:
        """Check availability of core AWS services."""
        services = {}
        
        # Define service check commands
        service_checks = {
            "ec2": ["ec2", "describe-regions", "--max-items", "1"],
            "ecs": ["ecs", "list-clusters", "--max-items", "1"],
            "rds": ["rds", "describe-db-instances", "--max-items", "1"],
            "elbv2": ["elbv2", "describe-load-balancers", "--max-items", "1"],
            "cloudformation": ["cloudformation", "list-stacks", "--max-items", "1"],
            "iam": ["iam", "get-user"],
            "kms": ["kms", "list-keys", "--limit", "1"],
            "cloudtrail": ["cloudtrail", "describe-trails", "--max-items", "1"],
            "logs": ["logs", "describe-log-groups", "--limit", "1"]
        }
        
        # Check each service concurrently (but limit concurrency)
        semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent checks
        
        async def check_service(service_name: str, command: List[str]) -> Tuple[str, AWSServiceStatus]:
            async with semaphore:
                try:
                    result = await self._run_aws_command(command, timeout=10)
                    if result and result.get("returncode") == 0:
                        return service_name, AWSServiceStatus.AVAILABLE
                    else:
                        return service_name, AWSServiceStatus.UNAVAILABLE
                except asyncio.TimeoutError:
                    return service_name, AWSServiceStatus.DEGRADED
                except Exception:
                    return service_name, AWSServiceStatus.UNKNOWN
        
        # Run all service checks
        tasks = [check_service(name, cmd) for name, cmd in service_checks.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, tuple):
                service_name, status = result
                services[service_name] = status
            else:
                # Exception occurred
                continue
        
        return services
    
    async def _check_resources(self) -> AWSResourceSummary:
        """Check AWS resource counts."""
        try:
            summary = AWSResourceSummary()
            
            # Define resource count commands
            resource_checks = {
                "vpcs": ["ec2", "describe-vpcs", "--query", "length(Vpcs)", "--output", "text"],
                "instances": ["ec2", "describe-instances", "--query", "length(Reservations[].Instances[])", "--output", "text"],
                "ecs_clusters": ["ecs", "list-clusters", "--query", "length(clusterArns)", "--output", "text"],
                "rds_instances": ["rds", "describe-db-instances", "--query", "length(DBInstances)", "--output", "text"],
                "load_balancers": ["elbv2", "describe-load-balancers", "--query", "length(LoadBalancers)", "--output", "text"]
            }
            
            # Run checks with limited concurrency
            semaphore = asyncio.Semaphore(2)
            
            async def get_resource_count(resource_name: str, command: List[str]) -> Tuple[str, int]:
                async with semaphore:
                    try:
                        result = await self._run_aws_command(command, timeout=15)
                        if result and result.get("returncode") == 0:
                            count_str = result["stdout"].strip()
                            count = int(count_str) if count_str.isdigit() else 0
                            return resource_name, count
                        return resource_name, 0
                    except Exception:
                        return resource_name, 0
            
            # Execute all resource checks
            tasks = [get_resource_count(name, cmd) for name, cmd in resource_checks.items()]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, tuple):
                    resource_name, count = result
                    setattr(summary, resource_name, count)
            
            return summary
            
        except Exception as e:
            return AWSResourceSummary(error_message=f"Resource check failed: {str(e)}")
    
    async def _run_aws_command(self, command: List[str], timeout: int = 30) -> Optional[Dict[str, Any]]:
        """
        Run AWS CLI command asynchronously.
        
        Args:
            command: AWS CLI command parts (without 'aws' prefix)
            timeout: Command timeout in seconds
        
        Returns:
            Dictionary with returncode, stdout, stderr
        """
        try:
            full_command = ["aws"] + command
            
            process = await asyncio.create_subprocess_exec(
                *full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=timeout
                )
                
                return {
                    "returncode": process.returncode,
                    "stdout": stdout.decode('utf-8') if stdout else "",
                    "stderr": stderr.decode('utf-8') if stderr else ""
                }
                
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise asyncio.TimeoutError(f"AWS command timed out after {timeout} seconds")
                
        except FileNotFoundError:
            return {
                "returncode": 1,
                "stdout": "",
                "stderr": "AWS CLI not found. Please install AWS CLI."
            }
        except Exception as e:
            return {
                "returncode": 1,
                "stdout": "",
                "stderr": str(e)
            }
    
    def get_status_type(self, aws_status: AWSStatus) -> StatusType:
        """
        Convert AWS status to StatusType for display.
        
        Args:
            aws_status: AWSStatus object
        
        Returns:
            StatusType for display
        """
        if not aws_status.credentials.is_valid:
            return StatusType.ERROR
        
        if not aws_status.connectivity:
            return StatusType.ERROR
        
        # Check service availability
        if aws_status.services:
            unavailable_services = [
                name for name, status in aws_status.services.items()
                if status == AWSServiceStatus.UNAVAILABLE
            ]
            
            degraded_services = [
                name for name, status in aws_status.services.items()
                if status == AWSServiceStatus.DEGRADED
            ]
            
            if unavailable_services:
                return StatusType.ERROR
            elif degraded_services:
                return StatusType.WARNING
        
        return StatusType.SUCCESS
    
    def get_status_message(self, aws_status: AWSStatus) -> str:
        """
        Get human-readable status message.
        
        Args:
            aws_status: AWSStatus object
        
        Returns:
            Status message string
        """
        if aws_status.error_message:
            return f"AWS Error"
        
        if not aws_status.credentials.is_valid:
            return "No AWS Credentials"
        
        if not aws_status.connectivity:
            return "AWS Unreachable"
        
        # Check services
        if aws_status.services:
            available_count = sum(1 for s in aws_status.services.values() 
                                if s == AWSServiceStatus.AVAILABLE)
            total_count = len(aws_status.services)
            
            if available_count == total_count:
                return f"AWS Connected ({aws_status.credentials.region})"
            else:
                return f"AWS Partial ({available_count}/{total_count})"
        
        return f"AWS Connected ({aws_status.credentials.region})"
    
    def get_status_icon(self, aws_status: AWSStatus) -> str:
        """
        Get status icon for display.
        
        Args:
            aws_status: AWSStatus object
        
        Returns:
            Status icon string
        """
        status_type = self.get_status_type(aws_status)
        
        icons = {
            StatusType.SUCCESS: "✅",
            StatusType.WARNING: "⚠️",
            StatusType.ERROR: "❌",
            StatusType.INFO: "ℹ️",
            StatusType.UNKNOWN: "❓"
        }
        
        return icons.get(status_type, "❓")
    
    async def check_specific_profile(self, profile_name: str) -> AWSStatus:
        """
        Check status for a specific AWS profile.
        
        Args:
            profile_name: AWS profile name to check
        
        Returns:
            AWSStatus for the specific profile
        """
        # Temporarily set profile environment variable
        original_profile = os.environ.get("AWS_PROFILE")
        
        try:
            os.environ["AWS_PROFILE"] = profile_name
            return await self.check_status(quick_check=True)
        finally:
            # Restore original profile
            if original_profile:
                os.environ["AWS_PROFILE"] = original_profile
            elif "AWS_PROFILE" in os.environ:
                del os.environ["AWS_PROFILE"]
    
    def get_cached_status(self) -> Optional[AWSStatus]:
        """
        Get last cached AWS status.
        
        Returns:
            Last AWSStatus or None if no cache
        """
        return self.last_status