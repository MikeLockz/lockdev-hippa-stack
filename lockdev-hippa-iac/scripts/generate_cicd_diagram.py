#!/usr/bin/env python3
"""
Phase 5: CI/CD Pipeline Architecture Diagram Generator
Visualizes the complete continuous integration and deployment pipeline
"""

import subprocess
import json
import os
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.devtools import Codepipeline, Codebuild, Codecommit, Codestar
from diagrams.aws.compute import ECS, Lambda
from diagrams.aws.storage import S3
from diagrams.aws.security import IAM, SecretsManager
from diagrams.aws.management import Cloudwatch
from diagrams.onprem.vcs import Github
from diagrams.onprem.container import Docker
from diagrams.onprem.ci import GithubActions
from diagrams.generic.blank import Blank
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CICDDiagramGenerator:
    def __init__(self, stack_name="hipaa-dev", output_dir="./output"):
        self.stack_name = stack_name
        self.output_dir = output_dir
        self.resources = {}
        
    def analyze_github_workflows(self):
        """Analyze GitHub Actions workflows from the repository"""
        workflows_dir = "../.github/workflows"
        workflows = []
        
        try:
            if os.path.exists(workflows_dir):
                for file in os.listdir(workflows_dir):
                    if file.endswith('.yml') or file.endswith('.yaml'):
                        file_path = os.path.join(workflows_dir, file)
                        with open(file_path, 'r') as f:
                            content = f.read()
                            workflows.append({
                                'name': file,
                                'content': content,
                                'type': self._determine_workflow_type(file)
                            })
            else:
                logger.warning("GitHub workflows directory not found, using mock data")
                workflows = self._get_mock_workflows()
                
        except Exception as e:
            logger.error(f"Failed to analyze workflows: {e}")
            workflows = self._get_mock_workflows()
            
        return workflows
    
    def _determine_workflow_type(self, filename):
        """Determine workflow type based on filename"""
        filename_lower = filename.lower()
        if 'infrastructure' in filename_lower or 'iac' in filename_lower:
            return 'infrastructure'
        elif 'application' in filename_lower or 'app' in filename_lower:
            return 'application'
        elif 'security' in filename_lower or 'scan' in filename_lower:
            return 'security'
        else:
            return 'general'
    
    def _get_mock_workflows(self):
        """Return mock workflow data when actual files aren't available"""
        return [
            {
                'name': 'infrastructure.yml',
                'type': 'infrastructure',
                'content': 'Infrastructure deployment workflow'
            },
            {
                'name': 'application.yml',
                'type': 'application',
                'content': 'Application deployment workflow'
            },
            {
                'name': 'security-scan.yml',
                'type': 'security',
                'content': 'Security scanning workflow'
            }
        ]
    
    def create_cicd_diagram(self, workflows):
        """Create CI/CD pipeline architecture diagram"""
        filename = f"{self.output_dir}/cicd_pipeline_architecture"
        
        with Diagram(
            "HIPAA CI/CD Pipeline Architecture",
            filename=filename,
            show=False,
            direction="LR",
            graph_attr={
                "bgcolor": "white",
                "pad": "0.5",
                "ranksep": "1.5",
                "nodesep": "1.0"
            }
        ):
            # Source code repositories
            with Cluster("Source Code Management"):
                github = Github("GitHub Repository")
                codecommit = Codecommit("CodeCommit\n(Backup)")
            
            # CI/CD Pipeline
            with Cluster("CI/CD Pipeline"):
                # GitHub Actions
                github_actions = GithubActions("GitHub Actions\nCI/CD Engine")
                
                # Build stages
                with Cluster("Build & Test Stages"):
                    code_quality = Codebuild("Code Quality\n(Lint, Format)")
                    security_scan = Codebuild("Security Scan\n(Trivy, Bandit)")
                    unit_tests = Codebuild("Unit Tests\n(Pytest)")
                    integration_tests = Codebuild("Integration Tests")
                    
                # Containerization
                with Cluster("Container Build"):
                    docker_build = Docker("Docker Build")
                    ecr_push = ECS("ECR Push")
            
            # Deployment pipeline
            with Cluster("Deployment Pipeline"):
                with Cluster("Development Environment"):
                    dev_deploy = Codepipeline("Dev Deploy")
                    dev_ecs = ECS("Dev ECS")
                    
                with Cluster("Staging Environment"):
                    staging_deploy = Codepipeline("Staging Deploy")
                    staging_ecs = ECS("Staging ECS")
                    staging_tests = Codebuild("Staging Tests")
                    
                with Cluster("Production Environment"):
                    prod_approval = Lambda("Manual Approval")
                    prod_deploy = Codepipeline("Production Deploy")
                    prod_ecs = ECS("Production ECS")
                    
            # Security & Compliance
            with Cluster("Security & Compliance"):
                secrets = SecretsManager("Secrets Manager")
                iam_roles = IAM("IAM Roles")
                compliance_checks = Lambda("HIPAA Compliance\nChecks")
                
            # Monitoring & Observability
            with Cluster("Monitoring & Rollback"):
                cloudwatch = Cloudwatch("CloudWatch\nMonitoring")
                rollback_trigger = Lambda("Auto Rollback\n(CloudWatch Alarms)")
                s3_artifacts = S3("Build Artifacts")
            
            # Disaster Recovery
            with Cluster("Disaster Recovery"):
                backup_s3 = S3("Backup Storage")
                dr_trigger = Lambda("DR Trigger")
                cross_region = S3("Cross-Region\nReplication")
            
            # Define connections
            # Source to CI/CD
            github >> github_actions
            github >> codecommit
            
            # CI/CD workflow
            github_actions >> code_quality >> security_scan >> unit_tests >> integration_tests
            integration_tests >> docker_build >> ecr_push
            
            # Deployment flow
            ecr_push >> dev_deploy >> dev_ecs
            dev_deploy >> staging_deploy >> staging_ecs
            staging_ecs >> staging_tests
            staging_tests >> prod_approval >> prod_deploy >> prod_ecs
            
            # Security integration
            secrets >> dev_deploy
            secrets >> staging_deploy
            secrets >> prod_deploy
            iam_roles >> github_actions
            
            # Compliance checks
            security_scan >> compliance_checks
            compliance_checks >> prod_approval
            
            # Monitoring
            dev_ecs >> cloudwatch
            staging_ecs >> cloudwatch
            prod_ecs >> cloudwatch
            cloudwatch >> rollback_trigger
            rollback_trigger >> prod_deploy
            
            # Artifacts
            docker_build >> s3_artifacts
            unit_tests >> s3_artifacts
            
            # Disaster recovery
            prod_ecs >> backup_s3
            backup_s3 >> cross_region
            cloudwatch >> dr_trigger
    
    def create_detailed_workflow_diagram(self, workflows):
        """Create detailed workflow-specific diagrams"""
        filename = f"{self.output_dir}/github_workflows_detailed"
        
        with Diagram(
            "GitHub Actions Workflows - Detailed View",
            filename=filename,
            show=False,
            direction="TB",
            graph_attr={
                "bgcolor": "white",
                "pad": "0.5",
                "ranksep": "1.0",
                "nodesep": "0.8"
            }
        ):
            # Infrastructure workflow
            with Cluster("Infrastructure Pipeline"):
                infra_trigger = Github("Infrastructure\nCode Push")
                infra_plan = Codebuild("Terraform Plan")
                infra_scan = Codebuild("Checkov Scan")
                infra_approve = Lambda("Manual Approval")
                infra_apply = Codebuild("Terraform Apply")
                infra_validate = Codebuild("Post-Deployment\nValidation")
            
            # Application workflow
            with Cluster("Application Pipeline"):
                app_trigger = Github("Application\nCode Push")
                app_test = Codebuild("Run Tests")
                app_security = Codebuild("Security Scan")
                app_build = Codebuild("Build Docker\nImage")
                app_deploy_dev = Codebuild("Deploy to Dev")
                app_test_dev = Codebuild("Dev Integration\nTests")
                app_deploy_staging = Codebuild("Deploy to Staging")
                app_test_staging = Codebuild("Staging Tests")
                app_deploy_prod = Codebuild("Deploy to Production")
            
            # Security workflow
            with Cluster("Security Pipeline"):
                sec_schedule = Lambda("Scheduled\nSecurity Scan")
                sec_sca = Codebuild("SCA Scan\n(Dependencies)")
                sec_sast = Codebuild("SAST Scan\n(Code Analysis)")
                sec_container = Codebuild("Container Scan")
                sec_report = Lambda("Security\nReport")
            
            # Connections
            infra_trigger >> infra_plan >> infra_scan >> infra_approve >> infra_apply >> infra_validate
            app_trigger >> app_test >> app_security >> app_build >> app_deploy_dev >> app_test_dev >> app_deploy_staging >> app_test_staging >> app_deploy_prod
            sec_schedule >> sec_sca >> sec_sast >> sec_container >> sec_report
    
    def validate_diagram(self):
        """Validate generated CI/CD diagrams"""
        cicd_path = f"{self.output_dir}/cicd_pipeline_architecture.png"
        detailed_path = f"{self.output_dir}/github_workflows_detailed.png"
        
        cicd_exists = os.path.exists(cicd_path)
        detailed_exists = os.path.exists(detailed_path)
        
        if cicd_exists and detailed_exists:
            logger.info("✅ CI/CD diagrams generated successfully")
            logger.info(f"📊 Main diagram: {cicd_path}")
            logger.info(f"📊 Detailed workflows: {detailed_path}")
            return True
        else:
            logger.error("❌ CI/CD diagram generation failed")
            if not cicd_exists:
                logger.error(f"Missing: {cicd_path}")
            if not detailed_exists:
                logger.error(f"Missing: {detailed_path}")
            return False

def main():
    """Main execution for Phase 5"""
    parser = argparse.ArgumentParser(description='Generate CI/CD Pipeline Architecture Diagram')
    parser.add_argument('--stack', default='hipaa-dev', help='Pulumi stack name')
    parser.add_argument('--output', default='./output', help='Output directory')
    
    args = parser.parse_args()
    
    generator = CICDDiagramGenerator(args.stack, args.output)
    
    # Phase 5 execution
    print("🚀 Phase 5: CI/CD Pipeline Architecture")
    print("=" * 50)
    
    # Analyze existing workflows
    workflows = generator.analyze_github_workflows()
    print(f"📊 Analyzed {len(workflows)} GitHub workflows")
    
    # Create diagrams
    generator.create_cicd_diagram(workflows)
    generator.create_detailed_workflow_diagram(workflows)
    
    if generator.validate_diagram():
        print("✅ Phase 5 Complete: CI/CD pipeline diagrams generated")
        print(f"📊 Output: {args.output}/cicd_pipeline_architecture.png")
        print(f"📊 Output: {args.output}/github_workflows_detailed.png")
        print("\n🔍 Manual validation checklist:")
        print("   [ ] All GitHub Actions workflows represented")
        print("   [ ] Build stages correctly ordered")
        print("   [ ] Security scanning stages included")
        print("   [ ] Deployment environments shown (dev/staging/prod)")
        print("   [ ] Manual approval gates indicated")
        print("   [ ] Rollback mechanisms shown")
        print("   [ ] Artifact storage and backup included")
        print("   [ ] Cross-environment promotion flow clear")
        return 0
    else:
        print("❌ Phase 5 Failed: Diagram validation failed")
        return 1

if __name__ == "__main__":
    exit(main())