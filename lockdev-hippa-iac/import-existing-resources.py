#!/usr/bin/env python3
"""
Script to import existing AWS resources into Pulumi state.
Run this before deploying to avoid conflicts.
"""

import subprocess
import sys
import json

def run_command(cmd, check=True):
    """Run a command and return the result."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)
        return result.stdout.strip() if result.stdout else ""
    except subprocess.CalledProcessError as e:
        if not check:
            return ""
        print(f"Error running command: {cmd}")
        print(f"Error: {e.stderr}")
        return ""

def check_resource_exists(resource_type, resource_name):
    """Check if an AWS resource exists."""
    print(f"Checking if {resource_type} {resource_name} exists...")
    
    if resource_type == "iam_role":
        cmd = f"aws iam get-role --role-name {resource_name}"
    elif resource_type == "sns_topic":
        cmd = f"aws sns get-topic-attributes --topic-arn arn:aws:sns:us-east-1:$(aws sts get-caller-identity --query Account --output text):{resource_name}"
    elif resource_type == "cloudwatch_log_group":
        cmd = f"aws logs describe-log-groups --log-group-name-prefix {resource_name}"
    else:
        return False
    
    result = run_command(cmd, check=False)
    return bool(result)

def import_resource(pulumi_resource_name, resource_type, aws_resource_id):
    """Import an existing AWS resource into Pulumi."""
    print(f"Importing {pulumi_resource_name} ({resource_type}) with ID: {aws_resource_id}")
    
    cmd = f"pulumi import {resource_type} {pulumi_resource_name} {aws_resource_id}"
    result = run_command(cmd, check=False)
    
    if "error" in result.lower():
        print(f"Failed to import {pulumi_resource_name}: {result}")
        return False
    else:
        print(f"Successfully imported {pulumi_resource_name}")
        return True

def main():
    """Main function to import existing resources."""
    print("Checking and importing existing AWS resources...")
    
    # Resources that might already exist
    resources_to_check = [
        {
            "pulumi_name": "ecs-task-execution-role",
            "type": "aws:iam/role:Role",
            "aws_name": "hipaa-ecs-task-execution-role",
            "check_type": "iam_role"
        },
        {
            "pulumi_name": "ecs-task-role", 
            "type": "aws:iam/role:Role",
            "aws_name": "hipaa-ecs-task-role",
            "check_type": "iam_role"
        },
        {
            "pulumi_name": "cloudwatch-role",
            "type": "aws:iam/role:Role", 
            "aws_name": "hipaa-cloudwatch-role",
            "check_type": "iam_role"
        },
        {
            "pulumi_name": "cloudtrail-role",
            "type": "aws:iam/role:Role",
            "aws_name": "hipaa-cloudtrail-role", 
            "check_type": "iam_role"
        },
        {
            "pulumi_name": "config-role",
            "type": "aws:iam/role:Role",
            "aws_name": "hipaa-config-role",
            "check_type": "iam_role"
        },
        {
            "pulumi_name": "guardduty-findings-topic",
            "type": "aws:sns/topic:Topic",
            "aws_name": "hipaa-guardduty-findings",
            "check_type": "sns_topic"
        },
        {
            "pulumi_name": "guardduty-log-group",
            "type": "aws:cloudwatch/logGroup:LogGroup", 
            "aws_name": "/aws/guardduty/findings",
            "check_type": "cloudwatch_log_group"
        }
    ]
    
    imported_count = 0
    
    for resource in resources_to_check:
        if check_resource_exists(resource["check_type"], resource["aws_name"]):
            if import_resource(resource["pulumi_name"], resource["type"], resource["aws_name"]):
                imported_count += 1
        else:
            print(f"Resource {resource['aws_name']} does not exist, skipping import")
    
    print(f"\nImport complete. Successfully imported {imported_count} resources.")
    print("You can now run 'make deploy-dev' to continue the deployment.")

if __name__ == "__main__":
    main()