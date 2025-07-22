# Detailed Cost Analysis - Traffic, Storage & Database Capacity

## Cost Estimate Assumptions ($112-163/month)

### **Traffic Assumptions**
- **API Requests**: 100,000-500,000 per month
- **Average requests/day**: 3,300-16,600
- **Peak requests/hour**: 700-2,000
- **Average response time**: 100-300ms
- **Data transfer out**: 10-50 GB/month
- **Concurrent users**: 10-50 simultaneous

### **Database Assumptions**
- **Instance**: db.t3.micro (1 vCPU, 1 GB RAM)
- **Storage**: 20 GB allocated (can auto-scale to 100 GB)
- **Database size**: 5-15 GB actual usage
- **Connections**: 20-50 concurrent
- **Transactions**: 10,000-50,000 per day
- **IOPS**: 100-1,000 per month (baseline)

### **Application Storage**
- **ECR Docker images**: 1-2 GB
- **CloudWatch logs**: 5-20 GB/month
- **CloudTrail logs**: 1-5 GB/month
- **Config snapshots**: 0.5-2 GB/month
- **S3 backup data**: 2-10 GB/month

### **Compute Resources**
- **ECS Tasks**: 1-2 tasks running 24/7
- **vCPU**: 0.5-1 vCPU per task
- **Memory**: 1-2 GB per task
- **Network**: 10-50 GB data transfer/month

## Traffic Scaling Cost Analysis

### **Light Usage** (10,000 requests/month)
```
Monthly Cost: $105-120
- API Requests: 10,000/month (330/day)
- Data Transfer: 2-5 GB/month
- DB Transactions: 1,000-5,000/day
- Concurrent Users: 1-5
- Storage Growth: 1-2 GB/month
```

### **Medium Usage** (100,000 requests/month) ⭐ **BASE ESTIMATE**
```
Monthly Cost: $112-163
- API Requests: 100,000/month (3,300/day)
- Data Transfer: 10-50 GB/month
- DB Transactions: 10,000-50,000/day
- Concurrent Users: 10-50
- Storage Growth: 2-5 GB/month
```

### **High Usage** (1,000,000 requests/month)
```
Monthly Cost: $180-250
- API Requests: 1,000,000/month (33,000/day)
- Data Transfer: 100-300 GB/month
- DB Transactions: 100,000-500,000/day
- Concurrent Users: 50-200
- Storage Growth: 10-20 GB/month
```

### **Enterprise Usage** (10,000,000 requests/month)
```
Monthly Cost: $500-1,200
- API Requests: 10,000,000/month (330,000/day)
- Data Transfer: 1-5 TB/month
- DB Transactions: 1,000,000-5,000,000/day
- Concurrent Users: 200-1,000
- Storage Growth: 50-200 GB/month
```

## Database Scaling Analysis

### **Current Setup: db.t3.micro**
```
Specifications:
- vCPU: 1 (burstable)
- RAM: 1 GB
- Storage: 20-100 GB (auto-scaling)
- Connections: Up to 85 concurrent
- IOPS: 100-3,000 (burstable)

Capacity:
- Records: 1-10 million (depending on size)
- Transactions: 100-1,000 per second
- Suitable for: Small to medium applications
```

### **Upgrade Path: db.t3.small**
```
Monthly Cost: +$25-35 (total: $137-198)
Specifications:
- vCPU: 1 (burstable)
- RAM: 2 GB
- Storage: 20-100 GB (auto-scaling)
- Connections: Up to 170 concurrent
- IOPS: 100-3,000 (burstable)

Capacity:
- Records: 10-50 million
- Transactions: 500-2,000 per second
- Suitable for: Medium applications
```

### **Production Scale: db.t3.medium**
```
Monthly Cost: +$50-70 (total: $162-233)
Specifications:
- vCPU: 2 (burstable)
- RAM: 4 GB
- Storage: 100-500 GB (auto-scaling)
- Connections: Up to 340 concurrent
- IOPS: 100-3,000 (burstable)

Capacity:
- Records: 50-200 million
- Transactions: 1,000-5,000 per second
- Suitable for: Large applications
```

## Storage Scaling Analysis

### **CloudWatch Logs**
```
Light Usage: 1-5 GB/month ($0.50-2.50)
- Application logs: 100-500 MB/month
- Database logs: 200-1,000 MB/month
- Infrastructure logs: 100-500 MB/month

Medium Usage: 5-20 GB/month ($2.50-10) ⭐ BASE ESTIMATE
- Application logs: 2-8 GB/month
- Database logs: 1-5 GB/month
- Infrastructure logs: 2-7 GB/month

High Usage: 20-100 GB/month ($10-50)
- Application logs: 10-50 GB/month
- Database logs: 5-25 GB/month
- Infrastructure logs: 5-25 GB/month
```

### **S3 Storage (Backups & Logs)**
```
Current Estimate: 5-20 GB/month ($0.25-1.00)
- CloudTrail logs: 1-5 GB/month
- Config snapshots: 1-3 GB/month
- Database backups: 2-10 GB/month
- Application backups: 1-2 GB/month

Scaling:
- 6 months: 30-120 GB total
- 1 year: 60-240 GB total
- 2 years: 120-480 GB total
```

## Real-World Usage Examples

### **Small Medical Practice**
```
Monthly Cost: $110-130
- Patients: 500-1,000
- Daily visits: 20-50
- API calls: 50,000/month
- Database: 2-5 GB
- Users: 5-10 concurrent
```

### **Mid-Size Health Tech Startup**
```
Monthly Cost: $140-180
- Patients: 5,000-10,000
- Daily visits: 100-300
- API calls: 200,000/month
- Database: 10-25 GB
- Users: 20-50 concurrent
```

### **Large Healthcare System**
```
Monthly Cost: $300-600
- Patients: 50,000-100,000
- Daily visits: 1,000-3,000
- API calls: 2,000,000/month
- Database: 100-500 GB
- Users: 100-500 concurrent
```

## Cost Breakdown by Resource Usage

### **ECS Fargate Costs**
```
Base Configuration: 0.5 vCPU, 1 GB RAM, 24/7
Monthly Cost: $15-25

Scaling:
- 2 tasks: $30-50/month
- 4 tasks: $60-100/month
- Auto-scaling (2-10 tasks): $30-250/month
```

### **RDS Costs by Storage**
```
20 GB storage: $25-35/month ⭐ BASE
50 GB storage: $30-45/month
100 GB storage: $40-60/month
500 GB storage: $75-120/month
1 TB storage: $125-200/month
```

### **Data Transfer Costs**
```
First 1 GB: Free
Next 10 TB: $0.09/GB
Next 50 TB: $0.085/GB

Monthly Examples:
- 10 GB: $0.81
- 50 GB: $4.41 ⭐ BASE ESTIMATE
- 100 GB: $8.91
- 500 GB: $44.91
```

## Performance Thresholds

### **When to Scale Up**

**Database (RDS):**
- CPU > 80% for 15+ minutes
- Memory > 85% consistently
- Connection count > 70 concurrent
- Storage > 80% full

**Application (ECS):**
- CPU > 80% for 10+ minutes
- Memory > 85% consistently
- Response time > 2 seconds
- Error rate > 5%

**Network:**
- Data transfer > 80% of estimate
- Load balancer target response time > 1 second

## Cost Optimization Recommendations

### **For Current Traffic Level (100K requests/month)**
```
Optimized Configuration:
- Keep db.t3.micro: $25-35/month
- Use 1 ECS task: $15-20/month
- 7-day log retention: $2-5/month
- Total optimized: $95-125/month
Savings: $17-38/month (15-23%)
```

### **For Growth (1M requests/month)**
```
Recommended Configuration:
- Upgrade to db.t3.small: $50-70/month
- Use 2-3 ECS tasks: $30-60/month
- 30-day log retention: $5-15/month
- Total recommended: $150-220/month
Additional cost: $38-57/month
```

## Summary

**Base Estimate ($112-163/month) includes:**

| Resource | Capacity | Usage Level |
|----------|----------|-------------|
| **API Requests** | 100,000-500,000/month | Light-Medium |
| **Database** | 1 GB RAM, 20 GB storage | Small-Medium |
| **Data Transfer** | 10-50 GB/month | Typical web app |
| **Storage** | 10-30 GB total | Standard logs/backups |
| **Concurrent Users** | 10-50 users | Small business |

This baseline supports most small to medium healthcare applications. Costs scale predictably with usage, typically doubling every 10x increase in traffic.