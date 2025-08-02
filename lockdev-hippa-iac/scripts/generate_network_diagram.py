#!/usr/bin/env python3
"""
Phase 1: Network Architecture Diagram Generator
Generates network-focused infrastructure visualization for HIPAA-compliant AWS stack
"""

import subprocess
import json
import os
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.network import VPC, NATGateway, InternetGateway, ELB
from diagrams.aws.compute import ECS, EC2
from diagrams.aws.database import RDS
from diagrams.aws.storage import S3
from diagrams.generic.network import Subnet
from diagrams.onprem.client import Users
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NetworkDiagramGenerator:
    def __init__(self, stack_name="hipaa-dev", output_dir="./output"):
        self.stack_name = stack_name
        self.output_dir = output_dir
        self.dot_file = "Pulumi.dot"
        self.resources = {}
        
    def generate_dot_file(self):
        """Generate DOT file from Pulumi stack"""
        try:
            logger.info("Generating Pulumi graph...")
            cmd = ["pulumi", "graph", "--stack", self.stack_name]
            with open(self.dot_file, 'w') as f:
                result = subprocess.run(cmd, capture_output=True, text=True, cwd="../")
                if result.returncode != 0:
                    logger.error(f"Pulumi graph failed: {result.stderr}")
                    return False
                f.write(result.stdout)
            logger.info(f"DOT file generated: {self.dot_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to generate DOT file: {e}")
            return False
    
    def parse_dot_file(self):
        """Parse DOT file and extract network resources"""
        try:
            with open(self.dot_file, 'r') as f:
                content = f.read()
            
            # Extract VPC information
            vpc_info = self._extract_vpc_info(content)
            subnet_info = self._extract_subnet_info(content)
            
            return {
                'vpc': vpc_info,
                'subnets': subnet_info,
                'parsed': True
            }
        except Exception as e:
            logger.error(f"Failed to parse DOT file: {e}")
            return {'parsed': False}
    
    def _extract_vpc_info(self, content):
        """Extract VPC configuration from DOT content"""
        # Mock VPC info for now - will parse from actual DOT
        return {
            'name': 'hipaa-vpc',
            'cidr': '10.0.0.0/16',
            'availability_zones': ['us-east-1a', 'us-east-1b']
        }
    
    def _extract_subnet_info(self, content):
        """Extract subnet configuration from DOT content"""
        # Mock subnet info for now - will parse from actual DOT
        return {
            'public_subnets': [
                {'name': 'public-subnet-1', 'az': 'us-east-1a', 'cidr': '10.0.1.0/24'},
                {'name': 'public-subnet-2', 'az': 'us-east-1b', 'cidr': '10.0.2.0/24'}
            ],
            'private_subnets': [
                {'name': 'private-subnet-1', 'az': 'us-east-1a', 'cidr': '10.0.3.0/24'},
                {'name': 'private-subnet-2', 'az': 'us-east-1b', 'cidr': '10.0.4.0/24'}
            ]
        }
    
    def create_network_diagram(self, network_data):
        """Create network architecture diagram"""
        filename = f"{self.output_dir}/network_architecture"
        
        with Diagram(
            "HIPAA Network Architecture",
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
            # Internet Gateway
            internet = InternetGateway("Internet Gateway")
            
            # NAT Gateways
            nat1 = NATGateway("NAT Gateway 1")
            nat2 = NATGateway("NAT Gateway 2")
            
            # Main VPC
            with Cluster("HIPAA VPC (10.0.0.0/16)"):
                # Public Subnets
                with Cluster("Public Subnets"):
                    public_subnet1 = Subnet("Public Subnet 1\n(10.0.1.0/24)\nus-east-1a")
                    public_subnet2 = Subnet("Public Subnet 2\n(10.0.2.0/24)\nus-east-1b")
                
                # Private Subnets
                with Cluster("Private Subnets"):
                    private_subnet1 = Subnet("Private Subnet 1\n(10.0.3.0/24)\nus-east-1a")
                    private_subnet2 = Subnet("Private Subnet 2\n(10.0.4.0/24)\nus-east-1b")
                
                # Load Balancer
                alb = ELB("Application Load Balancer")
                
                # Application tier
                with Cluster("Application Tier"):
                    ecs_cluster = ECS("ECS Cluster")
                
                # Database tier
                with Cluster("Database Tier"):
                    rds = RDS("RDS PostgreSQL\n(Multi-AZ)")
                
                # Storage
                s3_logs = S3("S3 Logs Bucket")
                
                # Connections
                internet >> alb
                alb >> ecs_cluster
                ecs_cluster >> rds
                
                # NAT Gateway connections
                nat1 >> private_subnet1
                nat2 >> private_subnet2
    
    def validate_diagram(self):
        """Validate generated diagram"""
        diagram_path = f"{self.output_dir}/network_architecture.png"
        if os.path.exists(diagram_path):
            logger.info(f"✅ Network diagram generated: {diagram_path}")
            return True
        else:
            logger.error("❌ Network diagram generation failed")
            return False

def main():
    """Main execution for Phase 1"""
    parser = argparse.ArgumentParser(description='Generate Network Architecture Diagram')
    parser.add_argument('--stack', default='hipaa-dev', help='Pulumi stack name')
    parser.add_argument('--output', default='./output', help='Output directory')
    parser.add_argument('--skip-generation', action='store_true', help='Skip DOT file generation')
    
    args = parser.parse_args()
    
    generator = NetworkDiagramGenerator(args.stack, args.output)
    
    # Phase 1 execution
    print("🚀 Phase 1: Network Architecture Diagram")
    print("=" * 50)
    
    if not args.skip_generation:
        if not generator.generate_dot_file():
            print("❌ Failed to generate DOT file. Exiting.")
            return 1
    
    network_data = generator.parse_dot_file()
    if not network_data['parsed']:
        print("❌ Failed to parse DOT file. Exiting.")
        return 1
    
    generator.create_network_diagram(network_data)
    
    if generator.validate_diagram():
        print("✅ Phase 1 Complete: Network architecture diagram generated")
        print(f"📊 Output: {args.output}/network_architecture.png")
        print("\n🔍 Manual validation checklist:")
        print("   [ ] VPC boundaries correctly shown")
        print("   [ ] Public/private subnets in correct AZs")
        print("   [ ] Internet Gateway and NAT Gateways positioned correctly")
        print("   [ ] Security group relationships clear")
        print("   [ ] Load balancer placement accurate")
        print("   [ ] Database tier properly isolated")
        return 0
    else:
        print("❌ Phase 1 Failed: Diagram validation failed")
        return 1

if __name__ == "__main__":
    exit(main())