#!/bin/bash

# Script to import existing AWS resources into Pulumi stack
# This handles conflicts from resources that already exist

echo "Importing existing AWS resources into Pulumi stack..."

cd lockdev-hippa-iac

# Set AWS profile for deployment
export AWS_PROFILE=pulumi-deploy-user-dev

# Import existing SNS topic
echo "Importing existing SNS topic..."
pulumi import aws:sns/topic:Topic guardduty-findings-topic arn:aws:sns:us-east-1:067518243012:hipaa-guardduty-findings

# Import existing RDS parameter group
echo "Importing existing RDS parameter group..."
pulumi import aws:rds/parameterGroup:ParameterGroup hipaa-db-parameter-group hipaa-postgres-params

# Import existing ECR repository
echo "Importing existing ECR repository..."
pulumi import aws:ecr/repository:Repository hipaa-app-repo hipaa-app

# Import existing CloudWatch log group
echo "Importing existing CloudWatch log group..."
pulumi import aws:cloudwatch/logGroup:LogGroup guardduty-log-group /aws/guardduty/findings

echo "Import completed. You can now run 'make deploy-dev' to continue deployment."