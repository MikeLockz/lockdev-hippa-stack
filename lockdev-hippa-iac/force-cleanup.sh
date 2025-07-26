#\!/bin/bash
set -e

export AWS_PROFILE=dev-root
export AWS_DEFAULT_REGION=us-east-1

echo "🚨 FORCE DESTROYING ALL DEV RESOURCES 🚨"
echo "Using AWS Profile: $AWS_PROFILE"
echo "Region: $AWS_DEFAULT_REGION"

# Function to force delete S3 buckets
force_delete_s3_buckets() {
    echo "🔥 Force deleting S3 buckets..."
    for bucket in $(aws s3api list-buckets --query "Buckets[?contains(Name, 'hipaa-dev')].Name" --output text); do
        if [ \! -z "$bucket" ]; then
            echo "Deleting bucket: $bucket"
            aws s3 rb s3://$bucket --force || echo "Bucket $bucket already deleted or inaccessible"
        fi
    done
}

# Function to delete ECS resources
force_delete_ecs() {
    echo "🔥 Force deleting ECS resources..."
    
    # Delete ECS services
    for service in $(aws ecs list-services --cluster hipaa-dev-ecs-cluster --query 'serviceArns[]' --output text 2>/dev/null || echo ""); do
        if [ \! -z "$service" ]; then
            echo "Deleting ECS service: $service"
            aws ecs delete-service --cluster hipaa-dev-ecs-cluster --service $service --force --no-cli-pager
        fi
    done
    
    # Delete ECS cluster
    aws ecs delete-cluster --cluster hipaa-dev-ecs-cluster --no-cli-pager 2>/dev/null || echo "Cluster already deleted"
}

# Function to delete RDS resources
force_delete_rds() {
    echo "🔥 Force deleting RDS resources..."
    
    # Delete RDS instances
    for db in $(aws rds describe-db-instances --query 'DBInstances[?contains(DBInstanceIdentifier, `hipaa-dev`)].DBInstanceIdentifier' --output text 2>/dev/null || echo ""); do
        if [ \! -z "$db" ]; then
            echo "Deleting RDS instance: $db"
            aws rds delete-db-instance --db-instance-identifier $db --skip-final-snapshot --no-cli-pager --delete-automated-backups
        fi
    done
    
    # Delete RDS subnet groups
    for subnet in $(aws rds describe-db-subnet-groups --query 'DBSubnetGroups[?contains(DBSubnetGroupName, `hipaa-dev`)].DBSubnetGroupName' --output text 2>/dev/null || echo ""); do
        if [ \! -z "$subnet" ]; then
            echo "Deleting RDS subnet group: $subnet"
            aws rds delete-db-subnet-group --db-subnet-group-name $subnet --no-cli-pager
        fi
    done
}

# Function to delete ECR repositories
force_delete_ecr() {
    echo "🔥 Force deleting ECR repositories..."
    for repo in $(aws ecr describe-repositories --query 'repositories[?contains(repositoryName, `hipaa-dev`)].repositoryName' --output text 2>/dev/null || echo ""); do
        if [ \! -z "$repo" ]; then
            echo "Deleting ECR repository: $repo"
            aws ecr delete-repository --repository-name $repo --force --no-cli-pager
        fi
    done
}

# Function to delete load balancers
force_delete_elb() {
    echo "🔥 Force deleting load balancers..."
    
    # Delete ALBs
    for alb in $(aws elbv2 describe-load-balancers --query 'LoadBalancers[?contains(LoadBalancerName, `hipaa-dev`)].LoadBalancerArn' --output text 2>/dev/null || echo ""); do
        if [ \! -z "$alb" ]; then
            echo "Deleting ALB: $alb"
            aws elbv2 delete-load-balancer --load-balancer-arn $alb --no-cli-pager
        fi
    done
    
    # Delete target groups
    for tg in $(aws elbv2 describe-target-groups --query 'TargetGroups[?contains(TargetGroupName, `hipaa-dev`)].TargetGroupArn' --output text 2>/dev/null || echo ""); do
        if [ \! -z "$tg" ]; then
            echo "Deleting target group: $tg"
            aws elbv2 delete-target-group --target-group-arn $tg --no-cli-pager
        fi
    done
}

# Function to delete CloudWatch log groups
force_delete_logs() {
    echo "🔥 Force deleting CloudWatch log groups..."
    for log_group in $(aws logs describe-log-groups --query 'logGroups[?contains(logGroupName, `hipaa-dev`)].logGroupName' --output text 2>/dev/null || echo ""); do
        if [ \! -z "$log_group" ]; then
            echo "Deleting log group: $log_group"
            aws logs delete-log-group --log-group-name $log_group --no-cli-pager
        fi
    done
}

# Function to delete IAM resources
force_delete_iam() {
    echo "🔥 Force deleting IAM resources..."
    
    # Delete IAM roles and policies
    for role in $(aws iam list-roles --query 'Roles[?contains(RoleName, `hipaa-dev`)].RoleName' --output text 2>/dev/null || echo ""); do
        if [ \! -z "$role" ]; then
            echo "Deleting IAM role: $role"
            
            # Detach all policies first
            for policy_arn in $(aws iam list-attached-role-policies --role-name $role --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null || echo ""); do
                if [ \! -z "$policy_arn" ]; then
                    aws iam detach-role-policy --role-name $role --policy-arn $policy_arn
                fi
            done
            
            # Delete inline policies
            for policy_name in $(aws iam list-role-policies --role-name $role --query 'PolicyNames[]' --output text 2>/dev/null || echo ""); do
                if [ \! -z "$policy_name" ]; then
                    aws iam delete-role-policy --role-name $role --policy-name $policy_name
                fi
            done
            
            aws iam delete-role --role-name $role --no-cli-pager 2>/dev/null || echo "Role already deleted"
        fi
    done
    
    # Delete IAM policies
    for policy in $(aws iam list-policies --scope Local --query 'Policies[?contains(PolicyName, `hipaa-dev`)].PolicyArn' --output text 2>/dev/null || echo ""); do
        if [ \! -z "$policy" ]; then
            echo "Deleting IAM policy: $policy"
            aws iam delete-policy --policy-arn $policy --no-cli-pager 2>/dev/null || echo "Policy already deleted"
        fi
    done
}

# Function to delete VPC and networking
force_delete_vpc() {
    echo "🔥 Force deleting VPC and networking..."
    
    # Get VPC ID
    vpc_id=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=*hipaa-dev*" --query 'Vpcs[0].VpcId' --output text 2>/dev/null || echo "")
    
    if [ \! -z "$vpc_id" ] && [ "$vpc_id" \!= "None" ]; then
        echo "Deleting VPC: $vpc_id"
        
        # Delete NAT gateways
        for nat in $(aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$vpc_id" --query 'NatGateways[].NatGatewayId' --output text 2>/dev/null || echo ""); do
            if [ \! -z "$nat" ]; then
                echo "Deleting NAT gateway: $nat"
                aws ec2 delete-nat-gateway --nat-gateway-id $nat --no-cli-pager
                aws ec2 wait nat-gateway-deleted --nat-gateway-ids $nat
            fi
        done
        
        # Delete subnets
        for subnet in $(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc_id" --query 'Subnets[].SubnetId' --output text 2>/dev/null || echo ""); do
            if [ \! -z "$subnet" ]; then
                echo "Deleting subnet: $subnet"
                aws ec2 delete-subnet --subnet-id $subnet --no-cli-pager
            fi
        done
        
        # Delete internet gateways
        for igw in $(aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$vpc_id" --query 'InternetGateways[].InternetGatewayId' --output text 2>/dev/null || echo ""); do
            if [ \! -z "$igw" ]; then
                echo "Detaching and deleting IGW: $igw"
                aws ec2 detach-internet-gateway --internet-gateway-id $igw --vpc-id $vpc_id --no-cli-pager
                aws ec2 delete-internet-gateway --internet-gateway-id $igw --no-cli-pager
            fi
        done
        
        # Delete security groups (except default)
        for sg in $(aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$vpc_id" --query 'SecurityGroups[?GroupName\!=`default`].GroupId' --output text 2>/dev/null || echo ""); do
            if [ \! -z "$sg" ]; then
                echo "Deleting security group: $sg"
                aws ec2 delete-security-group --group-id $sg --no-cli-pager 2>/dev/null || echo "SG already deleted"
            fi
        done
        
        # Delete route tables (except main)
        for rt in $(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$vpc_id" --query 'RouteTables[?contains(Tags[].Key, `Name`) && contains(Tags[].Value, `hipaa-dev`)].RouteTableId' --output text 2>/dev/null || echo ""); do
            if [ \! -z "$rt" ]; then
                echo "Deleting route table: $rt"
                aws ec2 delete-route-table --route-table-id $rt --no-cli-pager
            fi
        done
        
        # Finally delete VPC
        aws ec2 delete-vpc --vpc-id $vpc_id --no-cli-pager 2>/dev/null || echo "VPC already deleted"
    fi
}

# Function to delete KMS keys
force_delete_kms() {
    echo "🔥 Force deleting KMS keys..."
    for key_id in $(aws kms list-keys --query 'Keys[?contains(KeyArn, `hipaa-dev`)].KeyId' --output text 2>/dev/null || echo ""); do
        if [ \! -z "$key_id" ]; then
            echo "Scheduling deletion for KMS key: $key_id"
            aws kms schedule-key-deletion --key-id $key_id --pending-window-in-days 7 --no-cli-pager 2>/dev/null || echo "Key already scheduled for deletion"
        fi
    done
}

# Execute all cleanup functions
echo "Starting comprehensive cleanup..."
force_delete_s3_buckets
force_delete_ecs
force_delete_rds
force_delete_ecr
force_delete_elb
force_delete_logs
force_delete_iam
force_delete_vpc
force_delete_kms

echo "✅ Comprehensive cleanup initiated\!"
echo "Note: Some AWS resources may take time to fully delete"
echo "Check AWS Console for remaining resources"
