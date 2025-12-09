# 🚀 AWS Deployment Guide

This guide explains how to deploy the Smart Content Recommendations system to AWS using ECS Fargate, RDS, ElastiCache, and S3.

## 📋 **Prerequisites**

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
3. **Docker** installed locally 
4. **GitHub repository** with secrets configured

## 🏗️ **AWS Architecture**

```
┌─────────────────────────────────────────────────────────────────┐
│                        AWS DEPLOYMENT                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────┐ │
│  │ Internet    │───▶│     ALB      │───▶│   ECS Fargate       │ │
│  │ Users       │    │ (Port 80/443)│    │                     │ │
│  │             │    │              │    │  ┌─────────────────┐ │ │
│  └─────────────┘    └──────────────┘    │  │ FastAPI         │ │ │
│                                         │  │ Container       │ │ │
│                                         │  └─────────────────┘ │ │
│  ┌─────────────┐    ┌──────────────┐    │  ┌─────────────────┐ │ │
│  │   GitHub    │───▶│     ECR      │───▶│  │ Celery Worker   │ │ │
│  │ Actions CI  │    │ (Container   │    │  │ Container       │ │ │
│  │             │    │  Registry)   │    │  └─────────────────┘ │ │
│  └─────────────┘    └──────────────┘    │  ┌─────────────────┐ │ │
│                                         │  │ Celery Beat     │ │ │
│                                         │  │ Container       │ │ │
│                                         │  └─────────────────┘ │ │
│                                         └─────────────────────┘ │
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────┐ │
│  │   Secrets   │    │   RDS        │    │    ElastiCache      │ │
│  │  Manager    │    │ PostgreSQL   │    │      Redis          │ │
│  │             │    │              │    │                     │ │
│  │ Database    │    │ Multi-AZ     │    │   Cluster Mode      │ │
│  │ Redis URLs  │    │ Encrypted    │    │   Encrypted         │ │
│  │ API Keys    │    │              │    │                     │ │
│  └─────────────┘    └──────────────┘    └─────────────────────┘ │
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐                           │
│  │    S3       │    │ CloudWatch   │                           │
│  │   Bucket    │    │    Logs      │                           │
│  │             │    │              │                           │
│  │ File        │    │ Application  │                           │
│  │ Storage     │    │ Monitoring   │                           │
│  │ Encrypted   │    │              │                           │
│  └─────────────┘    └──────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

## 🚦 **Step-by-Step Deployment**

### **Step 1: Create AWS Infrastructure**

Deploy the CloudFormation stack:

```bash
aws cloudformation create-stack \
  --stack-name smart-content-recommendations-infrastructure \
  --template-body file://aws/cloudformation-infrastructure.yml \
  --parameters \
    ParameterKey=Environment,ParameterValue=production \
    ParameterKey=DatabasePassword,ParameterValue=YourSecurePassword123! \
  --capabilities CAPABILITY_NAMED_IAM
```

Wait for stack creation to complete:
```bash
aws cloudformation wait stack-create-complete \
  --stack-name smart-content-recommendations-infrastructure
```

### **Step 2: Create ECR Repository**

```bash
aws ecr create-repository \
  --repository-name smart-content-recommendations \
  --region us-east-1
```

### **Step 3: Configure GitHub Secrets**

Add these secrets to your GitHub repository:

```bash
# AWS Credentials
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=xxx...
AWS_REGION=us-east-1

# Additional configuration if needed
ECR_REGISTRY=123456789012.dkr.ecr.us-east-1.amazonaws.com
```

### **Step 4: Update Task Definition**

Update the ECS task definition with your account details:

```bash
# Replace YOUR_ACCOUNT_ID in aws/ecs-task-definition.json
sed -i 's/YOUR_ACCOUNT_ID/123456789012/g' aws/ecs-task-definition.json
```

Register the task definition:
```bash
aws ecs register-task-definition \
  --cli-input-json file://aws/ecs-task-definition.json
```

### **Step 5: Create ECS Service**

```bash
aws ecs create-service \
  --cluster smart-content-recommendations-cluster \
  --service-name smart-content-recommendations-service \
  --task-definition smart-content-recommendations:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/smart-content-recommendations-tg/xxx,containerName=smart-content-api,containerPort=8000"
```

### **Step 6: Deploy Application**

Push code to main branch to trigger deployment:

```bash
git add .
git commit -m "Deploy to AWS"
git push origin main
```

## 🔧 **Configuration**

### **Environment Variables**

The application uses these AWS-specific configurations:

```bash
# Core AWS Configuration
ENVIRONMENT=production
AWS_REGION=us-east-1
USE_AWS_SECRETS=true
AWS_SECRET_NAME=smart-content-recommendations/prod

# Database (from Secrets Manager)
DATABASE_URL=postgresql+asyncpg://user:pass@rds-endpoint:5432/db
DATABASE_SSL_MODE=require

# Redis (from Secrets Manager)  
REDIS_URL=redis://elasticache-endpoint:6379
REDIS_SSL=true

# S3 Storage
S3_BUCKET_NAME=smart-content-recommendations-storage-123456789012
S3_USE_SSL=true

# CloudWatch Logging
CLOUDWATCH_LOG_GROUP=/aws/ecs/smart-content-recommendations
```

### **Secrets Manager Configuration**

The following secrets are stored in AWS Secrets Manager:

```json
{
  "DATABASE_URL": "postgresql+asyncpg://username:password@rds-endpoint/smart_content",
  "REDIS_URL": "redis://elasticache-endpoint:6379",
  "CELERY_BROKER_URL": "redis://elasticache-endpoint:6379/0", 
  "CELERY_RESULT_BACKEND": "redis://elasticache-endpoint:6379/0",
  "SECRET_KEY": "generated-secret-key",
  "S3_BUCKET_NAME": "your-s3-bucket-name"
}
```

## 🔍 **Monitoring & Logging**

### **CloudWatch Logs**

Application logs are automatically sent to CloudWatch:
- **Log Group**: `/aws/ecs/smart-content-recommendations`
- **Log Streams**: 
  - `api/smart-content-api/[task-id]`
  - `celery-worker/smart-content-celery-worker/[task-id]`
  - `celery-beat/smart-content-celery-beat/[task-id]`

### **Health Checks**

The Application Load Balancer performs health checks:
- **Path**: `/health`
- **Interval**: 30 seconds
- **Timeout**: 5 seconds
- **Healthy threshold**: 2
- **Unhealthy threshold**: 3

## 📊 **Database Management**

### **Running Migrations**

Database migrations are automatically run during deployment via GitHub Actions.

Manual migration:
```bash
# Get running task ARN
TASK_ARN=$(aws ecs list-tasks \
  --cluster smart-content-recommendations-cluster \
  --service-name smart-content-recommendations-service \
  --query 'taskArns[0]' --output text)

# Run migration
aws ecs execute-command \
  --cluster smart-content-recommendations-cluster \
  --task $TASK_ARN \
  --container smart-content-api \
  --interactive \
  --command "python -m alembic upgrade head"
```

### **Database Backup**

RDS automated backups are configured with 7-day retention.

Manual backup:
```bash
aws rds create-db-snapshot \
  --db-instance-identifier smart-content-recommendations-database \
  --db-snapshot-identifier smart-content-manual-backup-$(date +%Y%m%d)
```

## 🔐 **Security Best Practices**

### **Network Security**
- ✅ VPC with public/private subnets
- ✅ Security groups with minimal required access
- ✅ RDS and ElastiCache in private subnets
- ✅ ECS tasks in private subnets with NAT gateway access

### **Data Encryption**
- ✅ RDS encrypted at rest
- ✅ ElastiCache encryption in transit and at rest  
- ✅ S3 server-side encryption (SSE-S3)
- ✅ Secrets Manager for sensitive data

### **Access Control**
- ✅ IAM roles with least privilege principle
- ✅ ECS task roles for AWS service access
- ✅ No hardcoded credentials in code

## 🚨 **Troubleshooting**

### **Common Issues**

**1. ECS Tasks Failing to Start**
```bash
# Check task logs
aws logs get-log-events \
  --log-group-name /aws/ecs/smart-content-recommendations \
  --log-stream-name api/smart-content-api/[task-id]
```

**2. Database Connection Issues**
- Verify RDS security group allows ECS access
- Check database credentials in Secrets Manager
- Ensure RDS is running and accessible

**3. Redis Connection Issues**
- Verify ElastiCache security group configuration
- Check Redis endpoint in Secrets Manager
- Ensure ElastiCache cluster is available

**4. Load Balancer Health Check Failures**
- Verify `/health` endpoint is responding
- Check ECS service target group configuration
- Review application startup logs

### **Monitoring Commands**

```bash
# Check ECS service status
aws ecs describe-services \
  --cluster smart-content-recommendations-cluster \
  --services smart-content-recommendations-service

# View recent logs
aws logs tail /aws/ecs/smart-content-recommendations --follow

# Check ALB target health
aws elbv2 describe-target-health \
  --target-group-arn arn:aws:elasticloadbalancing:region:account:targetgroup/smart-content-recommendations-tg/xxx
```

## 💰 **Cost Optimization**

### **Current Configuration Costs (Estimated)**
- **ECS Fargate**: ~$30-50/month (1 task, 1 vCPU, 2GB RAM)
- **RDS t3.micro**: ~$15-20/month
- **ElastiCache t3.micro**: ~$15-20/month  
- **ALB**: ~$20/month
- **S3**: Variable based on usage
- **Data Transfer**: Variable

### **Cost Optimization Tips**
1. **Use Spot Instances**: Mix Fargate and Fargate Spot
2. **Right-size Resources**: Monitor utilization and adjust
3. **Reserved Instances**: For predictable workloads
4. **S3 Intelligent Tiering**: For file storage
5. **CloudWatch Logs Retention**: Set appropriate retention periods

## 🎯 **Next Steps**

1. **Set up monitoring dashboards** in CloudWatch
2. **Configure alerts** for critical metrics
3. **Implement log aggregation** with ELK or CloudWatch Insights
4. **Add CDN** (CloudFront) for static assets
5. **Implement auto-scaling** based on CPU/memory usage
6. **Set up blue/green deployments** for zero-downtime updates

## 📞 **Support**

For deployment issues:
1. Check CloudWatch logs for error details
2. Review ECS service events and task status
3. Verify security group and network configuration
4. Test database and Redis connectivity manually

Your Smart Content Recommendations system is now running on AWS with enterprise-grade scalability, security, and monitoring! 🚀
