# AWS Production Deployment Architecture & Implementation Plan for View Dezider

This document presents a production-ready, secure, highly available, and cost-optimized AWS deployment architecture tailored to the **View Dezider** application stack (Expo React Native Frontend, FastAPI Backend, MongoDB Database).

> [!NOTE]
> **NAT Gateway Elimination (Cost Optimized)**: As requested, this architecture eliminates expensive NAT Gateways ($32/month per gateway + hourly processing fees) across all environments. Instead, it utilizes **ECS Fargate in Public Subnets with strict Security Groups (ALB-only ingress)** combined with **free S3 Gateway Endpoints** and direct Internet Gateway outbound routing.

---

## 1. Architectural Overview & Service Selection

Based on the code analysis (`backend/server.py`, `backend/Dockerfile`, `deploy/docker-compose.yml`, `frontend/package.json`), the application consists of an **Expo web/mobile frontend**, a **FastAPI backend** running async Python with heavy integrations (LLMs, OCR/MediaPipe, Razorpay, PDF generation, S3 media uploads), and a **MongoDB database**.

### Service Recommendations

| Layer | AWS Service / Solution | Rationale & Configuration |
| :--- | :--- | :--- |
| **Frontend (Web SPA)** | **AWS CloudFront + Amazon S3** | S3 hosts static Expo web exports (`npx expo export --platform web`). CloudFront provides global CDN edge caching, sub-100ms latency, free SSL via ACM, and custom SPA routing (redirecting 404/403 to `index.html`). |
| **Frontend (Mobile)** | **Expo Application Services (EAS) / App Stores** | iOS/Android app binaries distributed via Apple App Store / Google Play Store, pointing to environment API domain (`api.dezider.ai` / `staging-api.dezider.ai`). |
| **Backend Container Service** | **Amazon ECS on AWS Fargate** | Serverless container orchestration for the FastAPI Docker container (`backend/Dockerfile`). Deployed with `AssignPublicIp: ENABLED` in Public Subnets. Outbound internet access for LLMs/Razorpay via Internet Gateway (Zero NAT cost). Ingress restricted strictly to ALB Security Group. |
| **Load Balancing & Routing** | **AWS Application Load Balancer (ALB)** | Terminates TLS (HTTPS), routes traffic across ECS Fargate tasks across Availability Zones, and executes health checks (`/api/health/live`). |
| **Database** | **MongoDB Atlas on AWS (Primary)** *(or AWS DocumentDB)* | **Primary Recommendation**: Managed MongoDB Atlas running inside AWS region accessed securely via MongoDB Atlas IP Whitelisting (ECS Elastic IPs / Fargate Public IPs) or AWS PrivateLink.<br>**AWS Native Alternative**: **Amazon DocumentDB** (MongoDB-compatible) Multi-AZ cluster. |
| **Container Registry** | **Amazon ECR (Elastic Container Registry)** | Private Docker registry with image vulnerability scanning on push and IAM-based access control. |
| **Secrets & Config** | **AWS Secrets Manager + Parameter Store** | Stores sensitive environment variables (`MONGO_URL`, `OPENAI_API_KEY`, `RAZORPAY_SECRET`, `JWT_SECRET`). ECS injects secrets directly into container env vars at launch via IAM. |
| **Object Storage** | **Amazon S3 (Media & Files) + VPC Gateway Endpoint** | Stores user-uploaded files, generated PDFs, and media assets. Configured with a **Free S3 VPC Gateway Endpoint** so container-to-S3 traffic stays within the AWS internal network without touching the internet. |
| **Security & WAF** | **AWS WAF + AWS Shield Standard** | WAF attached to CloudFront and ALB to enforce rate limits, block OWASP Top 10 vulnerabilities (SQLi, XSS), and prevent DDoS attacks. |
| **DNS & SSL** | **Amazon Route 53 + AWS Certificate Manager (ACM)** | Route 53 manages DNS routing with latency-based records. ACM provides auto-renewed, free SSL/TLS certificates. |
| **Monitoring & Logs** | **Amazon CloudWatch + AWS X-Ray** | CloudWatch Logs aggregates container stdout/stderr. CloudWatch Metrics & Alarms monitor ALB response times, 5xx rates, and ECS resource usage. |

---

## 2. Multi-Environment Architecture Strategy & Zero-NAT Networking

To enforce complete isolation and zero NAT gateway costs, a **Multi-Account AWS Strategy** using **AWS Organizations** is implemented.

```
                                  ┌─────────────────────────────────────────┐
                                  │      AWS Organizations (Management)     │
                                  └────────────────────┬────────────────────┘
                                                       │
         ┌─────────────────────────────────────────────┼─────────────────────────────────────────────┐
         ▼                                             ▼                                             ▼
┌─────────────────────────┐               ┌─────────────────────────┐               ┌─────────────────────────┐
│   Development Account   │               │     Staging Account     │               │   Production Account    │
│  (Single AZ / Low Cost) │               │  (Mirror of Production) │               │   (Multi-AZ / High Availability) │
└─────────────────────────┘               └─────────────────────────┘               └─────────────────────────┘
```

### Zero-NAT Gateway Network Topology

```
                                   [ Route 53 DNS ]
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   │                                             │
      [ CloudFront CDN (SPA Frontend) ]             [ AWS WAF + ALB (API Gateway) ]
                   │                                             │
          (S3 Static Assets)                             │ (HTTPS Port 443)
                                                         │
                                               ┌─────────┴─────────┐
                                               │ Public Subnets    │
                                               │ (Multi-AZ + IGW)  │
                                               │                   │
                                               │  [ ECS Fargate ]  │ ──(Direct Outbound via IGW)──> [ OpenAI / Razorpay / External APIs ]
                                               │   (FastAPI Tasks) │
                                               └─────────┬─────────┘
                                                         │ ──(Free S3 VPC Gateway Endpoint)──> [ S3 Media Uploads ]
                                                         │
                                            [ MongoDB Atlas Cluster ]
                                              (Whitelisted Task IPs / PrivateLink)
```

### Security Isolation in Zero-NAT Setup
- **Strict Security Group Ingress**: The ECS Fargate tasks do **NOT** accept inbound traffic from the internet, even though they sit in public subnets. Their Security Group explicitly allows ingress **ONLY on port 8001 from the ALB's Security Group**. Direct internet attempts to reach the tasks are instantly dropped at the hypervisor level.
- **Direct Outbound via IGW**: Outbound traffic for OpenAI LLM calls, Razorpay payment APIs, WhatsApp OTP, and external Webhooks flows directly through the Internet Gateway ($0/hour cost).
- **Free S3 VPC Endpoint**: Communication with S3 bucket (`dezider-uploads-prod`) routes through an AWS VPC Gateway Endpoint attached to the route table ($0/hour cost, unlimited bandwidth).

---

## 3. Environment Specifications & Scaling

1. **Development (`dev.dezider.ai` / `dev-api.dezider.ai`)**:
   - **Compute**: ECS Fargate (1 Task: 0.5 vCPU, 1 GB RAM).
   - **Networking**: 1 Public Subnet + Internet Gateway + S3 Gateway Endpoint (**$0 NAT Cost**).
   - **Database**: MongoDB Atlas M10 instance or shared dev database cluster.
   - **Deployment**: Automatic deployment on push to `develop` / `dev` branch.

2. **Staging (`staging.dezider.ai` / `staging-api.dezider.ai`)**:
   - **Compute**: ECS Fargate (1-2 Tasks across 2 AZs: 1 vCPU, 2 GB RAM).
   - **Networking**: 2 Multi-AZ Public Subnets + Internet Gateway + S3 Gateway Endpoint (**$0 NAT Cost**).
   - **Database**: MongoDB Atlas M20 Multi-AZ cluster (isolated dataset with production schema).
   - **Deployment**: Automatic deployment on push to `staging` branch.

3. **Production (`dezider.ai` / `api.dezider.ai`)**:
   - **Compute**: ECS Fargate Auto-Scaling (Min: 2 Tasks, Max: 10+ Tasks across 3 AZs: 2 vCPU, 4 GB RAM). Auto-scaling policy based on Target Request Count (>500 req/min per task) and CPU Utilization (>70%).
   - **Networking**: 3 Multi-AZ Public Subnets + Internet Gateway + S3 Gateway Endpoint (**$0 NAT Cost**).
   - **Database**: MongoDB Atlas M30+ High-Availability Cluster with automated 3-node replication across 3 AZs, Continuous Cloud Backups, and Point-In-Time Recovery (PITR).
   - **Deployment**: Zero-downtime rolling deployment triggered by Git release tag or manual approval gate.

---

## 4. Implementation & Provisioning Strategy

### Phase 1: Infrastructure as Code (IaC via Terraform)

All AWS infrastructure will be defined declaratively in Terraform modules inside an `/infra` directory:

1. **VPC Module (Zero-NAT Architecture)**:
   - Public Subnets across Availability Zones (for ALB and ECS Tasks).
   - Internet Gateway (IGW) attached to VPC route tables.
   - S3 VPC Gateway Endpoint attached to route tables ($0/mo cost).
   - **No NAT Gateways or NAT Instances provisioned**.
2. **IAM & Security Groups**:
   - `EcsTaskExecutionRole`: Grants ECS permission to pull ECR images and fetch secrets from Secrets Manager.
   - `EcsTaskRole`: Grants FastAPI permission to access specific S3 buckets (`dezider-uploads-prod`) and KMS keys.
   - `GitHubActionsRole`: OIDC role enabling keyless deployment from GitHub Actions pipelines.
   - Security Groups: `ALB SG` allows 80/443 from anywhere -> `ECS SG` allows port 8001 ONLY from `ALB SG`.
3. **Secrets Management**:
   - Create Secrets Manager secret `/dezider/prod/backend-env` containing `MONGO_URL`, `OPENAI_API_KEY`, `RAZORPAY_SECRET`, `JWT_SECRET`, etc.

### Phase 2: Backend Containerization & ECS Deployment

1. **Production Dockerfile Enhancements**:
   - Utilize multi-stage build as currently configured in `backend/Dockerfile`.
   - Add non-root `appuser` execution for security compliance.
   - Configure health check endpoint (`GET /api/health/live`) with 30s interval, 5s timeout.
2. **ECS Task Definition & Service Configuration**:
   - Task Definition registered with `awslogs` driver sending logs to CloudWatch Log Group `/ecs/dezider-backend`.
   - `networkMode: awsvpc` with `assign_public_ip = true` in ECS Service network configuration.
   - Secret mapping: Load secrets directly from Secrets Manager into container env variables.
   - ECS Service setup with ALB Target Group, deregistration delay (30s), and rolling update deployment strategy (`minimumHealthyPercent=100`, `maximumPercent=200`).

### Phase 3: Frontend Deployment Pipeline

1. **Expo Web Build**:
   - Execute `npx expo export --platform web` producing optimized static web assets in `dist/`.
2. **S3 & CloudFront Hosting**:
   - S3 Bucket `dezider-frontend-prod` configured with Private access.
   - CloudFront Origin Access Control (OAC) created to restrict S3 bucket access strictly to CloudFront.
   - CloudFront Custom Error Pages: Map HTTP 404 & 403 errors to HTTP 200 `/index.html` for single-page app (SPA) client-side routing.

---

## 5. Security, High Availability, Monitoring & Disaster Recovery

### Security Best Practices
- **Network Ingress Protection**: Despite sitting in public subnets for zero-NAT outbound routing, ECS tasks block ALL public ingress. Only traffic routed through the ALB (which is protected by AWS WAF) is permitted.
- **Data Protection & Encryption**: All S3 buckets enforced with Server-Side Encryption (SSE-KMS). TLS 1.3 enforced on CloudFront & ALB (HSTS enabled).
- **DPDP / Compliance**: Sensitive PII encrypted at rest using AES-256 via KMS keys, aligned with `ViewDezider_Data_Security_Declaration.md`.
- **WAF Rule Sets**: Managed AWS WAF rules including Common Rule Set (CRS), SQL Injection Rule Set, Known Bad Inputs Rule Set, and Rate-based rule (100 req/5 min per IP).

### High Availability & Resiliency
- **Multi-AZ Deployment**: ECS tasks distributed across 2 (Staging) or 3 (Prod) Availability Zones.
- **Auto-Healing**: ECS Service automatically replaces unhealthy containers if health check `/api/health/live` fails 3 consecutive times.
- **Database HA**: MongoDB Atlas Multi-AZ 3-node replica set with automatic primary failover (<30 seconds).

### Monitoring & Observability
- **Structured Log Parsing**: FastAPI outputs structured JSON logs. CloudWatch Insights queries enable real-time tracking of slow queries (`elapsed_ms > 1500`).
- **CloudWatch Alarms**:
  - `High5xxErrors`: Triggered if ALB 5xx HTTP response rate > 1% over 5 minutes.
  - `HighCpuUtilization`: Triggered if ECS cluster CPU > 85% over 10 minutes.
  - `DatabaseStorageLow`: Triggered if DB disk space < 15%.
  - Notifications routed via Amazon SNS to Slack devops channel and PagerDuty.

---

## 6. Revised AWS Infrastructure Cost Breakdown (Zero NAT Gateway)

By eliminating NAT Gateways across all 3 environments, **you save ~$32–$96/month in base charges plus data processing fees**:

| Environment | Service Component | Configuration / Specification | Estimated Monthly Cost (USD) |
| :--- | :--- | :--- | :--- |
| **Dev Environment** | ECS Fargate | 1 Task (0.5 vCPU, 1 GB RAM) | ~$15 / mo |
| | ALB & CloudFront | Shared ALB rule + CloudFront Free Tier | ~$10 / mo |
| | MongoDB Atlas | M10 Cluster (General Purpose) | ~$60 / mo |
| | Networking & Storage | **Zero NAT Gateway ($0)** + IGW + S3 Dev storage | ~$5 / mo |
| | **Dev Subtotal** | | **~$90 / month** *(was $115)* |
| **Staging Environment**| ECS Fargate | 2 Tasks (1 vCPU, 2 GB RAM) | ~$45 / mo |
| | ALB & CloudFront | Shared ALB + CloudFront CDN | ~$15 / mo |
| | MongoDB Atlas | M20 Cluster (High Performance) | ~$140 / mo |
| | Networking & Storage | **Zero NAT Gateway ($0)** + IGW + Staging S3 Storage | ~$10 / mo |
| | **Staging Subtotal** | | **~$210 / month** *(was $265)* |
| **Production Environment**| ECS Fargate | Auto-scaling 2–6 Tasks (2 vCPU, 4 GB RAM) | ~$160 – $280 / mo |
| | ALB + AWS WAF | Dedicated ALB + WAF Managed Rules | ~$45 / mo |
| | CloudFront + S3 | Global CDN + Multi-region S3 Storage | ~$35 / mo |
| | MongoDB Atlas | M30 Multi-AZ Cluster (3-Node Replica Set, PITR) | ~$350 / mo |
| | Networking & Logs | **Zero NAT Gateway ($0)** + CloudWatch Logs, KMS, Secrets Mgr | ~$25 / mo |
| | **Production Subtotal**| | **~$615 – $735 / month** *(was $800)* |
| **TOTAL ESTIMATED COST**| **All 3 Environments (Dev + Staging + Prod)** | | **~$915 – $1,035 / month** *(Save ~$150+/mo)* |

---

## 7. Verification & Rollout Checklist

- [ ] **Phase 1 Infrastructure**: Run `terraform apply` for Dev, Staging, and Production VPCs (without NAT Gateways) and Security Groups.
- [ ] **Security Group Verification**: Verify that ECS Fargate tasks accept port 8001 traffic ONLY from ALB SG.
- [ ] **S3 Endpoint Verification**: Verify FastAPI S3 calls travel over the free S3 VPC Gateway Endpoint.
- [ ] **Database Connectivity**: Verify MongoDB Atlas connectivity from ECS tasks over Internet Gateway or PrivateLink.
- [ ] **Health Checks**: Confirm ALB target group reports `/api/health/live` as `HEALTHY`.
- [ ] **CI/CD Pipeline**: Test end-to-end deployment pipeline via GitHub Actions.
