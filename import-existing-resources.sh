#!/bin/bash

# Script to import existing AWS resources into Pulumi stack
# This handles conflicts from resources that already exist

echo "Importing existing AWS resources into Pulumi stack..."

cd lockdev-hippa-iac

# Set AWS profile for deployment - use root credentials for import
export AWS_PROFILE=dev-root

# Import existing IAM roles
echo "Importing existing IAM roles..."
poetry run pulumi import --yes aws:iam/role:Role ecs-task-role hipaa-ecs-task-role
poetry run pulumi import --yes aws:iam/role:Role ecs-task-execution-role hipaa-ecs-task-execution-role  
poetry run pulumi import --yes aws:iam/role:Role cloudwatch-role hipaa-cloudwatch-role
poetry run pulumi import --yes aws:iam/role:Role cloudtrail-role hipaa-cloudtrail-role
poetry run pulumi import --yes aws:iam/role:Role config-role hipaa-config-role

# Import existing KMS alias
echo "Importing existing KMS alias..."
poetry run pulumi import --yes aws:kms/alias:Alias hipaa-kms-alias alias/hipaa-encryption-key

# Import existing SNS topic
echo "Importing existing SNS topic..."
poetry run pulumi import --yes aws:sns/topic:Topic guardduty-findings-topic arn:aws:sns:us-east-1:067518243012:hipaa-guardduty-findings

# Import existing CloudWatch log groups
echo "Importing existing CloudWatch log groups..."
poetry run pulumi import --yes aws:cloudwatch/logGroup:LogGroup guardduty-log-group /aws/guardduty/findings

# Import existing RDS parameter group
echo "Importing existing RDS parameter group..."
poetry run pulumi import --yes aws:rds/parameterGroup:ParameterGroup hipaa-db-parameter-group hipaa-postgres-params

# Import existing ECR repository
echo "Importing existing ECR repository..."
poetry run pulumi import --yes aws:ecr/repository:Repository hipaa-app-repo hipaa-app

echo "Import completed. You can now run 'make deploy-dev' to continue deployment."