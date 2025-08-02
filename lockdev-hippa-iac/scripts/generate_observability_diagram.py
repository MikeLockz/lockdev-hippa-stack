#!/usr/bin/env python3
"""
Phase 6: Observability Architecture Diagram Generator
Generates comprehensive observability and monitoring visualization for HIPAA-compliant AWS stack
"""

import subprocess
import json
import os
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.management import Cloudwatch, Cloudtrail, Config
from diagrams.aws.security import Guardduty, SecurityHub, IAM
from diagrams.aws.analytics import Athena, Kinesis
from diagrams.aws.storage import S3
from diagrams.aws.database import RDS
from diagrams.aws.compute import ECS, Lambda
from diagrams.aws.network import VPC, CloudFront
from diagrams.aws.integration import SNS, SQS
from diagrams.aws.devtools import XRay
from diagrams.onprem.client import Users
from diagrams.onprem.monitoring import Grafana, Prometheus
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ObservabilityDiagramGenerator:
    def __init__(self, stack_name="hipaa-dev", output_dir="./output"):
        self.stack_name = stack_name
        self.output_dir = output_dir
        self.dot_file = "Pulumi.dot"
        self.resources = {}
        
    def gather_observability_resources(self):
        """Gather observability-related resources from Pulumi stack"""
        try:
            logger.info("Gathering observability resources...")
            
            # Mock observability resources based on actual HIPAA infrastructure
            return {
                'cloudwatch': {
                    'log_groups': [
                        '/aws/ecs/hipaa-app',
                        '/aws/rds/instance/hipaa-db/error',
                        '/aws/lambda/hipaa-*',
                        '/aws/apigateway/hipaa-api'
                    ],
                    'metrics': [
                        'ECS/ServiceName',
                        'RDS/DatabaseConnections',
                        'Application/PHIAccess'
                    ],
                    'alarms': [
                        'HighErrorRate',
                        'DatabaseConnectionThreshold',
                        'UnauthorizedAccess'
                    ]
                },
                'cloudtrail': {
                    'trails': ['hipaa-cloudtrail'],
                    's3_bucket': 'hipaa-cloudtrail-logs',
                    'regions': ['us-east-1']
                },
                'guardduty': {
                    'detectors': ['hipaa-guardduty-detector'],
                    'findings_bucket': 'hipaa-guardduty-findings'
                },
                'xray': {
                    'services': ['hipaa-app-service', 'hipaa-db-service'],
                    'traces': True
                },
                'config': {
                    'rules': [
                        's3-bucket-public-read-prohibited',
                        'rds-storage-encrypted',
                        'cloudtrail-enabled'
                    ]
                },
                'vpc_flow_logs': {
                    'log_group': 'hipaa-vpc-flow-logs',
                    's3_bucket': 'hipaa-vpc-flow-logs-bucket'
                }
            }
        except Exception as e:
            logger.error(f"Failed to gather observability resources: {e}")
            return {}
    
    def create_observability_diagram(self, observability_data):
        """Create comprehensive observability architecture diagram"""
        filename = f"{self.output_dir}/observability_architecture"
        
        with Diagram(
            "HIPAA Observability & Monitoring Architecture",
            filename=filename,
            show=False,
            direction="TB",
            graph_attr={
                "bgcolor": "white",
                "pad": "0.5",
                "ranksep": "1.5",
                "nodesep": "1.0"
            }
        ):
            # External Users/Systems
            users = Users("Users/Admins")
            
            # Main Observability Cluster
            with Cluster("HIPAA Observability & Monitoring"):
                
                # Central Monitoring Hub
                with Cluster("Central Monitoring"):
                    cloudwatch = Cloudwatch("CloudWatch\nLogs & Metrics")
                    sns = SNS("SNS Alerts")
                    sqs = SQS("Alert Queue")
                    
                # Security Monitoring
                with Cluster("Security Monitoring"):
                    guardduty = Guardduty("GuardDuty\nThreat Detection")
                    security_hub = SecurityHub("Security Hub\nCompliance")
                    
                # Audit & Compliance
                with Cluster("Audit & Compliance"):
                    cloudtrail = Cloudtrail("CloudTrail\nAPI Audit Logs")
                    config_service = Config("Config Rules\nCompliance")
                    
                # Distributed Tracing
                with Cluster("Application Monitoring"):
                    xray = XRay("X-Ray\nDistributed Tracing")
                    
                # Analytics & SIEM
                with Cluster("Analytics & SIEM"):
                    athena = Athena("Athena\nLog Analytics")
                    kinesis = Kinesis("Kinesis\nReal-time Processing")
                    
            # Infrastructure Components
            with Cluster("HIPAA Infrastructure"):
                
                # Application Layer
                with Cluster("Application Tier"):
                    ecs_cluster = ECS("ECS Services")
                    lambda_functions = Lambda("Lambda Functions")
                    
                # Database Layer
                with Cluster("Database Tier"):
                    rds_primary = RDS("RDS Primary")
                    rds_replica = RDS("RDS Read Replica")
                    
                # Storage Layer
                with Cluster("Storage"):
                    s3_logs = S3("Log Storage")
                    s3_backups = S3("Backup Storage")
                    
                # Network Layer
                with Cluster("Network"):
                    vpc = VPC("VPC Flow Logs")
                    cloudfront = CloudFront("CDN Logs")
            
            # Alerting & Notification Flows
            with Cluster("Alerting & Notifications"):
                ops_team = Users("Operations Team")
                security_team = Users("Security Team")
                compliance_team = Users("Compliance Team")
            
            # Data Flow Connections
            # Application monitoring
            ecs_cluster >> Edge(label="logs/metrics") >> cloudwatch
            lambda_functions >> Edge(label="logs/metrics") >> cloudwatch
            rds_primary >> Edge(label="logs/metrics") >> cloudwatch
            rds_replica >> Edge(label="logs/metrics") >> cloudwatch
            
            # Security monitoring
            ecs_cluster >> Edge(label="events") >> guardduty
            rds_primary >> Edge(label="events") >> guardduty
            s3_logs >> Edge(label="events") >> guardduty
            
            # Audit logging
            ecs_cluster >> Edge(label="API calls") >> cloudtrail
            rds_primary >> Edge(label="API calls") >> cloudtrail
            lambda_functions >> Edge(label="API calls") >> cloudtrail
            
            # Distributed tracing
            ecs_cluster >> Edge(label="traces") >> xray
            lambda_functions >> Edge(label="traces") >> xray
            rds_primary >> Edge(label="traces") >> xray
            
            # Log storage
            cloudwatch >> Edge(label="archive") >> s3_logs
            cloudtrail >> Edge(label="store") >> s3_logs
            guardduty >> Edge(label="findings") >> s3_logs
            
            # Analytics processing
            s3_logs >> Edge(label="analyze") >> athena
            cloudwatch >> Edge(label="stream") >> kinesis
            
            # Alerting flows
            cloudwatch >> Edge(label="alerts") >> sns
            guardduty >> Edge(label="alerts") >> sns
            security_hub >> Edge(label="alerts") >> sns
            
            sns >> Edge(label="notify") >> ops_team
            sns >> Edge(label="notify") >> security_team
            sns >> Edge(label="notify") >> compliance_team
            
            # Compliance monitoring
            config_service >> Edge(label="evaluate") >> security_hub
            security_hub >> Edge(label="compliance") >> compliance_team
            
            # VPC monitoring
            vpc >> Edge(label="flow logs") >> cloudwatch
            cloudfront >> Edge(label="access logs") >> s3_logs
    
    def create_detailed_monitoring_view(self, observability_data):
        """Create detailed monitoring component view"""
        filename = f"{self.output_dir}/monitoring_detailed"
        
        with Diagram(
            "HIPAA Detailed Monitoring Architecture",
            filename=filename,
            show=False,
            direction="LR",
            graph_attr={
                "bgcolor": "white",
                "pad": "0.5",
                "ranksep": "1.2",
                "nodesep": "0.8"
            }
        ):
            
            # Data Sources
            with Cluster("Data Sources"):
                ecs_sources = ECS("ECS Tasks")
                rds_sources = RDS("RDS Instances")
                lambda_sources = Lambda("Lambda Functions")
                vpc_sources = VPC("VPC Flow Logs")
                alb_sources = CloudFront("ALB Logs")
            
            # Collection Layer
            with Cluster("Collection Layer"):
                cw_logs = Cloudwatch("CloudWatch Logs")
                cw_metrics = Cloudwatch("CloudWatch Metrics")
                cw_events = Cloudwatch("CloudWatch Events")
            
            # Processing Layer
            with Cluster("Processing Layer"):
                kinesis_data = Kinesis("Kinesis Data Streams")
                lambda_proc = Lambda("Log Processors")
                athena_proc = Athena("Query Engine")
            
            # Storage Layer
            with Cluster("Storage Layer"):
                s3_raw = S3("Raw Logs")
                s3_processed = S3("Processed Data")
                s3_archives = S3("Long-term Archive")
            
            # Analysis Layer
            with Cluster("Analysis Layer"):
                guardduty_an = Guardduty("Threat Analysis")
                security_hub_an = SecurityHub("Compliance Analysis")
                xray_an = XRay("Performance Analysis")
            
            # Alerting Layer
            with Cluster("Alerting Layer"):
                sns_alerts = SNS("SNS Alerts")
                cw_alarms = Cloudwatch("CloudWatch Alarms")
                ops_team = Users("Operations")
                security_team = Users("Security")
            
            # Data Flow
            ecs_sources >> cw_logs >> s3_raw
            rds_sources >> cw_logs >> s3_raw
            lambda_sources >> cw_logs >> s3_raw
            vpc_sources >> cw_logs >> s3_raw
            alb_sources >> cw_logs >> s3_raw
            
            s3_raw >> kinesis_data >> lambda_proc >> s3_processed
            s3_processed >> athena_proc >> s3_archives
            
            cw_metrics >> cw_alarms >> sns_alerts >> ops_team
            cw_logs >> guardduty_an >> security_team
            cw_events >> security_hub_an >> security_team
            
            ecs_sources >> xray_an
            lambda_sources >> xray_an
    
    def validate_diagram(self):
        """Validate generated observability diagrams"""
        diagram_path = f"{self.output_dir}/observability_architecture.png"
        detailed_path = f"{self.output_dir}/monitoring_detailed.png"
        
        success = True
        
        if os.path.exists(diagram_path):
            logger.info(f"✅ Main observability diagram generated: {diagram_path}")
        else:
            logger.error("❌ Main observability diagram generation failed")
            success = False
            
        if os.path.exists(detailed_path):
            logger.info(f"✅ Detailed monitoring diagram generated: {detailed_path}")
        else:
            logger.error("❌ Detailed monitoring diagram generation failed")
            success = False
            
        return success

def main():
    """Main execution for Phase 6"""
    parser = argparse.ArgumentParser(description='Generate Observability Architecture Diagram')
    parser.add_argument('--stack', default='hipaa-dev', help='Pulumi stack name')
    parser.add_argument('--output', default='./output', help='Output directory')
    
    args = parser.parse_args()
    
    generator = ObservabilityDiagramGenerator(args.stack, args.output)
    
    # Phase 6 execution
    print("🚀 Phase 6: Observability Architecture Diagram")
    print("=" * 50)
    
    observability_data = generator.gather_observability_resources()
    if not observability_data:
        print("❌ Failed to gather observability resources. Exiting.")
        return 1
    
    generator.create_observability_diagram(observability_data)
    generator.create_detailed_monitoring_view(observability_data)
    
    if generator.validate_diagram():
        print("✅ Phase 6 Complete: Observability architecture diagrams generated")
        print(f"📊 Outputs:")
        print(f"   - {args.output}/observability_architecture.png")
        print(f"   - {args.output}/monitoring_detailed.png")
        print("\n🔍 Manual validation checklist:")
        print("   [ ] CloudWatch log groups for all components")
        print("   [ ] CloudTrail API audit logging")
        print("   [ ] GuardDuty threat detection")
        print("   [ ] X-Ray distributed tracing")
        print("   [ ] VPC Flow Logs configuration")
        print("   [ ] CloudWatch alarms and SNS notifications")
        print("   [ ] Config rules for compliance")
        print("   [ ] Log retention and archival policies")
        print("   [ ] Real-time alerting workflows")
        print("   [ ] HIPAA audit trail requirements")
        return 0
    else:
        print("❌ Phase 6 Failed: Diagram validation failed")
        return 1

if __name__ == "__main__":
    exit(main())