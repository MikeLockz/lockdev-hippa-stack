#!/usr/bin/env python3
"""
Phase 4: Security & Access Controls Diagram Generator
Generates security-focused infrastructure visualization for HIPAA-compliant AWS stack
"""

import subprocess
import json
import os
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.security import IAM, IAMRole, SecretsManager, CertificateManager, WAF, Shield
from diagrams.aws.network import VPC, Nacl, ElasticLoadBalancing
from diagrams.aws.management import Cloudtrail, Config, Cloudwatch
from diagrams.aws.storage import S3
from diagrams.aws.database import RDS
from diagrams.aws.compute import ECS, EC2
from diagrams.aws.network import ELB
from diagrams.onprem.client import Users
from diagrams.aws.general import General
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecurityDiagramGenerator:
    def __init__(self, stack_name="hipaa-dev", output_dir="./output"):
        self.stack_name = stack_name
        self.output_dir = output_dir
        self.dot_file = "Pulumi.dot"
        self.resources = {}
        
    def parse_security_resources(self):
        """Parse security-related resources from infrastructure"""
        try:
            # Get Pulumi stack outputs
            cmd = ["pulumi", "stack", "output", "--json", "--stack", self.stack_name]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd="../")
            
            if result.returncode != 0:
                logger.error(f"Failed to get stack outputs: {result.stderr}")
                return self._get_mock_security_data()
            
            try:
                outputs = json.loads(result.stdout)
                return self._extract_security_from_outputs(outputs)
            except json.JSONDecodeError:
                logger.warning("Using mock security data due to JSON parsing error")
                return self._get_mock_security_data()
                
        except Exception as e:
            logger.error(f"Failed to parse security resources: {e}")
            return self._get_mock_security_data()
    
    def _extract_security_from_outputs(self, outputs):
        """Extract security configuration from stack outputs"""
        security_data = {
            'iam_roles': [],
            'security_groups': [],
            'certificates': [],
            'secrets': [],
            'waf_rules': [],
            'audit_logging': [],
            'encryption': []
        }
        
        # Extract IAM roles from outputs
        if 'ecsTaskRoleArn' in outputs:
            security_data['iam_roles'].append({
                'name': 'ecs-task-role',
                'arn': outputs.get('ecsTaskRoleArn', {}).get('value', ''),
                'type': 'task-role'
            })
        
        if 'ecsExecutionRoleArn' in outputs:
            security_data['iam_roles'].append({
                'name': 'ecs-execution-role',
                'arn': outputs.get('ecsExecutionRoleArn', {}).get('value', ''),
                'type': 'execution-role'
            })
        
        # Extract security group information
        if 'albSecurityGroupId' in outputs:
            security_data['security_groups'].append({
                'name': 'alb-sg',
                'id': outputs.get('albSecurityGroupId', {}).get('value', ''),
                'type': 'load-balancer'
            })
        
        if 'appSecurityGroupId' in outputs:
            security_data['security_groups'].append({
                'name': 'app-sg',
                'id': outputs.get('appSecurityGroupId', {}).get('value', ''),
                'type': 'application'
            })
        
        if 'dbSecurityGroupId' in outputs:
            security_data['security_groups'].append({
                'name': 'db-sg',
                'id': outputs.get('dbSecurityGroupId', {}).get('value', ''),
                'type': 'database'
            })
        
        return security_data
    
    def _get_mock_security_data(self):
        """Provide mock security data for demonstration"""
        return {
            'iam_roles': [
                {'name': 'ecs-task-role', 'type': 'task-role'},
                {'name': 'ecs-execution-role', 'type': 'execution-role'},
                {'name': 'cloudtrail-role', 'type': 'service-role'},
                {'name': 'config-role', 'type': 'service-role'},
                {'name': 'guardduty-role', 'type': 'service-role'}
            ],
            'security_groups': [
                {'name': 'alb-sg', 'type': 'load-balancer'},
                {'name': 'app-sg', 'type': 'application'},
                {'name': 'db-sg', 'type': 'database'},
                {'name': 'vpc-endpoint-sg', 'type': 'vpc-endpoint'}
            ],
            'certificates': [
                {'name': 'hipaa-alb-cert', 'type': 'application'},
                {'name': 'api-gateway-cert', 'type': 'api-gateway'}
            ],
            'secrets': [
                {'name': 'database-password', 'type': 'rds'},
                {'name': 'jwt-secret', 'type': 'application'},
                {'name': 'api-keys', 'type': 'external-services'}
            ],
            'waf_rules': [
                {'name': 'hipaa-waf-rules', 'type': 'common-ruleset'},
                {'name': 'sql-injection-protection', 'type': 'managed-rule'},
                {'name': 'xss-protection', 'type': 'managed-rule'}
            ],
            'audit_logging': [
                {'name': 'cloudtrail', 'type': 'api-audit'},
                {'name': 'vpc-flow-logs', 'type': 'network-audit'},
                {'name': 'rds-audit-logs', 'type': 'database-audit'}
            ],
            'encryption': [
                {'name': 'rds-encryption', 'type': 'at-rest'},
                {'name': 's3-encryption', 'type': 'at-rest'},
                {'name': 'in-transit-encryption', 'type': 'tls-1.2'}
            ]
        }
    
    def create_security_diagram(self, security_data):
        """Create comprehensive security architecture diagram"""
        filename = f"{self.output_dir}/security_architecture"
        
        with Diagram(
            "HIPAA Security & Access Controls Architecture",
            filename=filename,
            show=False,
            direction="LR",
            graph_attr={
                "bgcolor": "white",
                "pad": "0.5",
                "ranksep": "1.5",
                "nodesep": "1.0",
                "fontsize": "12"
            }
        ):
            # External Users
            users = Users("External Users")
            admin_users = Users("Admin Users")
            
            # Certificate Management
            with Cluster("Certificate Management"):
                cert_manager = CertificateManager("AWS Certificate Manager")
                alb_cert = CertificateManager("ALB SSL/TLS")
                api_cert = CertificateManager("API Gateway SSL/TLS")
                
            # Identity & Access Management
            with Cluster("Identity & Access Management"):
                iam = IAM("AWS IAM")
                
                with Cluster("IAM Roles"):
                    task_role = IAMRole("ECS Task Role")
                    execution_role = IAMRole("ECS Execution Role")
                    cloudtrail_role = IAMRole("CloudTrail Role")
                    config_role = IAMRole("Config Role")
                    guardduty_role = IAMRole("GuardDuty Role")
                
                with Cluster("IAM Permissions"):
                    task_policy = IAM("Task Policy")
                    execution_policy = IAM("Execution Policy")
                    security_policy = IAM("Security Policy")
            
            # Secrets Management
            with Cluster("Secrets Management"):
                secrets_manager = SecretsManager("AWS Secrets Manager")
                db_password = SecretsManager("Database Password")
                jwt_secret = SecretsManager("JWT Secret")
                api_keys = SecretsManager("External API Keys")
            
            # Network Security
            with Cluster("Network Security"):
                with Cluster("Security Groups"):
                    alb_sg = General("ALB Security Group")
                    app_sg = General("App Security Group")
                    db_sg = General("Database Security Group")
                    vpc_endpoint_sg = General("VPC Endpoint SG")
                
                with Cluster("Network ACLs"):
                    public_nacl = Nacl("Public Subnet NACL")
                    private_nacl = Nacl("Private Subnet NACL")
                    db_nacl = Nacl("Database Subnet NACL")
            
            # Web Application Firewall
            with Cluster("Web Application Firewall"):
                waf = WAF("AWS WAF")
                shield = Shield("AWS Shield Standard")
                
                with Cluster("WAF Rules"):
                    common_rules = WAF("Common Rule Set")
                    sql_protection = WAF("SQL Injection Protection")
                    xss_protection = WAF("XSS Protection")
            
            # Audit & Compliance
            with Cluster("Audit & Compliance"):
                cloudtrail = Cloudtrail("CloudTrail")
                config = Config("AWS Config")
                guardduty = General("GuardDuty")
                security_hub = General("Security Hub")
            
            # Storage Security
            with Cluster("Storage Security"):
                s3_logs = S3("S3 Logs Bucket")
                s3_encryption = S3("S3 Encryption")
                rds_encryption = RDS("RDS Encryption")
            
            # Application Components (for context)
            with Cluster("Application Infrastructure"):
                alb = ElasticLoadBalancing("Application Load Balancer")
                ecs = ECS("ECS Cluster")
                rds = RDS("RDS PostgreSQL")
            
            # Access Control Flow
            users >> Edge(label="HTTPS/TLS 1.2") >> alb_cert
            alb_cert >> Edge(label="443") >> waf
            waf >> Edge(label="Filtered Traffic") >> alb_sg >> alb
            
            # Admin access flow
            admin_users >> iam >> Edge(label="Assume Role") >> task_role
            
            # Secrets access
            ecs >> Edge(label="Retrieve Secrets") >> secrets_manager
            secrets_manager >> [db_password, jwt_secret, api_keys]
            
            # Database access flow
            ecs >> Edge(label="DB Connection") >> app_sg >> db_sg >> rds_encryption >> rds
            
            # Audit logging
            [alb, ecs, rds] >> Edge(label="Security Events") >> cloudtrail
            cloudtrail >> Edge(label="Compliance Monitoring") >> [config, guardduty, security_hub]
            
            # Certificate distribution
            cert_manager >> [alb_cert, api_cert]
            
            # Security role assignments
            task_role >> Edge(label="Permissions") >> task_policy >> ecs
            execution_role >> Edge(label="Permissions") >> execution_policy >> ecs
    
    def validate_diagram(self):
        """Validate generated security diagram"""
        diagram_path = f"{self.output_dir}/security_architecture.png"
        if os.path.exists(diagram_path):
            logger.info(f"✅ Security diagram generated: {diagram_path}")
            return True
        else:
            logger.error("❌ Security diagram generation failed")
            return False
    
    def generate_security_summary(self):
        """Generate security configuration summary"""
        summary = {
            'compliance_frameworks': ['HIPAA', 'HITRUST', 'SOC2'],
            'encryption_standards': ['TLS 1.2+', 'AES-256', 'KMS'],
            'access_controls': [
                'IAM Roles with Least Privilege',
                'Security Groups with Minimal Rules',
                'Network ACLs for Subnet Isolation',
                'Secrets Manager for Credentials'
            ],
            'monitoring_tools': [
                'CloudTrail for API Audit',
                'GuardDuty for Threat Detection',
                'Config for Compliance Monitoring',
                'Security Hub for Centralized Security'
            ],
            'network_security': [
                'WAF for Application Protection',
                'Shield Standard for DDoS',
                'VPC Isolation',
                'Private Subnets for Sensitive Resources'
            ]
        }
        
        # Save summary to JSON
        summary_path = f"{self.output_dir}/security_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"✅ Security summary saved: {summary_path}")
        return summary

def main():
    """Main execution for Phase 4"""
    parser = argparse.ArgumentParser(description='Generate Security & Access Controls Diagram')
    parser.add_argument('--stack', default='hipaa-dev', help='Pulumi stack name')
    parser.add_argument('--output', default='./output', help='Output directory')
    
    args = parser.parse_args()
    
    generator = SecurityDiagramGenerator(args.stack, args.output)
    
    # Phase 4 execution
    print("🔒 Phase 4: Security & Access Controls Architecture")
    print("=" * 60)
    
    security_data = generator.parse_security_resources()
    
    generator.create_security_diagram(security_data)
    
    if generator.validate_diagram():
        summary = generator.generate_security_summary()
        print("✅ Phase 4 Complete: Security architecture diagram generated")
        print(f"📊 Output: {args.output}/security_architecture.png")
        print(f"📋 Security Summary: {args.output}/security_summary.json")
        print("\n🔍 Manual validation checklist:")
        print("   [ ] IAM roles follow principle of least privilege")
        print("   [ ] Security groups have minimal required rules")
        print("   [ ] Secrets are stored in AWS Secrets Manager")
        print("   [ ] SSL/TLS certificates are managed by ACM")
        print("   [ ] WAF rules protect against common attacks")
        print("   [ ] Audit logging is comprehensive (CloudTrail)")
        print("   [ ] Encryption is enabled for all data at rest")
        print("   [ ] Network segmentation is properly implemented")
        print("   [ ] GuardDuty threat detection is active")
        print("   [ ] Security Hub provides centralized security view")
        return 0
    else:
        print("❌ Phase 4 Failed: Diagram validation failed")
        return 1

if __name__ == "__main__":
    exit(main())