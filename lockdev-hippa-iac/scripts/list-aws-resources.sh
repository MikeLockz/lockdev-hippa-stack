#!/bin/bash

# Script to list all AWS resources in the account
# This script uses AWS CLI to discover and list various resource types

set -e

echo "🔍 Discovering AWS Resources..."
echo "================================="
echo ""

# Auto-detect and set the best available AWS profile
if [[ -z "$AWS_PROFILE" ]]; then
    # Try default credentials first
    if aws sts get-caller-identity &> /dev/null; then
        echo "✅ Using default AWS credentials"
    else
        # Try dev-root profile
        unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
        export AWS_PROFILE=dev-root
        if aws sts get-caller-identity &> /dev/null; then
            echo "✅ Using dev-root profile credentials"
        else
            echo "❌ No valid AWS credentials found."
            echo "Please either:"
            echo "  1. Run 'aws configure' to set up AWS CLI credentials, or"
            echo "  2. Set AWS credentials in environment variables: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
            echo "  3. Configure the dev-root profile: aws configure --profile dev-root"
            exit 1
        fi
    fi
else
    # User explicitly set AWS_PROFILE, use it
    if aws sts get-caller-identity &> /dev/null; then
        echo "✅ Using $AWS_PROFILE profile credentials"
    else
        echo "❌ Failed to authenticate with $AWS_PROFILE profile"
        exit 1
    fi
fi

# Get account info
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_DEFAULT_REGION:-$(aws configure get region 2>/dev/null || echo "us-east-1")}
echo "Account: $ACCOUNT_ID | Region: $REGION"
echo ""

# Function to list resources with count
list_resources() {
    local service=$1
    local command=$2
    local description=$3
    
    echo "📋 $description..."
    local count=0
    
    case $service in
        "ec2")
            count=$(aws ec2 describe-instances --no-cli-pager --query 'length(Reservations[].Instances[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   EC2 Instances:"
                aws ec2 describe-instances --no-cli-pager --query 'Reservations[].Instances[].[InstanceId,InstanceType,State.Name,Tags[?Key==`Name`].Value|[0]]' --output table 2>/dev/null || echo "   No EC2 instances found"
            fi
            ;;
        "rds")
            count=$(aws rds describe-db-instances --no-cli-pager --query 'length(DBInstances[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   RDS Instances:"
                aws rds describe-db-instances --no-cli-pager --query 'DBInstances[].[DBInstanceIdentifier,DBInstanceClass,Engine,DBInstanceStatus]' --output table 2>/dev/null || echo "   No RDS instances found"
            fi
            ;;
        "s3")
            count=$(aws s3api list-buckets --no-cli-pager --query 'length(Buckets[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   S3 Buckets:"
                aws s3api list-buckets --no-cli-pager --query 'Buckets[].[Name,CreationDate]' --output table 2>/dev/null || echo "   No S3 buckets found"
            fi
            ;;
        "ecs")
            count=$(aws ecs list-clusters --no-cli-pager --query 'length(clusterArns[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   ECS Clusters:"
                aws ecs list-clusters --no-cli-pager --query 'clusterArns[]' --output table 2>/dev/null || echo "   No ECS clusters found"
            fi
            ;;
        "lambda")
            count=$(aws lambda list-functions --no-cli-pager --query 'length(Functions[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   Lambda Functions:"
                aws lambda list-functions --no-cli-pager --query 'Functions[].[FunctionName,Runtime,State]' --output table 2>/dev/null || echo "   No Lambda functions found"
            fi
            ;;
        "iam")
            count=$(aws iam list-users --no-cli-pager --query 'length(Users[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   IAM Users:"
                aws iam list-users --no-cli-pager --query 'Users[].[UserName,CreateDate]' --output table 2>/dev/null || echo "   No IAM users found"
            fi
            ;;
        "cloudformation")
            count=$(aws cloudformation list-stacks --no-cli-pager --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query 'length(StackSummaries[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   CloudFormation Stacks:"
                aws cloudformation list-stacks --no-cli-pager --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query 'StackSummaries[].[StackName,StackStatus,CreationTime]' --output table 2>/dev/null || echo "   No CloudFormation stacks found"
            fi
            ;;
        "vpc")
            count=$(aws ec2 describe-vpcs --no-cli-pager --query 'length(Vpcs[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   VPCs:"
                aws ec2 describe-vpcs --no-cli-pager --query 'Vpcs[].[VpcId,CidrBlock,State,IsDefault]' --output table 2>/dev/null || echo "   No VPCs found"
            fi
            ;;
        "elb")
            count=$(aws elbv2 describe-load-balancers --no-cli-pager --query 'length(LoadBalancers[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   Load Balancers:"
                aws elbv2 describe-load-balancers --no-cli-pager --query 'LoadBalancers[].[LoadBalancerName,Type,Scheme,State.Code]' --output table 2>/dev/null || echo "   No load balancers found"
            fi
            ;;
        "kms")
            count=$(aws kms list-keys --no-cli-pager --query 'length(Keys[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   KMS Keys:"
                aws kms list-keys --no-cli-pager --query 'Keys[].[KeyId]' --output table 2>/dev/null || echo "   No KMS keys found"
            fi
            ;;
        "cloudtrail")
            count=$(aws cloudtrail describe-trails --no-cli-pager --query 'length(trailList[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   CloudTrail Trails:"
                aws cloudtrail describe-trails --no-cli-pager --query 'trailList[].[Name,S3BucketName,IsLogging]' --output table 2>/dev/null || echo "   No CloudTrail trails found"
            fi
            ;;
        "route53")
            count=$(aws route53 list-hosted-zones --no-cli-pager --query 'length(HostedZones[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   Route53 Hosted Zones:"
                aws route53 list-hosted-zones --no-cli-pager --query 'HostedZones[].[Name,ResourceRecordSetCount]' --output table 2>/dev/null || echo "   No Route53 hosted zones found"
            fi
            ;;
        "security-groups")
            count=$(aws ec2 describe-security-groups --no-cli-pager --query 'length(SecurityGroups[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   Security Groups:"
                aws ec2 describe-security-groups --no-cli-pager --query 'SecurityGroups[].[GroupId,GroupName,VpcId,Description]' --output table 2>/dev/null || echo "   No security groups found"
            fi
            ;;
        "subnets")
            count=$(aws ec2 describe-subnets --no-cli-pager --query 'length(Subnets[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   Subnets:"
                aws ec2 describe-subnets --no-cli-pager --query 'Subnets[].[SubnetId,VpcId,CidrBlock,AvailabilityZone,State]' --output table 2>/dev/null || echo "   No subnets found"
            fi
            ;;
        "route-tables")
            count=$(aws ec2 describe-route-tables --no-cli-pager --query 'length(RouteTables[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   Route Tables:"
                aws ec2 describe-route-tables --no-cli-pager --query 'RouteTables[].[RouteTableId,VpcId,length(Associations[]),length(Routes[])]' --output table 2>/dev/null || echo "   No route tables found"
            fi
            ;;
        "internet-gateways")
            count=$(aws ec2 describe-internet-gateways --no-cli-pager --query 'length(InternetGateways[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   Internet Gateways:"
                aws ec2 describe-internet-gateways --no-cli-pager --query 'InternetGateways[].[InternetGatewayId,State,Attachments[0].VpcId]' --output table 2>/dev/null || echo "   No internet gateways found"
            fi
            ;;
        "nat-gateways")
            count=$(aws ec2 describe-nat-gateways --no-cli-pager --query 'length(NatGateways[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   NAT Gateways:"
                aws ec2 describe-nat-gateways --no-cli-pager --query 'NatGateways[].[NatGatewayId,State,VpcId,SubnetId]' --output table 2>/dev/null || echo "   No NAT gateways found"
            fi
            ;;
        "dhcp-options")
            count=$(aws ec2 describe-dhcp-options --no-cli-pager --query 'length(DhcpOptions[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   DHCP Option Sets:"
                aws ec2 describe-dhcp-options --no-cli-pager --query 'DhcpOptions[].[DhcpOptionsId,Tags[?Key==`Name`].Value|[0]]' --output table 2>/dev/null || echo "   No DHCP option sets found"
            fi
            ;;
        "network-acls")
            count=$(aws ec2 describe-network-acls --no-cli-pager --query 'length(NetworkAcls[])' --output text 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                echo "   Network ACLs:"
                aws ec2 describe-network-acls --no-cli-pager --query 'NetworkAcls[].[NetworkAclId,VpcId,IsDefault,length(Entries[])]' --output table 2>/dev/null || echo "   No network ACLs found"
            fi
            ;;
    esac
    
    echo "   Found: $count"
    echo ""
}

# Set AWS CLI to not use pager
export AWS_PAGER=""

# List resources by category
echo "🖥️  COMPUTE RESOURCES"
echo "===================="
list_resources "ec2" "describe-instances" "EC2 Instances"
list_resources "ecs" "list-clusters" "ECS Clusters"
list_resources "lambda" "list-functions" "Lambda Functions"

echo "🗄️  STORAGE RESOURCES"
echo "===================="
list_resources "s3" "list-buckets" "S3 Buckets"
list_resources "rds" "describe-db-instances" "RDS Instances"

echo "🌐 NETWORKING RESOURCES"
echo "======================"
list_resources "vpc" "describe-vpcs" "VPCs"
list_resources "subnets" "describe-subnets" "Subnets"
list_resources "security-groups" "describe-security-groups" "Security Groups"
list_resources "route-tables" "describe-route-tables" "Route Tables"
list_resources "internet-gateways" "describe-internet-gateways" "Internet Gateways"
list_resources "nat-gateways" "describe-nat-gateways" "NAT Gateways"
list_resources "network-acls" "describe-network-acls" "Network ACLs"
list_resources "dhcp-options" "describe-dhcp-options" "DHCP Option Sets"
list_resources "elb" "describe-load-balancers" "Load Balancers"
list_resources "route53" "list-hosted-zones" "Route53 Hosted Zones"

echo "🔐 SECURITY & IAM RESOURCES"
echo "=========================="
list_resources "iam" "list-users" "IAM Users"
list_resources "kms" "list-keys" "KMS Keys"
list_resources "cloudtrail" "describe-trails" "CloudTrail Trails"

echo "🏗️  INFRASTRUCTURE AS CODE"
echo "========================"
list_resources "cloudformation" "list-stacks" "CloudFormation Stacks"

echo "📊 SUMMARY"
echo "=========="
echo "Resource discovery complete across AWS services"
echo "Note: This shows resources in the current region ($REGION)"
echo "For global services (like S3, IAM), results are account-wide"