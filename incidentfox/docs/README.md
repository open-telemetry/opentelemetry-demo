# IncidentFox Documentation

Complete documentation for the IncidentFox AI SRE lab environment.

---

## 📚 Documentation Map

Each document covers a specific topic with no overlap (MECE):

### **[coralogix.md](coralogix.md)** - Coralogix Integration
**What it covers:**
- Creating Coralogix API keys + identifying your Coralogix domain
- Installing Coralogix’s Kubernetes integration Helm chart
- Forwarding demo telemetry (fan-out) into Coralogix for AI-agent analysis
- Verification + troubleshooting

**Read this to:** Hook the lab up to Coralogix

---

### **[aws-deployment.md](aws-deployment.md)** - AWS Production Deployment
**What it covers:**
- Deploying to AWS EKS
- Infrastructure components (VPC, EKS, networking)
- Terraform usage and configuration
- Helm deployment
- LoadBalancer setup
- Monitoring and operations
- Troubleshooting deployment issues
- Cost estimates and optimization
- Cleanup procedures

**Read this to:** Deploy the lab to AWS

---

### **[local-setup.md](local-setup.md)** - Local Development
**What it covers:**
- Running demo with Docker Compose
- Running demo with kind/k3d
- Prerequisites for local development
- Accessing services locally
- Troubleshooting local issues

**Read this to:** Run the lab on your laptop

---

### **[secrets.md](secrets.md)** - Secrets Management
**What it covers:**
- What secrets exist (PostgreSQL, Grafana)
- Where secrets are stored (AWS, Terraform state, k8s)
- How secrets are generated (Terraform random_password)
- Two-tier architecture (AWS Secrets Manager + External Secrets Operator)
- IRSA for secure access
- Accessing, updating, and rotating secrets
- Exporting to 1Password
- Security best practices

**Read this to:** Understand and manage secrets

---

### **[agent-integration.md](agent-integration.md)** - Connecting Your AI Agent
**What it covers:**
- Observability endpoints (Prometheus, Jaeger, OpenSearch)
- Example Python code for querying data
- Agent configuration examples
- API query examples
- Feature flag control for remediation
- Testing the integration

**Read this to:** Connect your IncidentFox AI agent

---

### **[incident-scenarios.md](incident-scenarios.md)** - Testing Failures
**What it covers:**
- Catalog of 12 incident scenarios
- How to trigger each scenario
- Expected symptoms and metrics
- Resolution steps
- Multi-service cascade scenarios
- Creating custom scenarios

**Read this to:** Trigger incidents for agent testing

---

## 🚀 Getting Started Paths

### Path 1: Quick Local Test
```
1. README.md (overview)
2. local-setup.md (get it running)
3. incident-scenarios.md (trigger a test)
```

### Path 2: AWS Production Deploy
```
1. README.md (overview)
2. aws-deployment.md (deploy to AWS)
3. secrets.md (understand security)
4. agent-integration.md (connect agent)
```

### Path 3: Understanding the System
```
1. README.md (complete overview + architecture)
2. secrets.md (security model)
3. aws-deployment.md (how deployment works)
```

---

## 🎯 Document Boundaries (MECE)

Each document has a clear scope with no overlap:

| Document | Scope | Excludes |
|----------|-------|----------|
| **aws-deployment.md** | Deploy, operate, troubleshoot AWS | Local setup, agent usage |
| **coralogix.md** | Connect lab telemetry to Coralogix | Other vendors, agent logic |
| **local-setup.md** | Run locally (Docker/k8s) | AWS, production |
| **secrets.md** | Secret management & security | Other topics |
| **agent-integration.md** | Connect external AI agent | Deployment, incidents |
| **incident-scenarios.md** | Trigger & test failures | Architecture, deployment |

---

## 🔍 Quick Reference

**I want to...**

- **Understand the system** → ../README.md (main README)
- **Deploy to AWS** → aws-deployment.md
- **Hook up Coralogix** → coralogix.md
- **Run locally** → local-setup.md
- **Manage passwords** → secrets.md
- **Connect my agent** → agent-integration.md
- **Test incidents** → incident-scenarios.md

---

## 📝 Contributing

When adding documentation:
1. Choose the correct document for your topic
2. Maintain MECE boundaries (no overlap)
3. Link between docs for related concepts
4. Keep practical examples in each doc
5. Update this README when adding new docs

