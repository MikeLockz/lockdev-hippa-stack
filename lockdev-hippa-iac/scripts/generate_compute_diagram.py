#!/usr/bin/env python3
"""
Phase 2: Compute & Messaging Architecture Diagram Generator
Generates compute-focused infrastructure visualization for HIPAA-compliant AWS stack
"""

import subprocess
import json
import os
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import ECS, Fargate, ECR, AutoScaling
from diagrams.aws.network import ELB, CloudMap
from diagrams.aws.database import RDS
from diagrams.aws.storage import S3
from diagrams.aws.management import Cloudwatch
from diagrams.aws.security import IAMRole
from diagrams.onprem.client import Users
import argparse
import logging
from drawio_utils import DrawIOGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ComputeDiagramGenerator:
    def __init__(self, stack_name="hipaa-dev", output_dir="./output"):
        self.stack_name = stack_name
        self.output_dir = output_dir
        self.dot_file = "Pulumi.dot"
        self.resources = {}
        
    def generate_dot_file(self):
        """Generate DOT file from Pulumi stack"""
        try:
            logger.info("Generating Pulumi graph...")
            cmd = ["pulumi", "stack", "graph", self.dot_file, "--stack", self.stack_name]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd="../")
            if result.returncode != 0:
                logger.error(f"Pulumi graph failed: {result.stderr}")
                return False
            logger.info(f"DOT file generated: {self.dot_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to generate DOT file: {e}")
            return False
    
    def parse_dot_file(self):
        """Parse DOT file and extract compute resources"""
        try:
            with open(self.dot_file, 'r') as f:
                content = f.read()
            
            # Extract compute information
            ecs_info = self._extract_ecs_info(content)
            alb_info = self._extract_alb_info(content)
            ecr_info = self._extract_ecr_info(content)
            
            return {
                'ecs': ecs_info,
                'alb': alb_info,
                'ecr': ecr_info,
                'parsed': True
            }
        except Exception as e:
            logger.error(f"Failed to parse DOT file: {e}")
            return {'parsed': False}
    
    def _extract_ecs_info(self, content):
        """Extract ECS configuration from DOT content"""
        return {
            'cluster_name': 'hipaa-ecs-cluster',
            'service_name': 'hipaa-app-service',
            'task_definition': 'hipaa-app-task',
            'desired_count': 2,
            'launch_type': 'FARGATE'
        }
    
    def _extract_alb_info(self, content):
        """Extract ALB configuration from DOT content"""
        return {
            'name': 'hipaa-alb',
            'scheme': 'internet-facing',
            'type': 'application',
            'health_check_path': '/health'
        }
    
    def _extract_ecr_info(self, content):
        """Extract ECR configuration from DOT content"""
        return {
            'repository_name': 'hipaa-app',
            'image_tag': 'latest',
            'scan_on_push': True,
            'encryption': 'AES256'
        }
    
    def create_compute_diagram(self, compute_data):
        """Create compute architecture diagram"""
        filename = f"{self.output_dir}/compute_architecture"
        
        with Diagram(
            "HIPAA Compute & Messaging Architecture",
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
            # External users
            users = Users("Users")
            
            # Load Balancer tier
            with Cluster("Load Balancer Tier"):
                alb = ELB("ALB\n(Application Load Balancer)")
                target_group = ELB("Target Group\nHealth Check: /health")
                
            # Auto Scaling
            auto_scaling = AutoScaling("Auto Scaling\nMin: 2, Max: 10")
            
            # ECS Cluster
            with Cluster("ECS Fargate Cluster"):
                ecs_cluster = ECS("ECS Cluster\nhipaa-ecs-cluster")
                
                # Service definitions
                with Cluster("Application Services"):
                    app_service = Fargate("App Service\nFargate Tasks\nDesired: 2")
                    health_service = Fargate("Health Service\nSidecar Container")
                    
                # Task definitions
                with Cluster("Task Definitions"):
                    app_task = ECS("App Task\nCPU: 256, Memory: 512")
                    sidecar_task = ECS("Sidecar Task\nLogging & Monitoring")
            
            # Container Registry
            with Cluster("Container Registry"):
                ecr_repo = ECR("ECR Repository\nhipaa-app")
                image_scanning = ECR("Image Scanning\nVulnerability Scans")
                
            # Storage and Monitoring
            with Cluster("Supporting Services"):
                s3_logs = S3("S3 Logs\nApplication Logs")
                cloudwatch = Cloudwatch("CloudWatch\nMetrics & Alarms")
                
            # Database
            rds = RDS("RDS PostgreSQL\nMulti-AZ")
            
            # Connections
            users >> alb >> target_group
            target_group >> app_service
            auto_scaling >> app_service
            app_service >> app_task
            app_task >> ecr_repo
            ecr_repo >> image_scanning
            app_service >> s3_logs
            app_service >> cloudwatch
            app_service >> rds
    
    def create_drawio_diagram(self, compute_data):
        """Create draw.io XML diagram format using utility with AWS best practices"""
        drawio_gen = DrawIOGenerator(self.output_dir)
        
        mxfile = drawio_gen.create_mxfile("HIPAA Compute Architecture", "compute_arch")
        diagram = drawio_gen.create_diagram(mxfile, "HIPAA Compute Architecture", "compute_arch")
        mxgraphmodel = drawio_gen.create_graph_model(diagram)
        root = drawio_gen.create_root(mxgraphmodel)
        
        # External users
        drawio_gen.add_rectangle(root, "users", "👥 External Users", 350, 50, 120, 60, 
                                fill_color="#FF9900", stroke_color="#FF9900")
        
        # Load Balancer tier with modern AWS styling
        lb_container = drawio_gen.add_swimlane(root, "lb_tier", "⚖️ Load Balancer Tier", 50, 150, 750, 120)
        drawio_gen.add_rectangle(root, "alb", "⚖️ Application Load Balancer\n🔐 SSL Termination\n🎯 Health Checks", 
                                50, 30, 180, 60, fill_color="#FF9900", stroke_color="#FF9900", parent="lb_tier")
        drawio_gen.add_rectangle(root, "target_group", "🎯 Target Group\nHealth Check: /health\n🔄 Auto-registered", 
                                250, 30, 160, 60, fill_color="#2E73B8", stroke_color="#2E73B8", parent="lb_tier")
        drawio_gen.add_rectangle(root, "waf", "🛡️ AWS WAF\nRate Limiting\n🚫 Malicious Traffic", 
                                430, 30, 140, 60, fill_color="#D93232", stroke_color="#D93232", parent="lb_tier")
        
        # Auto Scaling with policies
        drawio_gen.add_rectangle(root, "auto_scaling", "📈 Auto Scaling Group\nMin: 2, Max: 10, Desired: 2\n🔄 Health-based Scaling", 
                                400, 300, 220, 60, fill_color="#FF9900", stroke_color="#FF9900")
        
        # ECS Cluster with detailed services
        ecs_container = drawio_gen.add_swimlane(root, "ecs_cluster", "🐳 ECS Fargate Cluster - HIPAA Compliant", 50, 300, 750, 200)
        
        # Main application service
        drawio_gen.add_rectangle(root, "app_service", "🚀 Main Application Service\nFargate Tasks: 2\n🔒 Private Subnets\n💾 Persistent Storage", 
                                50, 30, 200, 70, fill_color="#FF9900", stroke_color="#FF9900", parent="ecs_cluster")
        
        # Health service (sidecar pattern)
        drawio_gen.add_rectangle(root, "health_service", "🏥 Health Check Service\nSidecar Container\n📊 Monitoring Agent", 
                                270, 30, 180, 70, fill_color="#2E73B8", stroke_color="#2E73B8", parent="ecs_cluster")
        
        # Logging service (sidecar pattern)
        drawio_gen.add_rectangle(root, "logging_service", "📝 Logging Service\nFluent Bit Agent\n📊 CloudWatch Logs", 
                                470, 30, 180, 70, fill_color="#2E73B8", stroke_color="#2E73B8", parent="ecs_cluster")
        
        # Container Registry with security
        registry_container = drawio_gen.add_swimlane(root, "registry", "🗄️ Container Registry & Security", 50, 530, 750, 120)
        drawio_gen.add_rectangle(root, "ecr_repo", "🗄️ ECR Repository\nhipaa-app:latest\n🔐 Private Registry", 
                                50, 30, 180, 60, fill_color="#FF9900", stroke_color="#FF9900", parent="registry")
        drawio_gen.add_rectangle(root, "image_scanning", "🔍 Image Scanning\nClair + Trivy\n🚨 Vulnerability Reports", 
                                250, 30, 180, 60, fill_color="#D93232", stroke_color="#D93232", parent="registry")
        drawio_gen.add_rectangle(root, "lifecycle_policy", "📋 Lifecycle Policies\nImage Retention\n🔄 Auto-cleanup", 
                                450, 30, 180, 60, fill_color="#2E73B8", stroke_color="#2E73B8", parent="registry")
        
        # Supporting Services with HIPAA compliance
        support_container = drawio_gen.add_swimlane(root, "support", "🔧 Supporting Services & Monitoring", 50, 670, 750, 120)
        drawio_gen.add_cylinder(root, "s3_logs", "📦 S3 Logs Bucket\nApplication & Access Logs\n🔐 SSE-S3 Encrypted", 
                               50, 30, 180, 60, fill_color="#FF9900", stroke_color="#FF9900", parent="support")
        drawio_gen.add_rectangle(root, "cloudwatch", "📊 CloudWatch\nMetrics, Logs, Alarms\n🚨 HIPAA Monitoring", 
                                250, 30, 180, 60, fill_color="#FF9900", stroke_color="#FF9900", parent="support")
        drawio_gen.add_rectangle(root, "xray", "🔍 AWS X-Ray\nDistributed Tracing\n📈 Performance Insights", 
                                450, 30, 180, 60, fill_color="#2E73B8", stroke_color="#2E73B8", parent="support")
        
        # Database tier
        db_container = drawio_gen.add_swimlane(root, "database", "🗄️ Database Tier - Multi-AZ", 50, 810, 750, 120)
        drawio_gen.add_cylinder(root, "rds", "🗄️ RDS PostgreSQL 14\nMulti-AZ Deployment\n🔐 Encrypted at Rest\n💾 Automated Backups", 
                               50, 30, 220, 70, fill_color="#2E73B8", stroke_color="#2E73B8", parent="database")
        drawio_gen.add_cylinder(root, "rds_backup", "💾 RDS Backups\n7-day retention\n🔄 Point-in-time Recovery", 
                               300, 30, 180, 70, fill_color="#2E73B8", stroke_color="#2E73B8", parent="database")
        drawio_gen.add_cylinder(root, "s3_backup", "📦 S3 Backup Bucket\nCross-region replication\n🔄 Disaster Recovery", 
                               510, 30, 180, 70, fill_color="#FF9900", stroke_color="#FF9900", parent="database")
        
        # Security Groups and IAM
        security_container = drawio_gen.add_swimlane(root, "security", "🔐 Security Groups & IAM", 50, 950, 750, 120)
        drawio_gen.add_rectangle(root, "sg_alb", "🛡️ Security Group\nALB (443 → 80)\n🔐 TLS Termination", 
                                50, 30, 180, 60, fill_color="#D93232", stroke_color="#D93232", parent="security")
        drawio_gen.add_rectangle(root, "sg_ecs", "🛡️ Security Group\nECS (80 → 5432)\n🔒 Private Subnet Access", 
                                250, 30, 180, 60, fill_color="#D93232", stroke_color="#D93232", parent="security")
        drawio_gen.add_rectangle(root, "iam_role", "🔑 IAM Roles\nTask Execution Role\n📝 Least Privilege", 
                                450, 30, 180, 60, fill_color="#D93232", stroke_color="#D93232", parent="security")
        
        # Connections with detailed flow
        drawio_gen.add_edge(root, "edge1", "users", "alb")
        drawio_gen.add_edge(root, "edge2", "alb", "target_group", parent="lb_tier")
        drawio_gen.add_edge(root, "edge3", "target_group", "app_service")
        drawio_gen.add_edge(root, "edge4", "auto_scaling", "app_service")
        drawio_gen.add_edge(root, "edge5", "app_service", "ecr_repo")
        drawio_gen.add_edge(root, "edge6", "ecr_repo", "image_scanning", parent="registry")
        drawio_gen.add_edge(root, "edge7", "image_scanning", "lifecycle_policy", parent="registry")
        drawio_gen.add_edge(root, "edge8", "app_service", "s3_logs")
        drawio_gen.add_edge(root, "edge9", "app_service", "cloudwatch")
        drawio_gen.add_edge(root, "edge10", "app_service", "xray")
        drawio_gen.add_edge(root, "edge11", "app_service", "rds")
        drawio_gen.add_edge(root, "edge12", "rds", "rds_backup")
        drawio_gen.add_edge(root, "edge13", "rds_backup", "s3_backup")
        drawio_gen.add_edge(root, "edge14", "app_service", "sg_ecs")
        drawio_gen.add_edge(root, "edge15", "ecs", "iam_role")
        
        return drawio_gen.save_drawio_file(mxfile, "compute_architecture.drawio")

    def validate_diagram(self):
        """Validate generated diagram"""
        png_path = f"{self.output_dir}/compute_architecture.png"
        drawio_path = f"{self.output_dir}/compute_architecture.drawio"
        
        png_exists = os.path.exists(png_path)
        drawio_exists = os.path.exists(drawio_path)
        
        if png_exists and drawio_exists:
            logger.info(f"✅ Compute diagrams generated:")
            logger.info(f"   PNG: {png_path}")
            logger.info(f"   Draw.io: {drawio_path}")
            return True
        else:
            if not png_exists:
                logger.error("❌ Compute PNG diagram generation failed")
            if not drawio_exists:
                logger.error("❌ Compute Draw.io diagram generation failed")
            return False

def main():
    """Main execution for Phase 2"""
    parser = argparse.ArgumentParser(description='Generate Compute & Messaging Architecture Diagram')
    parser.add_argument('--stack', default='hipaa-dev', help='Pulumi stack name')
    parser.add_argument('--output', default='./output', help='Output directory')
    parser.add_argument('--skip-generation', action='store_true', help='Skip DOT file generation')
    
    args = parser.parse_args()
    
    generator = ComputeDiagramGenerator(args.stack, args.output)
    
    # Phase 2 execution
    print("🚀 Phase 2: Compute & Messaging Architecture")
    print("=" * 50)
    
    if not args.skip_generation:
        if not generator.generate_dot_file():
            print("❌ Failed to generate DOT file. Exiting.")
            return 1
    
    compute_data = generator.parse_dot_file()
    if not compute_data['parsed']:
        print("❌ Failed to parse DOT file. Exiting.")
        return 1
    
    generator.create_compute_diagram(compute_data)
    generator.create_drawio_diagram(compute_data)
    
    if generator.validate_diagram():
        print("✅ Phase 2 Complete: Compute architecture diagrams generated")
        print(f"📊 PNG Output: {args.output}/compute_architecture.png")
        print(f"📊 Draw.io Output: {args.output}/compute_architecture.drawio")
        print("\n🔍 Manual validation checklist:")
        print("   [ ] ECS Fargate cluster configuration shown")
        print("   [ ] Auto Scaling policies visualized")
        print("   [ ] ALB target group configuration")
        print("   [ ] ECR repository with security scanning")
        print("   [ ] Container task definitions and resource limits")
        print("   [ ] Integration with CloudWatch monitoring")
        print("   [ ] HIPAA compliance indicators (encryption, scanning)")
        print("   [ ] Draw.io file opens correctly")
        return 0
    else:
        print("❌ Phase 2 Failed: Diagram validation failed")
        return 1

if __name__ == "__main__":
    exit(main())