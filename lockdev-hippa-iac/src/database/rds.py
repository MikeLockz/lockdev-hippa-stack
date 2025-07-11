"""RDS PostgreSQL database for HIPAA compliance."""
import pulumi
import pulumi_aws as aws
from typing import List


def create_rds_instance(private_subnets: List[aws.ec2.Subnet], security_group: aws.ec2.SecurityGroup) -> aws.rds.Instance:
    """Create HIPAA compliant RDS PostgreSQL instance."""
    config = pulumi.Config()
    
    # Create DB subnet group
    db_subnet_group = aws.rds.SubnetGroup(
        "hipaa-db-subnet-group",
        name="hipaa-db-subnet-group",
        subnet_ids=[subnet.id for subnet in private_subnets],
        tags={
            "Name": "HIPAA-DB-Subnet-Group",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Create parameter group
    parameter_group = aws.rds.ParameterGroup(
        "hipaa-db-parameter-group",
        family="postgres13",
        name="hipaa-postgres-params",
        description="Parameter group for HIPAA compliant PostgreSQL",
        parameters=[
            aws.rds.ParameterGroupParameterArgs(
                name="log_statement",
                value="all"
            ),
            aws.rds.ParameterGroupParameterArgs(
                name="log_min_duration_statement",
                value="1000"
            ),
            aws.rds.ParameterGroupParameterArgs(
                name="rds.force_ssl",
                value="1"
            )
        ],
        tags={
            "Name": "HIPAA-DB-Parameter-Group",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Create RDS instance
    db_instance = aws.rds.Instance(
        "hipaa-database",
        identifier="hipaa-postgres-db",
        engine="postgres",
        engine_version="13.7",
        instance_class="db.t3.micro",
        allocated_storage=20,
        max_allocated_storage=100,
        storage_type="gp2",
        storage_encrypted=True,
        
        db_name="hipaa_app",
        username="postgres",
        password=config.require_secret("db_password"),
        
        vpc_security_group_ids=[security_group.id],
        db_subnet_group_name=db_subnet_group.name,
        parameter_group_name=parameter_group.name,
        
        backup_retention_period=7,
        backup_window="03:00-04:00",
        maintenance_window="sun:04:00-sun:05:00",
        
        multi_az=False,  # Set to True for production
        publicly_accessible=False,
        
        enabled_cloudwatch_logs_exports=["postgresql"],
        
        deletion_protection=True,
        skip_final_snapshot=False,
        final_snapshot_identifier="hipaa-db-final-snapshot",
        
        tags={
            "Name": "HIPAA-PostgreSQL-DB",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    return db_instance