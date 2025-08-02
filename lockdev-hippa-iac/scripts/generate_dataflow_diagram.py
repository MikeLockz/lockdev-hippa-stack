#!/usr/bin/env python3
"""
Phase 3: Data Flow Architecture Diagram Generator
Generates data flow visualization for HIPAA-compliant AWS stack
Focuses on RDS, S3, encryption, backup strategies, and data movement
"""

import subprocess
import json
import os
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.database import RDS, Dynamodb, ElasticacheForRedis
from diagrams.aws.storage import S3, EFS, Backup
from diagrams.aws.security import KMS, SecretsManager, CertificateManager
from diagrams.aws.compute import ECS, Lambda
from diagrams.aws.network import CloudFront, APIGateway
from diagrams.aws.analytics import Kinesis, Glue
from diagrams.aws.management import Cloudwatch
from diagrams.onprem.client import Users
from diagrams.onprem.database import Postgresql
from diagrams.onprem.monitoring import Prometheus, Grafana
import argparse
import logging
from drawio_utils import DrawIOGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataFlowDiagramGenerator:
    def __init__(self, stack_name="hipaa-dev", output_dir="./output"):
        self.stack_name = stack_name
        self.output_dir = output_dir
        
    def create_dataflow_diagram(self):
        """Create comprehensive data flow architecture diagram"""
        filename = f"{self.output_dir}/dataflow_architecture"
        
        with Diagram(
            "HIPAA Data Flow Architecture",
            filename=filename,
            show=False,
            direction="LR",
            graph_attr={
                "bgcolor": "white",
                "pad": "0.5",
                "ranksep": "1.5",
                "nodesep": "1.2",
                "fontsize": "11"
            }
        ):
            # External Users
            users = Users("External Users")
            
            # API Layer
            with Cluster("API & Edge Layer"):
                cloudfront = CloudFront("CloudFront CDN")
                api_gateway = APIGateway("API Gateway")
                
            # Application Layer
            with Cluster("Application Processing"):
                ecs_cluster = ECS("ECS Fargate\nFastAPI Application")
                lambda_functions = Lambda("Lambda Functions")
                
            # Encryption & Security Layer
            with Cluster("Encryption & Key Management"):
                kms = KMS("AWS KMS\nEncryption Keys")
                secrets = SecretsManager("Secrets Manager")
                certificates = CertificateManager("SSL Certificates")
                
            # Primary Database Layer
            with Cluster("Primary Data Storage"):
                with Cluster("RDS PostgreSQL"):
                    rds_primary = RDS("RDS Primary\nMulti-AZ")
                    rds_replica = RDS("RDS Read Replica")
                    
                with Cluster("Cache Layer"):
                    redis = ElasticacheForRedis("ElastiCache\nRedis")
                    
            # Object Storage
            with Cluster("Object Storage"):
                s3_data = S3("S3 Data Lake\n(Encrypted)")
                s3_backups = S3("S3 Backup Storage\n(Encrypted)")
                s3_logs = S3("S3 Log Storage\n(Encrypted)")
                
            # Backup & Recovery
            with Cluster("Backup & Recovery"):
                aws_backup = Backup("AWS Backup\nAutomated")
                
            # Monitoring & Analytics
            with Cluster("Monitoring & Analytics"):
                cloudwatch = Cloudwatch("CloudWatch\nMonitoring")
                kinesis = Kinesis("Kinesis\nData Stream")
                glue = Glue("Glue\nETL Jobs")
                
            # Data Flow Connections
            # User flow
            users >> Edge(label="HTTPS/TLS 1.3") >> cloudfront
            cloudfront >> Edge(label="HTTPS") >> api_gateway
            api_gateway >> Edge(label="JWT Auth") >> ecs_cluster
            
            # Application to database
            ecs_cluster >> Edge(label="SSL/TLS", style="dashed") >> rds_primary
            ecs_cluster >> Edge(label="Cache") >> redis
            
            # Read replica flow
            rds_primary >> Edge(label="Replication", style="dotted") >> rds_replica
            
            # Encryption integration
            kms >> Edge(label="Encrypt/Decrypt", color="red", style="bold") >> rds_primary
            kms >> Edge(label="Encrypt/Decrypt", color="red", style="bold") >> s3_data
            kms >> Edge(label="Encrypt/Decrypt", color="red", style="bold") >> s3_backups
            
            # Secrets management
            secrets >> Edge(label="Credentials", color="green", style="dashed") >> ecs_cluster
            
            # Object storage flows
            ecs_cluster >> Edge(label="File Upload", style="dashed") >> s3_data
            ecs_cluster >> Edge(label="Log Storage", style="dotted") >> s3_logs
            
            # Backup flows
            rds_primary >> Edge(label="Snapshot", style="bold") >> aws_backup
            aws_backup >> Edge(label="Archive", style="bold") >> s3_backups
            
            # Monitoring flows
            rds_primary >> Edge(label="Metrics", style="dotted") >> cloudwatch
            ecs_cluster >> Edge(label="Metrics", style="dotted") >> cloudwatch
            cloudwatch >> Edge(label="Alerts") >> kinesis
            kinesis >> Edge(label="Process") >> glue
            
            # Lambda processing
            s3_data >> Edge(label="Event Trigger", style="dotted") >> lambda_functions
            lambda_functions >> Edge(label="Process", style="dashed") >> s3_backups

    def create_dataflow_drawio_diagram(self):
        """Create data flow architecture DrawIO diagram with AWS best practices styling"""
        drawio_gen = DrawIOGenerator(self.output_dir)
        
        mxfile = drawio_gen.create_mxfile("HIPAA Data Flow Architecture", "dataflow_arch")
        diagram = drawio_gen.create_diagram(mxfile, "HIPAA Data Flow Architecture", "dataflow_arch")
        mxgraphmodel = drawio_gen.create_graph_model(diagram)
        root = drawio_gen.create_root(mxgraphmodel)
        
        # External Users
        drawio_gen.add_rectangle(root, "users", "👥 External Users\nHIPAA Authorized\n🔐 Authenticated", 
                                50, 50, 140, 60, fill_color="#181717", stroke_color="#181717")
        
        # API & Edge Layer
        edge_container = drawio_gen.add_swimlane(root, "edge", "🌐 API & Edge Layer", 250, 50, 700, 120)
        drawio_gen.add_rectangle(root, "cloudfront", "🌐 CloudFront CDN\nGlobal Distribution\n🔐 TLS 1.3", 
                                50, 30, 160, 60, fill_color="#FF9900", stroke_color="#FF9900", parent="edge")
        drawio_gen.add_rectangle(root, "api_gateway", "⚖️ API Gateway\nRate Limiting\n🛡️ WAF Protection", 
                                230, 30, 160, 60, fill_color="#FF9900", stroke_color="#FF9900", parent="edge")
        drawio_gen.add_rectangle(root, "certificates", "🔐 Certificate Manager\nSSL/TLS Certificates\n🔒 Encryption in Transit", 
                                410, 30, 160, 60, fill_color="#D93232", stroke_color="#D93232", parent="edge")
        
        # Application Layer
        app_container = drawio_gen.add_swimlane(root, "app", "🚀 Application Processing Layer", 250, 200, 700, 150)
        drawio_gen.add_rectangle(root, "ecs", "🐳 ECS Fargate Cluster\nHIPAA-Compliant Containers\n🔄 Auto Scaling", 
                                50, 30, 200, 70, fill_color="#FF9900", stroke_color="#FF9900", parent="app")
        drawio_gen.add_rectangle(root, "lambda", "⚡ Lambda Functions\nEvent Processing\n📝 Serverless", 
                                270, 30, 180, 70, fill_color="#FF9900", stroke_color="#FF9900", parent="app")
        drawio_gen.add_rectangle(root, "secrets", "🔑 Secrets Manager\nDB Credentials\n🔐 Encrypted Storage", 
                                470, 30, 160, 70, fill_color="#D93232", stroke_color="#D93232", parent="app")
        
        # Encryption & Key Management
        encryption_container = drawio_gen.add_swimlane(root, "encryption", "🔐 Encryption & Key Management", 250, 380, 700, 120)
        drawio_gen.add_rectangle(root, "kms", "🔐 AWS KMS\nCustomer Master Keys\n🔄 90-day Rotation", 
                                50, 30, 160, 60, fill_color="#D93232", stroke_color="#D93232", parent="encryption")
        drawio_gen.add_rectangle(root, "envelope", "📊 Envelope Encryption\nData Keys\n🔒 Hierarchical", 
                                230, 30, 160, 60, fill_color="#2E73B8", stroke_color="#2E73B8", parent="encryption")
        drawio_gen.add_rectangle(root, "audit", "📋 Audit Logging\nKey Usage\n🔍 Compliance Tracking", 
                                410, 30, 160, 60, fill_color="#2E73B8", stroke_color="#2E73B8", parent="encryption")
        
        # Primary Database Layer
        db_container = drawio_gen.add_swimlane(root, "database", "🗄️ Primary Data Storage", 50, 530, 900, 150)
        
        # RDS PostgreSQL
        rds_container = drawio_gen.add_swimlane(root, "rds", "🗄️ RDS PostgreSQL 14", 50, 50, 400, 120)
        drawio_gen.add_cylinder(root, "rds_primary", "🗄️ RDS Primary\nMulti-AZ Deployment\n💾 Encrypted at Rest", 
                               50, 30, 180, 70, fill_color="#2E73B8", stroke_color="#2E73B8", parent="rds")
        drawio_gen.add_cylinder(root, "rds_replica", "📖 RDS Read Replica\nRead Scaling\n🔄 Cross-AZ", 
                               250, 30, 160, 70, fill_color="#2E73B8", stroke_color="#2E73B8", parent="rds")
        
        # Cache Layer
        cache_container = drawio_gen.add_swimlane(root, "cache", "⚡ Cache Layer", 470, 50, 200, 120)
        drawio_gen.add_rectangle(root, "redis", "⚡ ElastiCache Redis\nSession Storage\n🚀 Performance Boost", 
                                50, 30, 140, 70, fill_color="#FF9900", stroke_color="#FF9900", parent="cache")
        
        # Object Storage Layer
        storage_container = drawio_gen.add_swimlane(root, "storage", "📦 Object Storage Layer", 50, 720, 900, 150)
        drawio_gen.add_cylinder(root, "s3_data", "📊 S3 Data Lake\nUnstructured Data\n🔐 SSE-KMS Encryption", 
                               50, 30, 160, 70, fill_color="#FF9900", stroke_color="#FF9900", parent="storage")
        drawio_gen.add_cylinder(root, "s3_backups", "💾 S3 Backup Storage\nCross-Region Replication\n🔄 Lifecycle Policies", 
                               230, 30, 180, 70, fill_color="#FF9900", stroke_color="#FF9900", parent="storage")
        drawio_gen.add_cylinder(root, "s3_logs", "📋 S3 Log Storage\nAccess Logs\n📊 Audit Trail", 
                               430, 30, 140, 70, fill_color="#FF9900", stroke_color="#FF9900", parent="storage")
        drawio_gen.add_cylinder(root, "s3_archive", "🗄️ S3 Glacier Archive\nLong-term Retention\n💰 Cost Optimization", 
                               600, 30, 160, 70, fill_color="#FF9900", stroke_color="#FF9900", parent="storage")
        
        # Backup & Recovery
        backup_container = drawio_gen.add_swimlane(root, "backup", "💾 Backup & Recovery", 50, 910, 900, 120)
        drawio_gen.add_rectangle(root, "aws_backup", "🔄 AWS Backup\nAutomated Snapshots\n📅 Scheduled", 
                                50, 30, 160, 60, fill_color="#28A745", stroke_color="#28A745", parent="backup")
        drawio_gen.add_cylinder(root, "snapshot", "📸 DB Snapshots\nPoint-in-time Recovery\n⏰ 7-day Retention", 
                               230, 30, 160, 60, fill_color="#2E73B8", stroke_color="#2E73B8", parent="backup")
        drawio_gen.add_rectangle(root, "cross_region", "🌍 Cross-Region Backup\nDR Strategy\n🔄 Automated", 
                                420, 30, 180, 60, fill_color="#28A745", stroke_color="#28A745", parent="backup")
        
        # Monitoring & Analytics
        analytics_container = drawio_gen.add_swimlane(root, "analytics", "📊 Monitoring & Analytics", 50, 1070, 900, 120)
        drawio_gen.add_rectangle(root, "cloudwatch", "📊 CloudWatch\nMetrics & Alarms\n🚨 Real-time Monitoring", 
                                50, 30, 160, 60, fill_color="#FF9900", stroke_color="#FF9900", parent="analytics")
        drawio_gen.add_rectangle(root, "kinesis", "📈 Kinesis Data Stream\nReal-time Processing\n🔄 Stream Analytics", 
                                230, 30, 160, 60, fill_color="#FF9900", stroke_color="#FF9900", parent="analytics")
        drawio_gen.add_rectangle(root, "glue", "🔧 AWS Glue\nETL Jobs\n📊 Data Transformation", 
                                410, 30, 140, 60, fill_color="#FF9900", stroke_color="#FF9900", parent="analytics")
        drawio_gen.add_rectangle(root, "athena", "🔍 Athena Queries\nSQL Analytics\n📊 Business Intelligence", 
                                580, 30, 160, 60, fill_color="#FF9900", stroke_color="#FF9900", parent="analytics")
        
        # Connections
        drawio_gen.add_edge(root, "e1", "users", "cloudfront")
        drawio_gen.add_edge(root, "e2", "cloudfront", "api_gateway")
        drawio_gen.add_edge(root, "e3", "api_gateway", "ecs")
        drawio_gen.add_edge(root, "e4", "ecs", "secrets")
        drawio_gen.add_edge(root, "e5", "ecs", "redis")
        drawio_gen.add_edge(root, "e6", "ecs", "rds_primary")
        drawio_gen.add_edge(root, "e7", "rds_primary", "rds_replica")
        drawio_gen.add_edge(root, "e8", "rds_primary", "aws_backup")
        drawio_gen.add_edge(root, "e9", "aws_backup", "snapshot")
        drawio_gen.add_edge(root, "e10", "snapshot", "cross_region")
        drawio_gen.add_edge(root, "e11", "ecs", "s3_data")
        drawio_gen.add_edge(root, "e12", "s3_data", "s3_backups")
        drawio_gen.add_edge(root, "e13", "s3_data", "s3_logs")
        drawio_gen.add_edge(root, "e14", "s3_data", "s3_archive")
        drawio_gen.add_edge(root, "e15", "ecs", "cloudwatch")
        drawio_gen.add_edge(root, "e16", "rds_primary", "cloudwatch")
        drawio_gen.add_edge(root, "e17", "cloudwatch", "kinesis")
        drawio_gen.add_edge(root, "e18", "kinesis", "glue")
        drawio_gen.add_edge(root, "e19", "glue", "athena")
        drawio_gen.add_edge(root, "e20", "s3_data", "lambda")
        drawio_gen.add_edge(root, "e21", "lambda", "s3_backups")
        drawio_gen.add_edge(root, "e22", "kms", "rds_primary")
        drawio_gen.add_edge(root, "e23", "kms", "s3_data")
        drawio_gen.add_edge(root, "e24", "kms", "s3_backups")
        
        return drawio_gen.save_drawio_file(mxfile, "dataflow_architecture.drawio")
    
    def create_encryption_flow_diagram(self):
        """Create detailed encryption flow diagram"""
        filename = f"{self.output_dir}/encryption_flow"
        
        with Diagram(
            "HIPAA Encryption Flow",
            filename=filename,
            show=False,
            direction="TB",
            graph_attr={
                "bgcolor": "white",
                "pad": "0.5",
                "ranksep": "1.2",
                "nodesep": "1.0"
            }
        ):
            # Data sources
            users = Users("Users")
            app = ECS("Application")
            
            # Encryption layers
            with Cluster("Transport Layer Encryption"):
                tls_edge = CertificateManager("TLS 1.3\nEdge Certificates")
                tls_internal = CertificateManager("TLS 1.3\nInternal Certificates")
                
            with Cluster("Application Layer Encryption"):
                jwt_tokens = SecretsManager("JWT Tokens")
                api_keys = SecretsManager("API Keys")
                
            with Cluster("Data Layer Encryption"):
                kms_master = KMS("KMS Master Key")
                kms_data = KMS("KMS Data Key")
                
            # Database encryption
            with Cluster("Database Encryption"):
                rds_encrypted = RDS("RDS\nAES-256")
                backup_encrypted = Backup("Encrypted\nBackups")
                
            # Storage encryption
            with Cluster("Storage Encryption"):
                s3_encrypted = S3("S3\nSSE-S3")
                s3_kms = S3("S3\nSSE-KMS")
                
            # Key rotation
            with Cluster("Key Management"):
                key_rotation = KMS("Key Rotation\n(90 days)")
                
            # Encryption flow
            users >> Edge(label="HTTPS/TLS 1.3") >> tls_edge >> app
            app >> Edge(label="JWT Signing") >> jwt_tokens
            app >> Edge(label="Database Connection") >> tls_internal >> rds_encrypted
            
            # Key hierarchy
            kms_master >> Edge(label="Encrypts", color="red") >> kms_data
            kms_data >> Edge(label="Encrypts Data", color="red") >> rds_encrypted
            kms_data >> Edge(label="Encrypts Files", color="red") >> s3_encrypted
            kms_data >> Edge(label="Encrypts Files", color="red") >> s3_kms
            
            # Backup encryption
            rds_encrypted >> Edge(label="Encrypted Backup", style="bold") >> backup_encrypted
            
            # Key rotation
            key_rotation >> Edge(label="Rotates Keys", style="dashed", color="blue") >> kms_master
    
    def create_encryption_flow_drawio(self):
        """Create draw.io XML for encryption flow diagram"""
        drawio_gen = DrawIOGenerator(self.output_dir)
        
        mxfile = drawio_gen.create_mxfile("HIPAA Encryption Flow", "encryption_flow")
        diagram = drawio_gen.create_diagram(mxfile, "HIPAA Encryption Flow", "encryption_flow")
        mxgraphmodel = drawio_gen.create_graph_model(diagram)
        root = drawio_gen.create_root(mxgraphmodel)
        
        # Data sources
        users = drawio_gen.add_rectangle(root, "users", "Users", 50, 50, 100, 60)
        app = drawio_gen.add_rectangle(root, "app", "Application", 200, 50, 120, 60)
        
        # Encryption layers
        transport_container = drawio_gen.add_swimlane(root, "transport", "Transport Layer Encryption", 50, 150, 300, 100)
        drawio_gen.add_rectangle(root, "tls_edge", "TLS 1.3\nEdge Certificates", 50, 30, 120, 50, parent="transport")
        drawio_gen.add_rectangle(root, "tls_internal", "TLS 1.3\nInternal Certificates", 180, 30, 120, 50, parent="transport")
        
        app_layer_container = drawio_gen.add_swimlane(root, "app_layer", "Application Layer Encryption", 400, 150, 300, 100)
        drawio_gen.add_rectangle(root, "jwt", "JWT Tokens", 50, 30, 120, 50, parent="app_layer")
        drawio_gen.add_rectangle(root, "api_keys", "API Keys", 180, 30, 120, 50, parent="app_layer")
        
        data_layer_container = drawio_gen.add_swimlane(root, "data_layer", "Data Layer Encryption", 50, 270, 300, 100)
        drawio_gen.add_rectangle(root, "kms_master", "KMS Master Key", 50, 30, 120, 50, parent="data_layer")
        drawio_gen.add_rectangle(root, "kms_data", "KMS Data Key", 180, 30, 120, 50, parent="data_layer")
        
        # Database encryption
        db_container = drawio_gen.add_swimlane(root, "db_enc", "Database Encryption", 400, 270, 300, 100)
        drawio_gen.add_cylinder(root, "rds_enc", "RDS\nAES-256", 50, 30, 120, 50, parent="db_enc")
        drawio_gen.add_cylinder(root, "backup_enc", "Encrypted\nBackups", 180, 30, 120, 50, parent="db_enc")
        
        # Storage encryption
        storage_container = drawio_gen.add_swimlane(root, "storage_enc", "Storage Encryption", 50, 390, 300, 100)
        drawio_gen.add_cylinder(root, "s3_enc", "S3\nSSE-S3", 50, 30, 120, 50, parent="storage_enc")
        drawio_gen.add_cylinder(root, "s3_kms", "S3\nSSE-KMS", 180, 30, 120, 50, parent="storage_enc")
        
        # Key rotation
        drawio_gen.add_rectangle(root, "key_rotation", "Key Rotation\n(90 days)", 400, 390, 120, 50)
        
        # Connections
        drawio_gen.add_edge(root, "e1", "users", "tls_edge")
        drawio_gen.add_edge(root, "e2", "tls_edge", "app")
        drawio_gen.add_edge(root, "e3", "app", "jwt")
        drawio_gen.add_edge(root, "e4", "app", "tls_internal")
        drawio_gen.add_edge(root, "e5", "tls_internal", "rds_enc")
        drawio_gen.add_edge(root, "e6", "kms_master", "kms_data", parent="data_layer")
        drawio_gen.add_edge(root, "e7", "kms_data", "rds_enc", parent="data_layer")
        drawio_gen.add_edge(root, "e8", "kms_data", "s3_enc", parent="storage_enc")
        drawio_gen.add_edge(root, "e9", "kms_data", "s3_kms", parent="storage_enc")
        drawio_gen.add_edge(root, "e10", "rds_enc", "backup_enc")
        drawio_gen.add_edge(root, "e11", "key_rotation", "kms_master")
        
        return drawio_gen.save_drawio_file(mxfile, "encryption_flow.drawio")

    def create_backup_flow_drawio(self):
        """Create draw.io XML for backup flow diagram"""
        drawio_gen = DrawIOGenerator(self.output_dir)
        
        mxfile = drawio_gen.create_mxfile("HIPAA Backup & Recovery Flow", "backup_flow")
        diagram = drawio_gen.create_diagram(mxfile, "HIPAA Backup & Recovery Flow", "backup_flow")
        mxgraphmodel = drawio_gen.create_graph_model(diagram)
        root = drawio_gen.create_root(mxgraphmodel)
        
        # Production systems
        prod_container = drawio_gen.add_swimlane(root, "prod", "Production Systems", 50, 50, 200, 150)
        drawio_gen.add_cylinder(root, "rds_prod", "RDS Production", 50, 50, 120, 50, parent="prod")
        drawio_gen.add_cylinder(root, "s3_prod", "S3 Production Data", 50, 100, 120, 50, parent="prod")
        
        # Backup services
        backup_container = drawio_gen.add_swimlane(root, "backup", "Backup Services", 300, 50, 200, 150)
        drawio_gen.add_rectangle(root, "backup_vault", "AWS Backup Vault", 50, 50, 120, 50, parent="backup")
        drawio_gen.add_rectangle(root, "backup_plan", "Backup Plans", 50, 100, 120, 50, parent="backup")
        
        # Storage tiers
        storage_container = drawio_gen.add_swimlane(root, "storage", "Backup Storage", 550, 50, 300, 150)
        drawio_gen.add_cylinder(root, "s3_warm", "S3 Standard-IA\n(30 days)", 50, 50, 120, 50, parent="storage")
        drawio_gen.add_cylinder(root, "s3_cold", "S3 Glacier\n(90 days)", 50, 100, 120, 50, parent="storage")
        drawio_gen.add_cylinder(root, "s3_deep", "S3 Glacier Deep\n(1+ years)", 180, 75, 120, 50, parent="storage")
        
        # Recovery systems
        recovery_container = drawio_gen.add_swimlane(root, "recovery", "Disaster Recovery", 900, 50, 200, 150)
        drawio_gen.add_cylinder(root, "rds_dr", "RDS DR Instance", 50, 50, 120, 50, parent="recovery")
        drawio_gen.add_cylinder(root, "s3_dr", "S3 DR Storage", 50, 100, 120, 50, parent="recovery")
        
        # Monitoring
        drawio_gen.add_rectangle(root, "cloudwatch", "Backup Monitoring", 400, 220, 120, 50)
        
        # Connections
        drawio_gen.add_edge(root, "e1", "rds_prod", "backup_plan")
        drawio_gen.add_edge(root, "e2", "s3_prod", "backup_plan")
        drawio_gen.add_edge(root, "e3", "backup_plan", "backup_vault")
        drawio_gen.add_edge(root, "e4", "backup_vault", "s3_warm")
        drawio_gen.add_edge(root, "e5", "s3_warm", "s3_cold")
        drawio_gen.add_edge(root, "e6", "s3_cold", "s3_deep")
        drawio_gen.add_edge(root, "e7", "backup_vault", "rds_dr")
        drawio_gen.add_edge(root, "e8", "backup_vault", "s3_dr")
        drawio_gen.add_edge(root, "e9", "backup_plan", "cloudwatch")
        
        return drawio_gen.save_drawio_file(mxfile, "backup_flow.drawio")

    def create_backup_flow_diagram(self):
        """Create backup and disaster recovery flow diagram"""
        filename = f"{self.output_dir}/backup_flow"
        
        with Diagram(
            "HIPAA Backup & Recovery Flow",
            filename=filename,
            show=False,
            direction="LR",
            graph_attr={
                "bgcolor": "white",
                "pad": "0.5",
                "ranksep": "1.5",
                "nodesep": "1.2"
            }
        ):
            # Primary systems
            with Cluster("Production Systems"):
                rds_prod = RDS("RDS Production")
                s3_prod = S3("S3 Production Data")
                
            # Backup services
            with Cluster("Backup Services"):
                backup_vault = Backup("AWS Backup Vault")
                backup_plan = Backup("Backup Plans")
                
            # Storage tiers
            with Cluster("Backup Storage"):
                s3_warm = S3("S3 Standard-IA\n(30 days)")
                s3_cold = S3("S3 Glacier\n(90 days)")
                s3_deep = S3("S3 Glacier Deep\n(1+ years)")
                
            # Recovery systems
            with Cluster("Disaster Recovery"):
                rds_dr = RDS("RDS DR Instance")
                s3_dr = S3("S3 DR Storage")
                
            # Monitoring
            with Cluster("Monitoring & Alerts"):
                cloudwatch = Cloudwatch("Backup Monitoring")
                
            # Backup flow
            rds_prod >> Edge(label="Daily Backup", style="bold") >> backup_plan
            s3_prod >> Edge(label="Cross-Region", style="bold") >> backup_plan
            
            backup_plan >> Edge(label="Store") >> backup_vault
            backup_vault >> Edge(label="Lifecycle Policy") >> s3_warm
            s3_warm >> Edge(label="Transition") >> s3_cold
            s3_cold >> Edge(label="Archive") >> s3_deep
            
            # Recovery flow
            backup_vault >> Edge(label="Restore", color="green", style="dashed") >> rds_dr
            backup_vault >> Edge(label="Restore", color="green", style="dashed") >> s3_dr
            
            # Monitoring
            backup_plan >> Edge(label="Status", style="dotted") >> cloudwatch
            
    def validate_diagrams(self):
        """Validate all generated diagrams"""
        diagrams = [
            f"{self.output_dir}/dataflow_architecture.png",
            f"{self.output_dir}/dataflow_architecture.drawio",
            f"{self.output_dir}/encryption_flow.png",
            f"{self.output_dir}/encryption_flow.drawio",
            f"{self.output_dir}/backup_flow.png",
            f"{self.output_dir}/backup_flow.drawio"
        ]
        
        success = True
        png_count = 0
        drawio_count = 0
        
        for diagram_path in diagrams:
            if os.path.exists(diagram_path):
                if diagram_path.endswith('.png'):
                    png_count += 1
                    logger.info(f"✅ PNG diagram generated: {diagram_path}")
                elif diagram_path.endswith('.drawio'):
                    drawio_count += 1
                    logger.info(f"✅ Draw.io diagram generated: {diagram_path}")
            else:
                logger.error(f"❌ Diagram missing: {diagram_path}")
                success = False
        
        logger.info(f"📊 Generated {png_count} PNG diagrams and {drawio_count} Draw.io diagrams")
        return success

def main():
    """Main execution for Phase 3"""
    parser = argparse.ArgumentParser(description='Generate Data Flow Architecture Diagrams')
    parser.add_argument('--stack', default='hipaa-dev', help='Pulumi stack name')
    parser.add_argument('--output', default='./output', help='Output directory')
    parser.add_argument('--skip-encryption', action='store_true', help='Skip encryption flow diagram')
    parser.add_argument('--skip-backup', action='store_true', help='Skip backup flow diagram')
    
    args = parser.parse_args()
    
    generator = DataFlowDiagramGenerator(args.stack, args.output)
    
    # Phase 3 execution
    print("🚀 Phase 3: Data Flow Architecture")
    print("=" * 50)
    
    # Create main data flow diagram
    print("📊 Creating main data flow architecture...")
    generator.create_dataflow_diagram()
    
    # Create encryption flow diagram
    if not args.skip_encryption:
        print("🔐 Creating encryption flow diagram...")
        generator.create_encryption_flow_diagram()
        generator.create_encryption_flow_drawio()
    
    # Create backup flow diagram
    if not args.skip_backup:
        print("💾 Creating backup and recovery flow diagram...")
        generator.create_backup_flow_diagram()
        generator.create_backup_flow_drawio()
    
    if generator.validate_diagrams():
        print("✅ Phase 3 Complete: All data flow diagrams generated")
        print(f"📁 Output directory: {args.output}")
        print("\n🔍 Manual validation checklist:")
        print("   [ ] Data encryption at rest and in transit shown")
        print("   [ ] Backup and recovery flows documented")
        print("   [ ] Key management and rotation depicted")
        print("   [ ] Cross-region replication shown")
        print("   [ ] Monitoring and alerting flows included")
        print("   [ ] HIPAA compliance indicators present")
        return 0
    else:
        print("❌ Phase 3 Failed: Some diagrams failed to generate")
        return 1

if __name__ == "__main__":
    exit(main())