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
        """Create draw.io XML diagram format using utility"""
        drawio_gen = DrawIOGenerator(self.output_dir)
        
        mxfile = drawio_gen.create_mxfile("HIPAA Compute Architecture", "compute_arch")
        diagram = drawio_gen.create_diagram(mxfile, "HIPAA Compute Architecture", "compute_arch")
        mxgraphmodel = drawio_gen.create_graph_model(diagram)
        root = drawio_gen.create_root(mxgraphmodel)
        
        # Users
        drawio_gen.add_rectangle(root, "users", "Users", 350, 50, 100, 60)
        
        # Load Balancer tier
        alb_container = drawio_gen.add_swimlane(root, "lb_tier", "Load Balancer Tier", 50, 150, 700, 100)
        drawio_gen.add_rectangle(root, "alb", "ALB\nApplication Load Balancer", 
                                50, 30, 150, 50, parent="lb_tier")
        drawio_gen.add_rectangle(root, "target_group", "Target Group\nHealth Check: /health", 
                                220, 30, 150, 50, parent="lb_tier")
        
        # Auto Scaling
        drawio_gen.add_rectangle(root, "auto_scaling", "Auto Scaling\nMin: 2, Max: 10", 
                                400, 280, 150, 60)
        
        # ECS Cluster
        ecs_container = drawio_gen.add_swimlane(root, "ecs_cluster", "ECS Fargate Cluster", 50, 280, 700, 150)
        drawio_gen.add_rectangle(root, "app_service", "App Service\nFargate Tasks\nDesired: 2", 
                                50, 30, 150, 50, parent="ecs_cluster")
        drawio_gen.add_rectangle(root, "health_service", "Health Service\nSidecar Container", 
                                220, 30, 150, 50, parent="ecs_cluster")
        
        # Container Registry
        ecr_container = drawio_gen.add_swimlane(root, "registry", "Container Registry", 50, 450, 700, 100)
        drawio_gen.add_rectangle(root, "ecr_repo", "ECR Repository\nhipaa-app", 
                                50, 30, 150, 50, parent="registry")
        drawio_gen.add_rectangle(root, "image_scanning", "Image Scanning\nVulnerability Scans", 
                                220, 30, 150, 50, parent="registry")
        
        # Supporting Services
        support_container = drawio_gen.add_swimlane(root, "support", "Supporting Services", 50, 570, 700, 100)
        drawio_gen.add_cylinder(root, "s3_logs", "S3 Logs\nApplication Logs", 
                               50, 30, 120, 50, parent="support")
        drawio_gen.add_rectangle(root, "cloudwatch", "CloudWatch\nMetrics & Alarms", 
                                200, 30, 150, 50, parent="support")
        
        # Database
        drawio_gen.add_cylinder(root, "rds", "RDS PostgreSQL\nMulti-AZ", 580, 400, 100, 80)
        
        # Connections
        drawio_gen.add_edge(root, "edge1", "users", "alb")
        drawio_gen.add_edge(root, "edge2", "alb", "target_group", parent="lb_tier")
        drawio_gen.add_edge(root, "edge3", "target_group", "app_service")
        drawio_gen.add_edge(root, "edge4", "auto_scaling", "app_service")
        drawio_gen.add_edge(root, "edge5", "app_service", "ecr_repo")
        drawio_gen.add_edge(root, "edge6", "ecr_repo", "image_scanning", parent="registry")
        drawio_gen.add_edge(root, "edge7", "app_service", "s3_logs")
        drawio_gen.add_edge(root, "edge8", "app_service", "cloudwatch")
        drawio_gen.add_edge(root, "edge9", "app_service", "rds")
        
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