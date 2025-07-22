"""
Main infrastructure program with AWS Secrets Manager integration.
This is an improved version that eliminates the need for manual password configuration.
"""
import pulumi
import pulumi_aws as aws

# Import modules
from networking.vpc import create_vpc
from security.kms import create_kms_key
from security.iam import create_iam_roles
from security.security_groups import create_security_groups
from security.cloudtrail import create_cloudtrail
from security.guardduty import create_guardduty
from security.config import create_config
from security.secrets import create_database_secret, update_database_secret
from database.rds import create_rds_instance
from compute.ecs import create_ecs_cluster
from compute.alb import create_alb
from monitoring.cloudwatch import create_cloudwatch_logs


def main():
    """Main infrastructure deployment with Secrets Manager."""
    config = pulumi.Config()
    environment = config.get("environment", "dev")
    
    # 1. Create KMS key (needed for encryption)
    kms_resources = create_kms_key()
    
    # 2. Create database secrets FIRST (before RDS)
    secrets_resources = create_database_secret(environment, kms_resources["kms_key"].id)
    
    # 3. Create networking
    vpc_resources = create_vpc()
    
    # 4. Create security groups
    sg_resources = create_security_groups(vpc_resources["vpc"])
    
    # 5. Create IAM roles (now includes Secrets Manager permissions)
    iam_resources = create_iam_roles()
    
    # 6. Create RDS with secrets
    db_resources = create_rds_instance(
        vpc_resources["private_subnets"],
        sg_resources["rds_security_group"],
        secrets_info={
            "db_password": secrets_resources["db_password"]
        }
    )
    
    # 7. Update secret with actual database endpoint
    update_database_secret(
        secrets_resources["db_secret"].arn,
        db_resources["db_instance"].endpoint,
        environment
    )
    
    # 8. Create compute resources
    ecs_resources = create_ecs_cluster()
    alb_resources = create_alb(
        vpc_resources["public_subnets"],
        sg_resources["alb_security_group"],
        vpc_resources["vpc"]
    )
    
    # 9. Create security monitoring
    cloudtrail_resources = create_cloudtrail()
    guardduty_resources = create_guardduty()
    config_resources = create_config()
    
    # 10. Create CloudWatch logs
    log_resources = create_cloudwatch_logs()
    
    # Export important outputs
    pulumi.export("vpc_id", vpc_resources["vpc"].id)
    pulumi.export("public_subnet_ids", [subnet.id for subnet in vpc_resources["public_subnets"]])
    pulumi.export("private_subnet_ids", [subnet.id for subnet in vpc_resources["private_subnets"]])
    
    pulumi.export("alb_dns_name", alb_resources["alb"].dns_name)
    pulumi.export("alb_zone_id", alb_resources["alb"].zone_id)
    
    pulumi.export("database_endpoint", db_resources["db_instance"].endpoint)
    pulumi.export("database_secret_arn", secrets_resources["db_secret"].arn)
    pulumi.export("jwt_secret_arn", secrets_resources["jwt_secret"].arn)
    
    pulumi.export("ecs_cluster_name", ecs_resources["cluster"].name)
    pulumi.export("ecr_repository_url", ecs_resources["repository"].repository_url)
    
    pulumi.export("kms_key_id", kms_resources["kms_key"].key_id)
    pulumi.export("kms_key_arn", kms_resources["kms_key"].arn)
    
    pulumi.export("cloudtrail_arn", cloudtrail_resources["cloudtrail"].arn)
    pulumi.export("guardduty_detector_id", guardduty_resources["guardduty_detector"].id)
    pulumi.export("config_recorder_name", config_resources["config_recorder"].name)
    
    # Export IAM role ARNs
    pulumi.export("ecs_task_execution_role_arn", iam_resources["ecs_task_execution_role"].arn)
    pulumi.export("ecs_task_role_arn", iam_resources["ecs_task_role"].arn)
    
    # Export task definition ARN (if using ECS service)
    if "task_definition" in ecs_resources:
        pulumi.export("task_definition_arn", ecs_resources["task_definition"].arn)
        pulumi.export("ecs_service_name", ecs_resources["service"].name)


if __name__ == "__main__":
    main()