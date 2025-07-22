# Cost Optimization Guide - Reduce AWS Costs by 30-60%

## 💰 Quick Wins - Save $30-70/month (30-40% reduction)

### **1. Eliminate NAT Gateway** (Save $32/month)
```bash
# Current cost: $32/month
# Optimized cost: $0/month
# Savings: $32/month (24% total savings)

# Replace NAT Gateway with VPC Endpoints
# Edit src/networking/vpc.py to add:
vpc_endpoints = [
    aws.ec2.VpcEndpoint("s3-endpoint",
        vpc_id=vpc.id,
        service_name="com.amazonaws.us-east-1.s3",
        route_table_ids=[private_route_table.id]
    ),
    aws.ec2.VpcEndpoint("ecr-endpoint",
        vpc_id=vpc.id,
        service_name="com.amazonaws.us-east-1.ecr.dkr",
        subnet_ids=[private_subnet_1.id, private_subnet_2.id],
        security_group_ids=[ecs_sg.id]
    )
]
```

### **2. Use Smaller Database Instance** (Save $15-20/month)
```bash
# Current: db.t3.micro ($25-35/month)
# Optimized: db.t3.nano ($10-15/month)
# Savings: $15-20/month

# Edit src/database/rds.py:
instance_class="db.t3.nano"  # Instead of db.t3.micro
allocated_storage=10         # Instead of 20
```

### **3. Optimize CloudWatch Logs** (Save $8-12/month)
```bash
# Current: 30-day retention ($10-15/month)
# Optimized: 7-day retention ($2-3/month)
# Savings: $8-12/month

# Edit src/monitoring/cloudwatch.py:
retention_in_days=7  # Instead of 30
```

### **4. Use Spot Instances for Non-Critical Tasks** (Save $5-10/month)
```bash
# For development/testing environments
# Edit ECS task definition to use Spot capacity
capacity_providers=["FARGATE_SPOT"]
```

## 🏆 Major Optimizations - Save $50-90/month (45-60% reduction)

### **Strategy 1: Serverless Architecture** (Save $50-70/month)
```bash
# Replace ECS Fargate + ALB + RDS with:
# - Lambda functions ($0-5/month)
# - API Gateway ($0-10/month)  
# - DynamoDB ($0-25/month)
# - S3 for static content ($1-3/month)

# Total optimized cost: $25-60/month
# Savings: $87-103/month (60-70% reduction)
```

### **Strategy 2: Development Environment Automation** (Save $80-130/month)
```bash
# Auto-shutdown during off-hours
# Run infrastructure only during business hours (40 hours/week vs 168 hours/week)
# Savings: 76% of compute costs

# Create auto-shutdown script:
#!/bin/bash
# Stop ECS service at 6 PM
aws ecs update-service --cluster hipaa-ecs-cluster --service hipaa-app-service --desired-count 0

# Stop RDS instance at 6 PM  
aws rds stop-db-instance --db-instance-identifier hipaa-postgres-db

# Start everything at 8 AM
aws ecs update-service --cluster hipaa-ecs-cluster --service hipaa-app-service --desired-count 1
aws rds start-db-instance --db-instance-identifier hipaa-postgres-db
```

### **Strategy 3: Multi-Tenant Architecture** (Save $40-60/month)
```bash
# Share resources across multiple clients/applications
# Use database schemas or prefixes to separate data
# Maintain HIPAA compliance with proper access controls

# One infrastructure serves 3-5 small clients
# Per-client cost: $25-45/month instead of $112-163/month
```

## 📊 Detailed Cost Optimization Plan

### **Phase 1: Immediate Changes (Week 1)**
```bash
# 1. Switch to db.t3.nano
pulumi config set db_instance_class db.t3.nano
pulumi config set db_allocated_storage 10

# 2. Reduce log retention
# Edit cloudwatch.py retention_in_days=7

# 3. Remove unused resources
# Comment out GuardDuty for development (keep for production)

# Expected savings: $25-35/month
pulumi up
```

### **Phase 2: Infrastructure Changes (Week 2)**
```bash
# 1. Implement VPC endpoints
# Edit networking/vpc.py to add VPC endpoints

# 2. Optimize ECS task size
# Reduce from 1GB to 512MB RAM
task_definition_memory=512

# 3. Use ECR public gallery for base images
# Reduce ECR storage costs

# Expected additional savings: $35-45/month
pulumi up
```

### **Phase 3: Advanced Optimizations (Week 3-4)**
```bash
# 1. Implement Lambda for low-traffic endpoints
# Move health checks and simple APIs to Lambda

# 2. Add CloudFront CDN
# Cache static content, reduce data transfer costs

# 3. Implement intelligent tiering
# Move old logs to cheaper storage classes

# Expected additional savings: $20-30/month
```

## 💡 Cost-Optimized Configurations

### **Ultra-Budget Configuration** - $45-65/month
```yaml
# 60% cost reduction
Resources:
  - Lambda functions instead of ECS
  - DynamoDB instead of RDS
  - S3 + CloudFront for static content
  - CloudWatch with 3-day retention
  - No NAT Gateway (VPC endpoints only)
  - Spot instances for development

Monthly Cost Breakdown:
  - Lambda: $0-5
  - DynamoDB: $5-25
  - S3 + CloudFront: $5-15
  - CloudWatch: $2-5
  - VPC endpoints: $7-15
  - Other services: $5-10
```

### **Development-Optimized Configuration** - $25-40/month
```yaml
# 75% cost reduction (non-production)
Resources:
  - ECS with Spot instances
  - RDS with stop/start automation
  - 3-day log retention
  - No redundancy/backup
  - Manual scaling only

Monthly Cost Breakdown:
  - ECS Spot: $5-10
  - RDS (partial uptime): $8-15
  - ALB: $22 (required)
  - CloudWatch: $1-3
  - Other services: $2-5
```

### **Production-Optimized Configuration** - $85-110/month
```yaml
# 25% cost reduction (production-safe)
Resources:
  - ECS with right-sized tasks
  - RDS db.t3.small with reserved capacity
  - 14-day log retention
  - VPC endpoints instead of NAT
  - Auto-scaling enabled

Monthly Cost Breakdown:
  - ECS: $15-20
  - RDS: $35-45
  - ALB: $22
  - CloudWatch: $5-8
  - VPC endpoints: $7-15
  - Other services: $8-12
```

## 🛠️ Implementation Scripts

### **Quick Cost Reduction Script**
```bash
#!/bin/bash
# Run this to implement immediate 30% cost savings

echo "Implementing cost optimizations..."

# 1. Update database to nano instance
cd lockdev-hippa-iac
pulumi config set db_instance_class db.t3.nano
pulumi config set db_allocated_storage 10

# 2. Reduce ECS task size
# Edit task definition in src/compute/ecs.py
sed -i 's/memory=1024/memory=512/' src/compute/ecs.py
sed -i 's/cpu=512/cpu=256/' src/compute/ecs.py

# 3. Reduce log retention
sed -i 's/retention_in_days=30/retention_in_days=7/' src/monitoring/cloudwatch.py

# 4. Deploy changes
pulumi up --yes

echo "Cost optimizations applied! Expected savings: $25-35/month"
```

### **Development Auto-Shutdown Script**
```bash
#!/bin/bash
# Schedule with cron for automatic cost savings

# shutdown.sh - Run at 6 PM
aws ecs update-service --cluster hipaa-ecs-cluster --service hipaa-app-service --desired-count 0
aws rds stop-db-instance --db-instance-identifier hipaa-postgres-db
echo "Infrastructure stopped at $(date)"

# startup.sh - Run at 8 AM  
aws rds start-db-instance --db-instance-identifier hipaa-postgres-db
sleep 300  # Wait for DB to start
aws ecs update-service --cluster hipaa-ecs-cluster --service hipaa-app-service --desired-count 1
echo "Infrastructure started at $(date)"

# Add to crontab:
# 0 18 * * 1-5 /path/to/shutdown.sh
# 0 8 * * 1-5 /path/to/startup.sh
```

## 🎯 Optimization by Use Case

### **Development/Testing Environment**
```bash
# Goal: Minimize costs while maintaining functionality
# Target: $25-50/month (70% reduction)

Optimizations:
- Use Spot instances
- Stop resources outside business hours
- Minimal logging and monitoring
- No redundancy or backup
- Shared resources across projects
```

### **Small Production Environment**
```bash
# Goal: Balance cost and reliability
# Target: $75-100/month (35% reduction)

Optimizations:
- Right-size all resources
- Use VPC endpoints
- Optimize logging retention
- Reserved instances for predictable workloads
- Automated scaling
```

### **Multi-Tenant SaaS**
```bash
# Goal: Cost per customer optimization
# Target: $20-40/month per customer

Optimizations:
- Share infrastructure across customers
- Use database schemas for isolation
- Implement usage-based scaling
- Optimize for multiple small workloads
```

## 📈 ROI Analysis

### **Investment vs Savings**
```
Time Investment: 2-8 hours setup
Monthly Savings: $30-90
Annual Savings: $360-1,080
ROI: 4,500-16,200% annually
```

### **Risk Assessment**
```
Low Risk Optimizations:
- Log retention reduction: No impact
- Database right-sizing: Minimal impact
- VPC endpoints: Better security

Medium Risk Optimizations:
- Auto-shutdown: Requires automation
- Spot instances: Potential interruptions
- Resource sharing: Complexity increase

High Risk Optimizations:
- Serverless migration: Architecture change
- Multi-tenancy: Security complexity
- Aggressive downsizing: Performance impact
```

## 🏁 Quick Start Optimization

### **5-Minute Cost Reduction (Save $25/month)**
```bash
# 1. Change database instance
pulumi config set db_instance_class db.t3.nano

# 2. Reduce allocated storage
pulumi config set db_allocated_storage 10

# 3. Apply changes
pulumi up --yes

# Total time: 5 minutes
# Monthly savings: $15-25
```

### **30-Minute Cost Reduction (Save $50/month)**
```bash
# Follow the 5-minute steps above, plus:

# 4. Edit cloudwatch retention
sed -i 's/retention_in_days=30/retention_in_days=7/' src/monitoring/cloudwatch.py

# 5. Reduce ECS task size
sed -i 's/memory=1024/memory=512/' src/compute/ecs.py

# 6. Comment out GuardDuty for development
# Edit src/security/guardduty.py

# 7. Deploy all changes
pulumi up --yes

# Total time: 30 minutes
# Monthly savings: $40-60
```

## Summary - Cost Optimization Options

| Strategy | Time Investment | Monthly Savings | Risk Level |
|----------|----------------|-----------------|------------|
| **Quick wins** | 30 minutes | $30-50 | Low |
| **Infrastructure optimization** | 2-4 hours | $50-70 | Medium |
| **Architecture changes** | 1-2 days | $70-90 | High |
| **Development automation** | 4-8 hours | $80-130 | Low |

**Recommended approach**: Start with quick wins (30% savings in 30 minutes), then implement infrastructure optimizations for an additional 20-30% savings.

**Total potential savings**: 50-75% reduction ($55-120/month → $25-60/month) while maintaining HIPAA compliance!