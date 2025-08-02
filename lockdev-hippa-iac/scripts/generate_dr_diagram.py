#!/usr/bin/env python3
"""
Phase 7: Disaster Recovery Architecture Diagram Generator
Generates comprehensive disaster recovery visualization for HIPAA-compliant AWS stack
including multi-AZ deployments, backup strategies, failover mechanisms, and RTO/RPO indicators
"""

import subprocess
import json
import os
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.network import VPC, CloudFront, Route53
from diagrams.aws.compute import ECS, AutoScaling, Lambda
from diagrams.aws.database import RDS, Dynamodb
from diagrams.aws.storage import S3, EFS
from diagrams.aws.security import KMS, IAM, Shield
from diagrams.aws.management import Cloudformation
from diagrams.aws.management import Cloudwatch
from diagrams.aws.integration import SNS, SQS
from diagrams.onprem.client import Users
from diagrams.generic.storage import Storage
from diagrams.generic.compute import Rack
import argparse
import logging
from drawio_utils import DrawIOGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DisasterRecoveryDiagramGenerator:
    def __init__(self, stack_name="hipaa-dev", output_dir="./output"):
        self.stack_name = stack_name
        self.output_dir = output_dir
        self.dr_config = self._get_dr_config()
        
    def _get_dr_config(self):
        """Get disaster recovery configuration"""
        return {
            'rto_minutes': 15,
            'rpo_minutes': 5,
            'backup_retention_days': 35,
            'cross_region_backup': True,
            'multi_az': True,
            'auto_failover': True
        }
    
    def create_disaster_recovery_diagram(self):
        """Create comprehensive disaster recovery architecture diagram"""
        filename = f"{self.output_dir}/disaster_recovery_architecture"
        
        with Diagram(
            "HIPAA Disaster Recovery Architecture",
            filename=filename,
            show=False,
            direction="LR",
            graph_attr={
                "bgcolor": "white",
                "pad": "0.5",
                "ranksep": "2.0",
                "nodesep": "1.5",
                "fontname": "Arial",
                "fontsize": "12"
            }
        ):
            # Primary Region
            with Cluster("Primary Region (us-east-1)"):
                with Cluster("Primary VPC"):
                    # Multi-AZ Database
                    with Cluster("Multi-AZ Database"):
                        rds_primary = RDS("RDS Primary\n(AZ-1)")
                        rds_standby = RDS("RDS Standby\n(AZ-2)")
                        rds_backup = Storage("Automated Backups\n(35 days)")
                        
                        rds_primary >> Edge(label="SYNC") >> rds_standby
                        rds_primary >> Edge(label="BACKUP") >> rds_backup
                    
                    # ECS Cluster
                    with Cluster("ECS Fargate Cluster"):
                        ecs_service1 = ECS("Service AZ-1")
                        ecs_service2 = ECS("Service AZ-2")
                        auto_scaling = AutoScaling("Auto Scaling")
                        
                        ecs_service1 >> auto_scaling
                        ecs_service2 >> auto_scaling
                    
                    # Storage
                    with Cluster("Primary Storage"):
                        s3_primary = S3("S3 Primary\n(Encrypted)")
                        efs_primary = EFS("EFS Primary\n(Multi-AZ)")
                        
                    # Monitoring
                    cloudwatch = Cloudwatch("CloudWatch\nMonitoring")
            
            # Secondary Region
            with Cluster("Secondary Region (us-west-2)"):
                with Cluster("DR VPC"):
                    # Cross-region resources
                    with Cluster("DR Database"):
                        rds_dr = RDS("RDS DR\n(Restore Point)")
                        backup_restore = Storage("Cross-Region\nBackup Restore")
                        
                    # DR Storage
                    with Cluster("DR Storage"):
                        s3_dr = S3("S3 Cross-Region\nReplication")
                        glacier = S3("Glacier\nArchive")
                        
                    # DR Infrastructure
                    with Cluster("DR Infrastructure"):
                        ecs_dr = ECS("DR ECS\n(Stopped)")
                        lambda_warmup = Lambda("Warmup Function")
            
            # DNS & Traffic Management
            route53 = Route53("Route 53\nHealth Checks")
            cloudfront = CloudFront("CloudFront\nCDN")
            
            # Security & Encryption
            kms_primary = KMS("KMS Primary\n(Encryption Keys)")
            kms_dr = KMS("KMS DR\n(Replica Keys)")
            shield = Shield("AWS Shield\n(DDoS Protection)")
            
            # Notification & Orchestration
            sns = SNS("SNS Alerts")
            sqs = SQS("SQS Queues")
            
            # Backup & Recovery Flow
            with Cluster("Backup Strategy"):
                daily_backup = Storage("Daily Snapshots")
                weekly_backup = Storage("Weekly Backups")
                monthly_archive = Storage("Monthly Archive\n(Glacier)")
                
                daily_backup >> weekly_backup >> monthly_archive
            
            # Connections
            # Primary flow
            rds_primary >> Edge(label="CROSS-REGION\nREPLICATION") >> rds_dr
            s3_primary >> Edge(label="REPLICATE") >> s3_dr
            kms_primary >> Edge(label="REPLICATE") >> kms_dr
            
            # Health monitoring
            route53 >> Edge(label="HEALTH CHECK") >> ecs_service1
            route53 >> Edge(label="HEALTH CHECK") >> ecs_service2
            
            # Auto-scaling triggers
            cloudwatch >> Edge(label="TRIGGER") >> auto_scaling
            cloudwatch >> Edge(label="ALERT") >> sns
            
            # DR activation
            sns >> Edge(label="ACTIVATE DR") >> lambda_warmup
            lambda_warmup >> Edge(label="START") >> ecs_dr
            
            # User access
            users = Users("Users")
            users >> cloudfront >> route53
            
            # Encryption
            kms_primary >> Edge(label="ENCRYPT") >> [rds_primary, s3_primary, efs_primary]
            kms_dr >> Edge(label="ENCRYPT") >> [rds_dr, s3_dr]
    
    def create_dr_flow_diagram(self):
        """Create detailed disaster recovery flow diagram"""
        filename = f"{self.output_dir}/dr_flow_process"
        
        with Diagram(
            "Disaster Recovery Process Flow",
            filename=filename,
            show=False,
            direction="TB",
            graph_attr={
                "bgcolor": "white",
                "pad": "0.5",
                "ranksep": "1.5",
                "fontname": "Arial",
                "fontsize": "10"
            }
        ):
            # RTO/RPO Indicators
            with Cluster("Recovery Objectives"):
                rto = Storage("RTO: 15 minutes\n(Recovery Time)")
                rpo = Storage("RPO: 5 minutes\n(Recovery Point)")
                sla = Storage("SLA: 99.9%\nAvailability")
            
            # Monitoring & Detection
            with Cluster("Monitoring & Detection"):
                health_checks = Cloudwatch("Health Checks")
                metric_alarms = Cloudwatch("Metric Alarms")
                incident_detection = Lambda("Incident Detection")
            
            # Decision Process
            with Cluster("Decision Process"):
                incident_assessment = Lambda("Assess Incident")
                dr_decision = Lambda("DR Decision")
                notification = SNS("Stakeholder Alert")
            
            # DR Activation
            with Cluster("DR Activation"):
                initiate_dr = Lambda("Initiate DR")
                route_failover = Route53("DNS Failover")
                scale_up_dr = AutoScaling("Scale Up DR")
            
            # Recovery Process
            with Cluster("Recovery Process"):
                restore_database = RDS("Database Restore")
                sync_storage = S3("Storage Sync")
                validate_services = Lambda("Service Validation")
            
            # Post-Recovery
            with Cluster("Post-Recovery"):
                health_validation = Cloudwatch("Health Validation")
                performance_monitoring = Cloudwatch("Performance Check")
                incident_review = Lambda("Post-Incident Review")
            
            # Flow connections
            health_checks >> metric_alarms >> incident_detection
            incident_detection >> incident_assessment >> dr_decision
            dr_decision >> notification
            dr_decision >> initiate_dr
            
            initiate_dr >> route_failover
            initiate_dr >> scale_up_dr
            initiate_dr >> restore_database
            
            restore_database >> sync_storage >> validate_services
            validate_services >> health_validation >> performance_monitoring
            performance_monitoring >> incident_review
    
    def create_backup_strategy_diagram(self):
        """Create backup and retention strategy diagram"""
        filename = f"{self.output_dir}/backup_strategy"
        
        with Diagram(
            "Backup & Retention Strategy",
            filename=filename,
            show=False,
            direction="LR",
            graph_attr={
                "bgcolor": "white",
                "pad": "0.5",
                "ranksep": "2.0",
                "fontname": "Arial",
                "fontsize": "10"
            }
        ):
            # Backup Sources
            with Cluster("Backup Sources"):
                rds_source = RDS("RDS Database")
                s3_source = S3("S3 Buckets")
                efs_source = EFS("EFS File Systems")
            
            # Backup Targets
            with Cluster("Backup Targets"):
                daily_backup = S3("Daily Snapshots\n(7 days)")
                weekly_backup = S3("Weekly Backups\n(4 weeks)")
                monthly_backup = S3("Monthly Backups\n(12 months)")
                glacier_archive = S3("Archive\n(S3 Glacier\n7 years)")
            
            # Cross-Region
            with Cluster("Cross-Region"):
                replication = S3("Cross-Region\nReplication")
                dr_backup = S3("DR Region\nBackup")
            
            # Encryption
            kms = KMS("KMS Encryption")
            
            # Connections
            [rds_source, s3_source, efs_source] >> daily_backup >> weekly_backup >> monthly_backup >> glacier_archive
            daily_backup >> replication >> dr_backup
            kms >> Edge(label="ENCRYPT") >> [daily_backup, weekly_backup, monthly_backup, glacier_archive]
    
    def create_dr_flow_drawio(self):
        """Create draw.io XML for disaster recovery flow diagram"""
        drawio_gen = DrawIOGenerator(self.output_dir)
        
        mxfile = drawio_gen.create_mxfile("Disaster Recovery Process Flow", "dr_flow")
        diagram = drawio_gen.create_diagram(mxfile, "Disaster Recovery Process Flow", "dr_flow")
        mxgraphmodel = drawio_gen.create_graph_model(diagram)
        root = drawio_gen.create_root(mxgraphmodel)
        
        # Recovery Objectives
        obj_container = drawio_gen.add_swimlane(root, "objectives", "Recovery Objectives", 50, 50, 700, 100)
        drawio_gen.add_rectangle(root, "rto", "RTO: 15 minutes\n(Recovery Time)", 50, 30, 150, 50, parent="objectives")
        drawio_gen.add_rectangle(root, "rpo", "RPO: 5 minutes\n(Recovery Point)", 220, 30, 150, 50, parent="objectives")
        drawio_gen.add_rectangle(root, "sla", "SLA: 99.9%\nAvailability", 390, 30, 150, 50, parent="objectives")
        
        # Monitoring & Detection
        monitor_container = drawio_gen.add_swimlane(root, "monitoring", "Monitoring & Detection", 50, 170, 700, 100)
        drawio_gen.add_rectangle(root, "health_checks", "Health Checks", 50, 30, 150, 50, parent="monitoring")
        drawio_gen.add_rectangle(root, "metric_alarms", "Metric Alarms", 220, 30, 150, 50, parent="monitoring")
        drawio_gen.add_rectangle(root, "incident_detection", "Incident Detection", 390, 30, 150, 50, parent="monitoring")
        
        # Decision Process
        decision_container = drawio_gen.add_swimlane(root, "decision", "Decision Process", 50, 290, 700, 100)
        drawio_gen.add_rectangle(root, "assessment", "Assess Incident", 50, 30, 150, 50, parent="decision")
        drawio_gen.add_rectangle(root, "dr_decision", "DR Decision", 220, 30, 150, 50, parent="decision")
        drawio_gen.add_rectangle(root, "notification", "Stakeholder Alert", 390, 30, 150, 50, parent="decision")
        
        # DR Activation
        activation_container = drawio_gen.add_swimlane(root, "activation", "DR Activation", 50, 410, 700, 100)
        drawio_gen.add_rectangle(root, "initiate", "Initiate DR", 50, 30, 150, 50, parent="activation")
        drawio_gen.add_rectangle(root, "failover", "DNS Failover", 220, 30, 150, 50, parent="activation")
        drawio_gen.add_rectangle(root, "scale_up", "Scale Up DR", 390, 30, 150, 50, parent="activation")
        
        # Recovery Process
        recovery_container = drawio_gen.add_swimlane(root, "recovery", "Recovery Process", 50, 530, 700, 100)
        drawio_gen.add_cylinder(root, "restore_db", "Database Restore", 50, 30, 120, 50, parent="recovery")
        drawio_gen.add_cylinder(root, "sync_storage", "Storage Sync", 200, 30, 120, 50, parent="recovery")
        drawio_gen.add_rectangle(root, "validate", "Service Validation", 370, 30, 150, 50, parent="recovery")
        
        # Post-Recovery
        post_container = drawio_gen.add_swimlane(root, "post", "Post-Recovery", 50, 650, 700, 100)
        drawio_gen.add_rectangle(root, "health_val", "Health Validation", 50, 30, 150, 50, parent="post")
        drawio_gen.add_rectangle(root, "perf_check", "Performance Check", 220, 30, 150, 50, parent="post")
        drawio_gen.add_rectangle(root, "review", "Post-Incident Review", 390, 30, 150, 50, parent="post")
        
        # Connections
        drawio_gen.add_edge(root, "e1", "health_checks", "metric_alarms", parent="monitoring")
        drawio_gen.add_edge(root, "e2", "metric_alarms", "incident_detection", parent="monitoring")
        drawio_gen.add_edge(root, "e3", "incident_detection", "assessment", parent="decision")
        drawio_gen.add_edge(root, "e4", "assessment", "dr_decision", parent="decision")
        drawio_gen.add_edge(root, "e5", "dr_decision", "notification", parent="decision")
        drawio_gen.add_edge(root, "e6", "dr_decision", "initiate", parent="activation")
        drawio_gen.add_edge(root, "e7", "initiate", "failover", parent="activation")
        drawio_gen.add_edge(root, "e8", "initiate", "scale_up", parent="activation")
        drawio_gen.add_edge(root, "e9", "initiate", "restore_db", parent="recovery")
        drawio_gen.add_edge(root, "e10", "restore_db", "sync_storage", parent="recovery")
        drawio_gen.add_edge(root, "e11", "sync_storage", "validate", parent="recovery")
        drawio_gen.add_edge(root, "e12", "validate", "health_val", parent="post")
        drawio_gen.add_edge(root, "e13", "health_val", "perf_check", parent="post")
        drawio_gen.add_edge(root, "e14", "perf_check", "review", parent="post")
        
        return drawio_gen.save_drawio_file(mxfile, "dr_flow_process.drawio")

    def create_backup_strategy_drawio(self):
        """Create draw.io XML for backup strategy diagram"""
        drawio_gen = DrawIOGenerator(self.output_dir)
        
        mxfile = drawio_gen.create_mxfile("Backup & Retention Strategy", "backup_strategy")
        diagram = drawio_gen.create_diagram(mxfile, "Backup & Retention Strategy", "backup_strategy")
        mxgraphmodel = drawio_gen.create_graph_model(diagram)
        root = drawio_gen.create_root(mxgraphmodel)
        
        # Backup Sources
        sources_container = drawio_gen.add_swimlane(root, "sources", "Backup Sources", 50, 50, 200, 300)
        drawio_gen.add_cylinder(root, "rds_source", "RDS Database", 50, 50, 120, 50, parent="sources")
        drawio_gen.add_cylinder(root, "s3_source", "S3 Buckets", 50, 120, 120, 50, parent="sources")
        drawio_gen.add_cylinder(root, "efs_source", "EFS File Systems", 50, 190, 120, 50, parent="sources")
        
        # Backup Targets
        targets_container = drawio_gen.add_swimlane(root, "targets", "Backup Targets", 300, 50, 500, 300)
        drawio_gen.add_cylinder(root, "daily", "Daily Snapshots\n(7 days)", 50, 50, 120, 50, parent="targets")
        drawio_gen.add_cylinder(root, "weekly", "Weekly Backups\n(4 weeks)", 50, 120, 120, 50, parent="targets")
        drawio_gen.add_cylinder(root, "monthly", "Monthly Backups\n(12 months)", 50, 190, 120, 50, parent="targets")
        drawio_gen.add_cylinder(root, "glacier", "Archive\n(S3 Glacier\n7 years)", 200, 120, 120, 50, parent="targets")
        
        # Cross-Region
        cross_container = drawio_gen.add_swimlane(root, "cross", "Cross-Region", 50, 370, 500, 150)
        drawio_gen.add_cylinder(root, "replication", "Cross-Region\nReplication", 50, 50, 120, 50, parent="cross")
        drawio_gen.add_cylinder(root, "dr_backup", "DR Region\nBackup", 200, 50, 120, 50, parent="cross")
        
        # Encryption
        drawio_gen.add_rectangle(root, "kms", "KMS Encryption", 650, 200, 120, 50)
        
        # Connections
        drawio_gen.add_edge(root, "e1", "rds_source", "daily")
        drawio_gen.add_edge(root, "e2", "s3_source", "daily")
        drawio_gen.add_edge(root, "e3", "efs_source", "daily")
        drawio_gen.add_edge(root, "e4", "daily", "weekly", parent="targets")
        drawio_gen.add_edge(root, "e5", "weekly", "monthly", parent="targets")
        drawio_gen.add_edge(root, "e6", "monthly", "glacier", parent="targets")
        drawio_gen.add_edge(root, "e7", "daily", "replication", parent="cross")
        drawio_gen.add_edge(root, "e8", "replication", "dr_backup", parent="cross")
        drawio_gen.add_edge(root, "e9", "kms", "daily")
        drawio_gen.add_edge(root, "e10", "kms", "weekly")
        drawio_gen.add_edge(root, "e11", "kms", "monthly")
        drawio_gen.add_edge(root, "e12", "kms", "glacier")
        
        return drawio_gen.save_drawio_file(mxfile, "backup_strategy.drawio")

    def validate_diagram(self):
        """Validate generated disaster recovery diagrams"""
        diagrams_to_check = [
            "disaster_recovery_architecture.png",
            "disaster_recovery_architecture.drawio",
            "dr_flow_process.png",
            "dr_flow_process.drawio",
            "backup_strategy.png",
            "backup_strategy.drawio"
        ]
        
        existing_diagrams = []
        for diagram in diagrams_to_check:
            diagram_path = f"{self.output_dir}/{diagram}"
            if os.path.exists(diagram_path):
                existing_diagrams.append(diagram_path)
                logger.info(f"✅ DR diagram generated: {diagram_path}")
        
        if len(existing_diagrams) >= 6:  # Both PNG and draw.io for each
            return True
        else:
            logger.error("❌ Some DR diagrams failed to generate")
            return False
    
    def generate_dr_report(self):
        """Generate disaster recovery configuration report"""
        report_path = f"{self.output_dir}/dr_config_report.json"
        
        dr_report = {
            "disaster_recovery_strategy": {
                "rto_minutes": self.dr_config['rto_minutes'],
                "rpo_minutes": self.dr_config['rpo_minutes'],
                "backup_retention_days": self.dr_config['backup_retention_days'],
                "cross_region_backup": self.dr_config['cross_region_backup'],
                "multi_az": self.dr_config['multi_az'],
                "auto_failover": self.dr_config['auto_failover']
            },
            "components": {
                "primary_region": "us-east-1",
                "secondary_region": "us-west-2",
                "database_backup": "Automated RDS snapshots with cross-region replication",
                "storage_backup": "S3 cross-region replication with lifecycle policies",
                "monitoring": "CloudWatch alarms and Route 53 health checks",
                "notification": "SNS topics for incident alerts",
                "encryption": "KMS key replication for DR region"
            },
            "recovery_procedures": {
                "database_recovery": "Restore from latest snapshot in DR region",
                "application_deployment": "ECS task definition deployment in DR region",
                "dns_failover": "Route 53 health check and failover",
                "storage_sync": "S3 replication and EFS backup restore"
            }
        }
        
        with open(report_path, 'w') as f:
            json.dump(dr_report, f, indent=2)
        
        logger.info(f"✅ DR configuration report generated: {report_path}")
        return report_path

def main():
    """Main execution for Phase 7"""
    parser = argparse.ArgumentParser(description='Generate Disaster Recovery Architecture Diagram')
    parser.add_argument('--stack', default='hipaa-dev', help='Pulumi stack name')
    parser.add_argument('--output', default='./output', help='Output directory')
    
    args = parser.parse_args()
    
    generator = DisasterRecoveryDiagramGenerator(args.stack, args.output)
    
    # Phase 7 execution
    print("🚀 Phase 7: Disaster Recovery Architecture")
    print("=" * 50)
    
    # Create diagrams
    generator.create_disaster_recovery_diagram()
    generator.create_dr_flow_diagram()
    generator.create_backup_strategy_diagram()
    generator.create_dr_flow_drawio()
    generator.create_backup_strategy_drawio()
    
    # Generate report
    dr_report = generator.generate_dr_report()
    
    if generator.validate_diagram():
        print("✅ Phase 7 Complete: Disaster recovery architecture diagrams generated")
        print(f"📊 Output: {args.output}/")
        print(f"📋 DR Report: {dr_report}")
        print("\n🔍 Manual validation checklist:")
        print("   [ ] RTO/RPO objectives clearly marked")
        print("   [ ] Cross-region replication shown")
        print("   [ ] Multi-AZ deployment visualized")
        print("   [ ] Backup strategy and retention periods")
        print("   [ ] Failover process flow documented")
        print("   [ ] Encryption key replication shown")
        print("   [ ] Monitoring and alerting integration")
        print("   [ ] HIPAA compliance indicators present")
        return 0
    else:
        print("❌ Phase 7 Failed: DR diagram validation failed")
        return 1

if __name__ == "__main__":
    exit(main())