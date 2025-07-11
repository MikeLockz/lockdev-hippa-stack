"""AWS Config configuration for compliance monitoring."""
import pulumi
import pulumi_aws as aws
import json


def create_config():
    """Create AWS Config for compliance monitoring."""
    config = pulumi.Config()
    
    # Get current AWS account ID
    current = aws.get_caller_identity()
    
    # Create S3 bucket for Config
    config_bucket = aws.s3.Bucket(
        "config-bucket",
        bucket=f"hipaa-config-bucket-{config.get('environment', 'dev')}-{current.account_id}",
        force_destroy=True,
        tags={
            "Name": "HIPAA-Config-Bucket",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Enable S3 bucket versioning
    aws.s3.BucketVersioningV2(
        "config-bucket-versioning",
        bucket=config_bucket.id,
        versioning_configuration=aws.s3.BucketVersioningV2VersioningConfigurationArgs(
            status="Enabled"
        )
    )
    
    # Block public access
    aws.s3.BucketPublicAccessBlock(
        "config-bucket-pab",
        bucket=config_bucket.id,
        block_public_acls=True,
        block_public_policy=True,
        ignore_public_acls=True,
        restrict_public_buckets=True
    )
    
    # Create IAM role for Config
    config_role = aws.iam.Role(
        "config-role",
        name="hipaa-config-role",
        assume_role_policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "config.amazonaws.com"
                    }
                }
            ]
        }),
        tags={
            "Name": "HIPAA-Config-Role",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Attach AWS managed policy for Config
    aws.iam.RolePolicyAttachment(
        "config-role-policy",
        role=config_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/ConfigRole"
    )
    
    # Create custom policy for Config S3 access
    config_s3_policy = aws.iam.Policy(
        "config-s3-policy",
        name="hipaa-config-s3-policy",
        description="Policy for Config S3 access",
        policy=pulumi.Output.all(config_bucket.id, current.account_id).apply(
            lambda args: json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetBucketAcl",
                            "s3:GetBucketLocation"
                        ],
                        "Resource": f"arn:aws:s3:::{args[0]}"
                    },
                    {
                        "Effect": "Allow",
                        "Action": "s3:PutObject",
                        "Resource": f"arn:aws:s3:::{args[0]}/*",
                        "Condition": {
                            "StringEquals": {
                                "s3:x-amz-acl": "bucket-owner-full-control"
                            }
                        }
                    },
                    {
                        "Effect": "Allow",
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{args[0]}/*"
                    }
                ]
            })
        ),
        tags={
            "Name": "HIPAA-Config-S3-Policy",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Attach S3 policy to Config role
    aws.iam.RolePolicyAttachment(
        "config-s3-role-policy-attachment",
        role=config_role.name,
        policy_arn=config_s3_policy.arn
    )
    
    # Create Config delivery channel
    config_delivery_channel = aws.cfg.DeliveryChannel(
        "config-delivery-channel",
        name="hipaa-config-delivery-channel",
        s3_bucket_name=config_bucket.id,
        s3_key_prefix="config",
        snapshot_delivery_properties=aws.cfg.DeliveryChannelSnapshotDeliveryPropertiesArgs(
            delivery_frequency="TwentyFour_Hours"
        )
    )
    
    # Create Config configuration recorder
    config_recorder = aws.cfg.Recorder(
        "config-recorder",
        name="hipaa-config-recorder",
        role_arn=config_role.arn,
        recording_group=aws.cfg.RecorderRecordingGroupArgs(
            all_supported=True,
            include_global_resource_types=True
        )
    )
    
    # Create Config rules for HIPAA compliance
    
    # Rule: Ensure RDS instances are encrypted
    rds_encrypted_rule = aws.cfg.Rule(
        "rds-storage-encrypted",
        name="rds-storage-encrypted",
        description="Checks whether storage encryption is enabled for RDS instances",
        source=aws.cfg.RuleSourceArgs(
            owner="AWS",
            source_identifier="RDS_STORAGE_ENCRYPTED"
        ),
        opts=pulumi.ResourceOptions(depends_on=[config_recorder])
    )
    
    # Rule: Ensure S3 buckets are encrypted
    s3_encrypted_rule = aws.cfg.Rule(
        "s3-bucket-server-side-encryption-enabled",
        name="s3-bucket-server-side-encryption-enabled",
        description="Checks whether S3 buckets have server-side encryption enabled",
        source=aws.cfg.RuleSourceArgs(
            owner="AWS",
            source_identifier="S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED"
        ),
        opts=pulumi.ResourceOptions(depends_on=[config_recorder])
    )
    
    # Rule: Ensure CloudTrail is enabled
    cloudtrail_enabled_rule = aws.cfg.Rule(
        "cloudtrail-enabled",
        name="cloudtrail-enabled",
        description="Checks whether CloudTrail is enabled",
        source=aws.cfg.RuleSourceArgs(
            owner="AWS",
            source_identifier="CLOUD_TRAIL_ENABLED"
        ),
        opts=pulumi.ResourceOptions(depends_on=[config_recorder])
    )
    
    # Rule: Ensure security groups don't allow unrestricted SSH access
    sg_ssh_restricted_rule = aws.cfg.Rule(
        "incoming-ssh-disabled",
        name="incoming-ssh-disabled",
        description="Checks whether security groups disallow unrestricted SSH access",
        source=aws.cfg.RuleSourceArgs(
            owner="AWS",
            source_identifier="INCOMING_SSH_DISABLED"
        ),
        opts=pulumi.ResourceOptions(depends_on=[config_recorder])
    )
    
    # Rule: Ensure root access key is not used
    root_access_key_rule = aws.cfg.Rule(
        "root-access-key-check",
        name="root-access-key-check",
        description="Checks whether root access keys exist",
        source=aws.cfg.RuleSourceArgs(
            owner="AWS",
            source_identifier="ROOT_ACCESS_KEY_CHECK"
        ),
        opts=pulumi.ResourceOptions(depends_on=[config_recorder])
    )
    
    # Rule: Ensure MFA is enabled for root account
    mfa_enabled_rule = aws.cfg.Rule(
        "mfa-enabled-for-iam-console-access",
        name="mfa-enabled-for-iam-console-access",
        description="Checks whether MFA is enabled for IAM users",
        source=aws.cfg.RuleSourceArgs(
            owner="AWS",
            source_identifier="MFA_ENABLED_FOR_IAM_CONSOLE_ACCESS"
        ),
        opts=pulumi.ResourceOptions(depends_on=[config_recorder])
    )
    
    return {
        "config_bucket": config_bucket,
        "config_role": config_role,
        "config_delivery_channel": config_delivery_channel,
        "config_recorder": config_recorder,
        "config_rules": {
            "rds_encrypted": rds_encrypted_rule,
            "s3_encrypted": s3_encrypted_rule,
            "cloudtrail_enabled": cloudtrail_enabled_rule,
            "sg_ssh_restricted": sg_ssh_restricted_rule,
            "root_access_key": root_access_key_rule,
            "mfa_enabled": mfa_enabled_rule
        }
    }