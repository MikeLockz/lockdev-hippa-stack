"""CloudTrail configuration for audit logging."""
import pulumi
import pulumi_aws as aws
import json


def create_cloudtrail():
    """Create CloudTrail for comprehensive audit logging."""
    config = pulumi.Config()
    
    # Get current AWS account ID
    current = aws.get_caller_identity()
    
    # Create S3 bucket for CloudTrail logs
    cloudtrail_bucket = aws.s3.Bucket(
        "cloudtrail-bucket",
        bucket=f"hipaa-cloudtrail-logs-{config.get('environment', 'dev')}-{current.account_id}",
        force_destroy=True,
        tags={
            "Name": "HIPAA-CloudTrail-Logs",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Enable S3 bucket versioning
    aws.s3.BucketVersioningV2(
        "cloudtrail-bucket-versioning",
        bucket=cloudtrail_bucket.id,
        versioning_configuration=aws.s3.BucketVersioningV2VersioningConfigurationArgs(
            status="Enabled"
        )
    )
    
    # Enable S3 bucket server-side encryption
    aws.s3.BucketServerSideEncryptionConfigurationV2(
        "cloudtrail-bucket-encryption",
        bucket=cloudtrail_bucket.id,
        rules=[
            aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
                apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
                    sse_algorithm="AES256"
                )
            )
        ]
    )
    
    # Block public access
    aws.s3.BucketPublicAccessBlock(
        "cloudtrail-bucket-pab",
        bucket=cloudtrail_bucket.id,
        block_public_acls=True,
        block_public_policy=True,
        ignore_public_acls=True,
        restrict_public_buckets=True
    )
    
    # Create bucket policy for CloudTrail
    bucket_policy = aws.s3.BucketPolicy(
        "cloudtrail-bucket-policy",
        bucket=cloudtrail_bucket.id,
        policy=pulumi.Output.all(cloudtrail_bucket.id, current.account_id).apply(
            lambda args: json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AWSCloudTrailAclCheck",
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "cloudtrail.amazonaws.com"
                        },
                        "Action": "s3:GetBucketAcl",
                        "Resource": f"arn:aws:s3:::{args[0]}",
                        "Condition": {
                            "StringEquals": {
                                "AWS:SourceAccount": args[1]
                            }
                        }
                    },
                    {
                        "Sid": "AWSCloudTrailWrite",
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "cloudtrail.amazonaws.com"
                        },
                        "Action": "s3:PutObject",
                        "Resource": f"arn:aws:s3:::{args[0]}/*",
                        "Condition": {
                            "StringEquals": {
                                "s3:x-amz-acl": "bucket-owner-full-control",
                                "AWS:SourceAccount": args[1]
                            }
                        }
                    }
                ]
            })
        )
    )
    
    # Create CloudWatch log group for CloudTrail
    cloudtrail_log_group = aws.cloudwatch.LogGroup(
        "cloudtrail-log-group",
        name="/aws/cloudtrail/hipaa-audit-trail",
        retention_in_days=90,
        tags={
            "Name": "HIPAA-CloudTrail-Logs",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Create CloudWatch role for CloudTrail
    cloudtrail_role = aws.iam.Role(
        "cloudtrail-role",
        name="hipaa-cloudtrail-role",
        assume_role_policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "cloudtrail.amazonaws.com"
                    }
                }
            ]
        }),
        tags={
            "Name": "HIPAA-CloudTrail-Role",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Create CloudWatch policy for CloudTrail
    cloudtrail_policy = aws.iam.Policy(
        "cloudtrail-policy",
        name="hipaa-cloudtrail-policy",
        description="Policy for HIPAA CloudTrail logging",
        policy=pulumi.Output.all(cloudtrail_log_group.arn).apply(
            lambda args: json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                            "logs:DescribeLogGroups",
                            "logs:DescribeLogStreams"
                        ],
                        "Resource": f"{args[0]}*"
                    }
                ]
            })
        ),
        tags={
            "Name": "HIPAA-CloudTrail-Policy",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Attach policy to role
    aws.iam.RolePolicyAttachment(
        "cloudtrail-role-policy-attachment",
        role=cloudtrail_role.name,
        policy_arn=cloudtrail_policy.arn
    )
    
    # Create CloudTrail
    cloudtrail = aws.cloudtrail.Trail(
        "hipaa-cloudtrail",
        name="hipaa-audit-trail",
        s3_bucket_name=cloudtrail_bucket.id,
        include_global_service_events=True,
        is_multi_region_trail=True,
        enable_logging=True,
        cloud_watch_logs_group_arn=cloudtrail_log_group.arn.apply(lambda arn: f"{arn}:*"),
        cloud_watch_logs_role_arn=cloudtrail_role.arn,
        event_selectors=[
            aws.cloudtrail.TrailEventSelectorArgs(
                read_write_type="All",
                include_management_events=True,
                data_resources=[
                    aws.cloudtrail.TrailEventSelectorDataResourceArgs(
                        type="AWS::S3::Object",
                        values=["arn:aws:s3"]
                    )
                ]
            )
        ],
        tags={
            "Name": "HIPAA-CloudTrail",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    return {
        "cloudtrail_bucket": cloudtrail_bucket,
        "cloudtrail": cloudtrail,
        "cloudtrail_log_group": cloudtrail_log_group,
        "cloudtrail_role": cloudtrail_role
    }