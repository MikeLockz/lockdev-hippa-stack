"""GuardDuty configuration for threat detection."""
import pulumi
import pulumi_aws as aws


def create_guardduty():
    """Create GuardDuty for threat detection."""
    config = pulumi.Config()
    
    # Enable GuardDuty detector
    guardduty_detector = aws.guardduty.Detector(
        "hipaa-guardduty-detector",
        enable=True,
        finding_publishing_frequency="FIFTEEN_MINUTES",
        datasources=aws.guardduty.DetectorDatasourcesArgs(
            s3_logs=aws.guardduty.DetectorDatasourcesS3LogsArgs(
                enable=True
            ),
            kubernetes=aws.guardduty.DetectorDatasourcesKubernetesArgs(
                audit_logs=aws.guardduty.DetectorDatasourcesKubernetesAuditLogsArgs(
                    enable=True
                )
            ),
            malware_protection=aws.guardduty.DetectorDatasourcesMalwareProtectionArgs(
                scan_ec2_instance_with_findings=aws.guardduty.DetectorDatasourcesMalwareProtectionScanEc2InstanceWithFindingsArgs(
                    ebs_volumes=aws.guardduty.DetectorDatasourcesMalwareProtectionScanEc2InstanceWithFindingsEbsVolumesArgs(
                        enable=True
                    )
                )
            )
        ),
        tags={
            "Name": "HIPAA-GuardDuty-Detector",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Create SNS topic for GuardDuty findings
    guardduty_sns_topic = aws.sns.Topic(
        "guardduty-findings-topic",
        name="hipaa-guardduty-findings",
        tags={
            "Name": "HIPAA-GuardDuty-Findings",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Create EventBridge rule for GuardDuty findings
    guardduty_eventbridge_rule = aws.cloudwatch.EventRule(
        "guardduty-findings-rule",
        name="hipaa-guardduty-findings-rule",
        description="Capture GuardDuty findings",
        event_pattern=pulumi.Output.all().apply(lambda _: """{
            "source": ["aws.guardduty"],
            "detail-type": ["GuardDuty Finding"],
            "detail": {
                "severity": [4.0, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 5.0, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 6.0, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 7.0, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 8.0, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 9.0, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9, 10.0]
            }
        }"""),
        tags={
            "Name": "HIPAA-GuardDuty-Findings-Rule",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Create EventBridge target for SNS
    guardduty_eventbridge_target = aws.cloudwatch.EventTarget(
        "guardduty-findings-target",
        rule=guardduty_eventbridge_rule.name,
        target_id="GuardDutyFindingsTarget",
        arn=guardduty_sns_topic.arn
    )
    
    # Create CloudWatch log group for GuardDuty findings
    guardduty_log_group = aws.cloudwatch.LogGroup(
        "guardduty-log-group",
        name="/aws/guardduty/findings",
        retention_in_days=90,
        tags={
            "Name": "HIPAA-GuardDuty-Logs",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Note: IPSet and ThreatIntelSet removed due to permission requirements
    # and S3 bucket dependencies. Can be added later with proper setup.
    
    return {
        "guardduty_detector": guardduty_detector,
        "guardduty_sns_topic": guardduty_sns_topic,
        "guardduty_eventbridge_rule": guardduty_eventbridge_rule,
        "guardduty_log_group": guardduty_log_group
    }