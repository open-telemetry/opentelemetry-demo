# IncidentFox: AWS Infrastructure (Terraform)

This directory will contain Terraform configurations for deploying the OpenTelemetry Demo to AWS EKS.

## Status

✅ **Implemented** - Production-grade Terraform infrastructure is ready for deployment.

## Planned Components

### Core Infrastructure
- **VPC** - Isolated network with public/private subnets across 2 AZs
- **EKS Cluster** - Kubernetes 1.28+ with managed node groups
- **Node Groups**
  - System nodes (t3.medium) for control plane & monitoring
  - Application nodes (t3.large) for demo services
- **IAM Roles** - Cluster role, node role, IRSA for add-ons

### Networking
- **ALB** - Application Load Balancer for ingress
- **NAT Gateway** - For private subnet internet access
- **Security Groups** - Network access controls

### Storage
- **EBS CSI Driver** - For persistent volumes
- **StorageClass** - gp3 volumes for Prometheus, OpenSearch, Grafana

### Observability (optional)
- **CloudWatch Container Insights** - Cluster-level monitoring
- **VPC Flow Logs** - Network traffic analysis

## Planned Structure

```
terraform/
├── main.tf                  # Main configuration
├── variables.tf             # Input variables
├── outputs.tf               # Cluster connection details
├── versions.tf              # Provider versions
├── vpc.tf                   # VPC and networking
├── eks.tf                   # EKS cluster configuration
├── iam.tf                   # IAM roles and policies
├── alb.tf                   # ALB controller setup
├── ebs-csi.tf              # EBS CSI driver
├── terraform.tfvars.example # Example variable values
└── modules/
    ├── vpc/                # VPC module
    ├── eks/                # EKS module
    └── monitoring/         # CloudWatch, logging
```

## Quick Start

Use the idempotent deployment script:

```bash
# From repo root
cd incidentfox
./scripts/build-all.sh deploy
```

Or manually:

## Usage

```bash
# Clone and configure
cd incidentfox/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your settings

# Initialize
terraform init

# Plan
terraform plan

# Apply
terraform apply

# Get kubeconfig
aws eks update-kubeconfig --name incidentfox-demo --region us-west-2

# Deploy demo (via Helm)
cd ../helm
helm install otel-demo ./opentelemetry-demo -n otel-demo --create-namespace

# Cleanup
cd ../terraform
terraform destroy
```

## Configuration

### Required Variables

- `region` - AWS region (default: us-west-2)
- `cluster_name` - EKS cluster name
- `vpc_cidr` - VPC CIDR block
- `node_instance_type` - EC2 instance type for nodes
- `desired_capacity` - Initial node count

### Optional Variables

- `enable_cloudwatch_insights` - Enable Container Insights
- `enable_vpc_flow_logs` - Enable VPC Flow Logs
- `domain_name` - Custom domain for ALB (optional)
- `ssl_certificate_arn` - ACM certificate ARN (optional)

## Cost Estimation

Estimated monthly cost for 24/7 operation:

- EKS Control Plane: $73/month
- EC2 Instances (t3.large × 3): ~$190/month
- NAT Gateway: ~$32/month
- ALB: ~$16/month
- EBS Storage (100GB): ~$8/month
- **Total: ~$320/month**

Cost optimization:
- Use Spot instances (50-70% savings)
- Stop cluster when not needed
- Use smaller instances for testing
- Enable cluster autoscaling

## Development Roadmap

- [ ] VPC module with public/private subnets
- [ ] EKS cluster with managed node groups
- [ ] IAM roles and policies (IRSA)
- [ ] ALB controller deployment
- [ ] EBS CSI driver
- [ ] Security groups and NACLs
- [ ] CloudWatch integration (optional)
- [ ] Terraform remote state (S3 + DynamoDB)
- [ ] CI/CD integration
- [ ] Auto-scaling configuration
- [ ] Monitoring and alerting
- [ ] Backup and disaster recovery

## Resources

- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [EKS Terraform Module](https://registry.terraform.io/modules/terraform-aws-modules/eks/aws/latest)
- [AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)

## Contributing

When implementing Terraform configs:
1. Follow AWS best practices
2. Use modules for reusability
3. Add comprehensive variable descriptions
4. Include validation for inputs
5. Output useful information (cluster endpoint, etc.)
6. Document cost implications
7. Add examples and usage instructions

## Support

For questions or issues with AWS deployment, contact the SRE team.

