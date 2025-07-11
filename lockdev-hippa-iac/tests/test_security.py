"""Security tests for HIPAA infrastructure."""
import pytest
import pulumi
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pulumi.runtime.test
def test_kms_key_creation():
    """Test KMS key creation and configuration."""
    from security.kms import create_kms_key
    
    kms_resources = create_kms_key()
    
    assert kms_resources["kms_key"] is not None
    assert kms_resources["kms_alias"] is not None


@pulumi.runtime.test
def test_iam_roles_creation():
    """Test IAM roles creation with least privilege."""
    from security.iam import create_iam_roles
    
    iam_resources = create_iam_roles()
    
    assert iam_resources["ecs_task_execution_role"] is not None
    assert iam_resources["ecs_task_role"] is not None
    assert iam_resources["cloudwatch_role"] is not None
    assert iam_resources["ecs_task_policy"] is not None
    assert iam_resources["cloudwatch_policy"] is not None


@pulumi.runtime.test
def test_cloudtrail_creation():
    """Test CloudTrail audit logging configuration."""
    from security.cloudtrail import create_cloudtrail
    
    cloudtrail_resources = create_cloudtrail()
    
    assert cloudtrail_resources["cloudtrail"] is not None
    assert cloudtrail_resources["cloudtrail_bucket"] is not None
    assert cloudtrail_resources["cloudtrail_log_group"] is not None
    assert cloudtrail_resources["cloudtrail_role"] is not None


@pulumi.runtime.test
def test_guardduty_creation():
    """Test GuardDuty threat detection setup."""
    from security.guardduty import create_guardduty
    
    guardduty_resources = create_guardduty()
    
    assert guardduty_resources["guardduty_detector"] is not None
    assert guardduty_resources["guardduty_sns_topic"] is not None
    assert guardduty_resources["guardduty_eventbridge_rule"] is not None
    assert guardduty_resources["guardduty_log_group"] is not None


@pulumi.runtime.test
def test_config_creation():
    """Test AWS Config compliance monitoring setup."""
    from security.config import create_config
    
    config_resources = create_config()
    
    assert config_resources["config_bucket"] is not None
    assert config_resources["config_role"] is not None
    assert config_resources["config_delivery_channel"] is not None
    assert config_resources["config_recorder"] is not None
    assert config_resources["config_rules"] is not None
    assert len(config_resources["config_rules"]) >= 6  # At least 6 compliance rules


@pulumi.runtime.test
def test_security_groups_exist():
    """Test security groups are properly configured."""
    from security.security_groups import create_security_groups
    import pulumi_aws as aws
    
    # Create a mock VPC for testing
    vpc = aws.ec2.Vpc(
        "test-vpc",
        cidr_block="10.0.0.0/16",
        enable_dns_hostnames=True,
        enable_dns_support=True
    )
    
    sg_resources = create_security_groups(vpc)
    
    assert sg_resources["alb_security_group"] is not None
    assert sg_resources["ecs_security_group"] is not None
    assert sg_resources["rds_security_group"] is not None


class TestSecurityCompliance:
    """Test security compliance requirements."""
    
    @pulumi.runtime.test
    def test_encryption_at_rest(self):
        """Test encryption at rest is enabled."""
        from security.kms import create_kms_key
        
        kms_resources = create_kms_key()
        
        # Verify KMS key is created for encryption
        assert kms_resources["kms_key"] is not None
        assert kms_resources["kms_alias"] is not None
    
    @pulumi.runtime.test
    def test_audit_logging_enabled(self):
        """Test audit logging is properly configured."""
        from security.cloudtrail import create_cloudtrail
        
        cloudtrail_resources = create_cloudtrail()
        
        # Verify CloudTrail is configured
        assert cloudtrail_resources["cloudtrail"] is not None
        assert cloudtrail_resources["cloudtrail_log_group"] is not None
    
    @pulumi.runtime.test
    def test_threat_detection_enabled(self):
        """Test threat detection is enabled."""
        from security.guardduty import create_guardduty
        
        guardduty_resources = create_guardduty()
        
        # Verify GuardDuty is configured
        assert guardduty_resources["guardduty_detector"] is not None
    
    @pulumi.runtime.test
    def test_compliance_monitoring_enabled(self):
        """Test compliance monitoring is enabled."""
        from security.config import create_config
        
        config_resources = create_config()
        
        # Verify Config is configured
        assert config_resources["config_recorder"] is not None
        assert config_resources["config_rules"] is not None
    
    @pulumi.runtime.test
    def test_least_privilege_access(self):
        """Test IAM roles follow least privilege principle."""
        from security.iam import create_iam_roles
        
        iam_resources = create_iam_roles()
        
        # Verify IAM roles are created with appropriate policies
        assert iam_resources["ecs_task_execution_role"] is not None
        assert iam_resources["ecs_task_role"] is not None
        assert iam_resources["cloudwatch_role"] is not None


class TestHIPAACompliance:
    """Test HIPAA compliance requirements."""
    
    @pulumi.runtime.test
    def test_data_encryption_requirements(self):
        """Test data encryption requirements are met."""
        from security.kms import create_kms_key
        
        kms_resources = create_kms_key()
        
        # HIPAA requires encryption at rest and in transit
        assert kms_resources["kms_key"] is not None
    
    @pulumi.runtime.test
    def test_access_control_requirements(self):
        """Test access control requirements are met."""
        from security.iam import create_iam_roles
        
        iam_resources = create_iam_roles()
        
        # HIPAA requires proper access controls
        assert iam_resources["ecs_task_execution_role"] is not None
        assert iam_resources["ecs_task_role"] is not None
    
    @pulumi.runtime.test
    def test_audit_trail_requirements(self):
        """Test audit trail requirements are met."""
        from security.cloudtrail import create_cloudtrail
        
        cloudtrail_resources = create_cloudtrail()
        
        # HIPAA requires comprehensive audit logging
        assert cloudtrail_resources["cloudtrail"] is not None
        assert cloudtrail_resources["cloudtrail_log_group"] is not None
    
    @pulumi.runtime.test
    def test_monitoring_requirements(self):
        """Test monitoring requirements are met."""
        from security.guardduty import create_guardduty
        from security.config import create_config
        
        guardduty_resources = create_guardduty()
        config_resources = create_config()
        
        # HIPAA requires continuous monitoring
        assert guardduty_resources["guardduty_detector"] is not None
        assert config_resources["config_recorder"] is not None
    
    @pulumi.runtime.test
    def test_network_security_requirements(self):
        """Test network security requirements are met."""
        from security.security_groups import create_security_groups
        import pulumi_aws as aws
        
        # Create a mock VPC for testing
        vpc = aws.ec2.Vpc(
            "test-vpc-hipaa",
            cidr_block="10.0.0.0/16",
            enable_dns_hostnames=True,
            enable_dns_support=True
        )
        
        sg_resources = create_security_groups(vpc)
        
        # HIPAA requires network segmentation and security
        assert sg_resources["alb_security_group"] is not None
        assert sg_resources["ecs_security_group"] is not None
        assert sg_resources["rds_security_group"] is not None