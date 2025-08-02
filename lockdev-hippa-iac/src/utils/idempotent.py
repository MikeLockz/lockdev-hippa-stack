"""Utility functions for idempotent resource creation in Pulumi."""
import pulumi
import pulumi_aws as aws
from typing import Optional, Dict, Any


def create_idempotent_resource_options(
    protect: bool = True,
    ignore_changes: Optional[list] = None,
    import_id: Optional[str] = None
) -> pulumi.ResourceOptions:
    """
    Create standardized ResourceOptions for idempotent resource creation.
    
    Args:
        protect: Whether to protect the resource from deletion
        ignore_changes: List of properties to ignore on updates
        import_id: ID of existing resource to import
    
    Returns:
        pulumi.ResourceOptions configured for idempotent deployment
    """
    return pulumi.ResourceOptions(
        protect=protect,
        ignore_changes=ignore_changes or [],
        import_=import_id if import_id else None
    )


def get_existing_resource_id(resource_type: str, name: str, **kwargs) -> Optional[str]:
    """
    Attempt to get the ID of an existing AWS resource.
    
    Args:
        resource_type: Type of AWS resource (e.g., 'guardduty_detector', 'ecr_repository')
        name: Name or identifier of the resource
        **kwargs: Additional parameters for the lookup
    
    Returns:
        Resource ID if found, None otherwise
    """
    try:
        if resource_type == "guardduty_detector":
            detector = aws.guardduty.get_detector()
            return detector.id
        elif resource_type == "ecr_repository":
            repo = aws.ecr.get_repository(name=name)
            return repo.arn
        elif resource_type == "cloudwatch_log_group":
            log_group = aws.cloudwatch.get_log_group(name=name)
            return log_group.name
        elif resource_type == "sns_topic":
            topic = aws.sns.get_topic(name=name)
            return topic.arn
        elif resource_type == "rds_parameter_group":
            param_group = aws.rds.get_parameter_group(name=name)
            return param_group.name
        else:
            return None
    except Exception:
        # Resource doesn't exist or can't be accessed
        return None


def create_with_fallback(
    resource_class,
    resource_name: str,
    resource_type: str,
    lookup_name: str,
    **resource_args
) -> Any:
    """
    Create a resource with fallback to existing resource if it already exists.
    
    Args:
        resource_class: Pulumi resource class (e.g., aws.guardduty.Detector)
        resource_name: Pulumi resource name
        resource_type: Type identifier for lookup
        lookup_name: Name used for resource lookup
        **resource_args: Arguments to pass to resource constructor
    
    Returns:
        Created or imported resource
    """
    existing_id = get_existing_resource_id(resource_type, lookup_name)
    
    # Add idempotent resource options
    if "opts" not in resource_args:
        resource_args["opts"] = create_idempotent_resource_options(
            import_id=existing_id
        )
    else:
        # Merge with existing options
        existing_opts = resource_args["opts"]
        resource_args["opts"] = pulumi.ResourceOptions(
            protect=True,
            ignore_changes=getattr(existing_opts, "ignore_changes", []),
            import_=existing_id,
            depends_on=getattr(existing_opts, "depends_on", None),
            parent=getattr(existing_opts, "parent", None)
        )
    
    return resource_class(resource_name, **resource_args)


class IdempotentResourceManager:
    """Manager for creating idempotent AWS resources."""
    
    def __init__(self, config: pulumi.Config):
        self.config = config
        self.environment = config.get("environment", "dev")
    
    def create_guardduty_detector(self, **kwargs) -> aws.guardduty.Detector:
        """Create GuardDuty detector with idempotent handling."""
        return create_with_fallback(
            aws.guardduty.Detector,
            "hipaa-guardduty-detector",
            "guardduty_detector",
            "",  # GuardDuty detector lookup doesn't need a name
            **kwargs
        )
    
    def create_ecr_repository(self, name: str, **kwargs) -> aws.ecr.Repository:
        """Create ECR repository with idempotent handling."""
        return create_with_fallback(
            aws.ecr.Repository,
            "hipaa-app-repo",
            "ecr_repository",
            name,
            name=name,
            **kwargs
        )
    
    def create_cloudwatch_log_group(self, name: str, **kwargs) -> aws.cloudwatch.LogGroup:
        """Create CloudWatch log group with idempotent handling."""
        return create_with_fallback(
            aws.cloudwatch.LogGroup,
            f"log-group-{name.replace('/', '-').replace('_', '-')}",
            "cloudwatch_log_group",
            name,
            name=name,
            **kwargs
        )
    
    def create_sns_topic(self, name: str, **kwargs) -> aws.sns.Topic:
        """Create SNS topic with idempotent handling."""
        return create_with_fallback(
            aws.sns.Topic,
            f"sns-topic-{name}",
            "sns_topic",
            name,
            name=name,
            **kwargs
        )
    
    def create_rds_parameter_group(self, name: str, **kwargs) -> aws.rds.ParameterGroup:
        """Create RDS parameter group with idempotent handling."""
        return create_with_fallback(
            aws.rds.ParameterGroup,
            "hipaa-db-parameter-group",
            "rds_parameter_group",
            name,
            name=name,
            **kwargs
        )


def add_standard_tags(
    tags: Dict[str, Any], 
    environment: str, 
    compliance: str = "HIPAA"
) -> Dict[str, Any]:
    """
    Add standard tags to resource tags.
    
    Args:
        tags: Existing tags dictionary
        environment: Environment name (dev, staging, prod)
        compliance: Compliance standard (default: HIPAA)
    
    Returns:
        Tags dictionary with standard tags added
    """
    standard_tags = {
        "Environment": environment,
        "Compliance": compliance,
        "ManagedBy": "Pulumi",
        "CreatedBy": "HIPAA-Infrastructure-Stack"
    }
    
    # Merge with existing tags, giving precedence to existing ones
    return {**standard_tags, **tags}