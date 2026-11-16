# CareFlow - Clinic Appointment Management Platform

CareFlow is a containerized clinic appointment and management demonstration platform developed using Python, FastAPI, HTML, CSS, JavaScript, Docker, and AWS technologies. It provides separate workflows for patients, doctors, and administrators.

> **Important:** CareFlow is an educational demonstration project. Use synthetic data only. It is not intended for real patient records, medical diagnosis, treatment, or emergency care.

## 1. Project Overview

CareFlow aims to simplify basic clinic appointment management by providing a centralized platform for patients, doctors, and administrators.

The project demonstrates backend API development, role-based authentication, database integration, containerization, asynchronous event processing, and an AWS cloud deployment.

### Project Objectives

- Provide separate role-based access for patients, doctors, and administrators.
- Allow patients to browse available doctors and request appointments.
- Allow patients to view and cancel eligible appointments.
- Allow doctors to view assigned appointments and update appointment statuses.
- Allow administrators to manage doctor profiles and accounts.
- Provide secure authentication using JSON Web Tokens (JWT).
- Implement database persistence using DynamoDB.
- Containerize the frontend and backend using Docker.
- Demonstrate asynchronous event processing using an outbox pattern.
- Prepare an infrastructure design using AWS services and DevOps tools.

## 2. Application Features

| Module | Features |
|---|---|
| Authentication | User registration, login, JWT-based authentication |
| Patient Dashboard | Browse doctors, request appointments, view appointment history, cancel eligible appointments |
| Doctor Dashboard | View assigned appointments and update appointment status |
| Admin Dashboard | Manage doctor profiles, provision doctor accounts, view all appointments |
| REST API | FastAPI endpoints for authentication, doctors, appointments, and health checks |
| Database | In-memory and DynamoDB repository implementations |
| Event Processing | Transactional outbox, event dispatcher, and Lambda-compatible consumer |
| Frontend | HTML, CSS, and JavaScript |
| Web Server | Apache HTTP Server with API reverse proxy |
| Containerization | Separate backend and frontend Docker containers |

## 3. Technology Stack

### Application Technologies

| Technology | Purpose |
|---|---|
| Python 3.12 | Backend development |
| FastAPI | REST API development |
| Uvicorn | ASGI application server |
| HTML | Frontend structure |
| CSS | Frontend styling |
| JavaScript | Frontend functionality |
| Amazon DynamoDB | Database persistence |
| Apache HTTP Server | Frontend hosting and reverse proxy |
| Docker | Application containerization |
| Docker Compose | Multi-container deployment |
| Git | Version control |
| GitHub | Source code repository |
| AWS CLI | AWS command-line management |

### DevOps Tools

The following tools form the planned DevOps toolset. Tools marked as planned have not yet been fully integrated into the project.

| Tool | Purpose | Status |
|---|---|---|
| Git | Version control | Used |
| GitHub | Source code hosting | Configured |
| Python | Backend development and testing | Used |
| Docker | Build and run containers | Implemented and tested |
| Docker Compose | Manage application containers | Implemented and tested |
| Apache HTTP Server | Serve frontend and proxy API requests | Implemented and tested |
| AWS CLI | Manage and verify AWS resources | Used |
| GitHub Actions | CI/CD automation | Planned |
| Trivy | Container vulnerability scanning | Planned |
| Ansible | EC2 configuration and deployment automation | Planned |
| Kubernetes (Kind) | Local Kubernetes environment | Planned |
| Helm | Kubernetes package management | Planned |
| Prometheus | Metrics collection | Planned |
| Grafana | Monitoring dashboards | Planned |
| Loki | Log aggregation | Planned |
| CloudFormation | Infrastructure as code | Used; AWS stacks deployed |

## 4. AWS Cloud Architecture

CareFlow has been deployed to AWS in the **us-east-2 (Ohio)** region. The deployment uses CloudFormation, EC2, DynamoDB, SQS, Lambda, S3, CloudWatch, Systems Manager, and IAM.

### AWS Services

| No. | AWS Service | Purpose | Current Status |
|---:|---|---|---|
| 1 | Amazon EC2 | Host the containerized CareFlow application | Deployed; t3.micro instance |
| 2 | Amazon VPC | Provide network isolation | Deployed |
| 3 | Amazon S3 | Store the Lambda deployment artefact | Deployed; private bucket |
| 4 | Amazon DynamoDB | Store users, doctors, appointments, and event records | Deployed and integrated |
| 5 | Amazon SQS | Queue appointment events | Deployed; event delivery verified |
| 6 | AWS Lambda | Process queued appointment events | Deployed; successful invocation verified |
| 7 | Amazon SNS | Notification delivery | Planned |
| 8 | Amazon EventBridge | Event routing and scheduled automation | Planned |
| 9 | Amazon CloudWatch | Lambda execution logs and monitoring | Deployed; logs verified |
| 10 | AWS CloudTrail | Record AWS account activity | Not separately configured for this project |
| 11 | AWS Systems Manager | Secure EC2 administration and port forwarding | Deployed and used |
| 12 | AWS CloudFormation | Provision AWS infrastructure as code | Deployed; multiple stacks created |

IAM is used for service roles and access permissions and is excluded from the 12-service count.

### Deployed CloudFormation Stacks

| Stack | Purpose |
|---|---|
| careflow-dynamodb | DynamoDB tables |
| careflow-sqs | Main event queue and dead-letter queue |
| careflow-artifacts | Private Lambda artefact bucket |
| careflow-lambda | Lambda function and SQS event-source mapping |
| careflow-ec2 | EC2 application host and associated networking |

### Deployment and Access

- AWS region: `us-east-2`
- EC2 instance type: `t3.micro`
- Application: Docker Compose with Apache frontend and FastAPI backend
- Database: Amazon DynamoDB
- Event transport: Amazon SQS
- Event consumer: AWS Lambda
- Administration: AWS Systems Manager Session Manager

The EC2 security group has no inbound rules. The application was accessed through an SSM port-forwarding session rather than opening public application ports.

AWS resource usage can incur charges depending on service usage, account eligibility, and current pricing. Review AWS Billing and Cost Explorer regularly.
## 5. Application Architecture

CareFlow follows a layered application structure:

1. **Frontend:** Provides the patient, doctor, and administrator interfaces.
2. **Web server:** Apache serves frontend files and forwards API requests.
3. **Backend:** FastAPI handles authentication, authorization, validation, and application operations.
4. **Repository layer:** Provides storage interfaces and implementations.
5. **Database:** DynamoDB stores application records in the AWS deployment.
6. **Event processing:** An outbox worker dispatches appointment events to SQS, where Lambda processes them.

### Appointment Event Processing

CareFlow implements an asynchronous event-processing design using a transactional outbox pattern.

- Appointment creation and supported status changes can write an outbox event in the same DynamoDB transaction as the appointment update.
- The outbox worker claims pending events and sends them to Amazon SQS.
- The SQS event-source mapping invokes the `CareFlow-EventProcessor` Lambda function.
- The consumer validates event records and uses the processed-events repository to prevent duplicate processing.
- Failed records can be retried through SQS partial-batch failure handling.

**AWS verification:** The deployed SQS queue, Lambda function, and event-source mapping were checked. A demonstration appointment event was recorded in the outbox and processed-events tables. The queue and dead-letter queue had no messages visible or in flight at the time of verification. CloudWatch showed a successful Lambda invocation with no exception in the supplied execution logs.

This verifies a demonstration event-processing flow; it does not establish production-scale reliability or suitability for real healthcare workloads.
## 6. Repository Structure

```text
CareFlow/
Ã¢â€â€š
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ app/
Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ backend/
Ã¢â€â€š   Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ careflow_api/
Ã¢â€â€š   Ã¢â€â€š   Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ routers/
Ã¢â€â€š   Ã¢â€â€š   Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ main.py
Ã¢â€â€š   Ã¢â€â€š   Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ storage.py
Ã¢â€â€š   Ã¢â€â€š   Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ dynamodb_repositories.py
Ã¢â€â€š   Ã¢â€â€š   Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ dynamodb_tables.py
Ã¢â€â€š   Ã¢â€â€š   Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ outbox_dispatcher.py
Ã¢â€â€š   Ã¢â€â€š   Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ outbox_worker.py
Ã¢â€â€š   Ã¢â€â€š   Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ lambda_handler.py
Ã¢â€â€š   Ã¢â€â€š   Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ event_processor.py
Ã¢â€â€š   Ã¢â€â€š   Ã¢â€â€š
Ã¢â€â€š   Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ tests/
Ã¢â€â€š   Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ requirements.txt
Ã¢â€â€š   Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ requirements-runtime.txt
Ã¢â€â€š   Ã¢â€â€š
Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ frontend/
Ã¢â€â€š       Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ apache/
Ã¢â€â€š       Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ httpd.conf
Ã¢â€â€š       Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ app.js
Ã¢â€â€š       Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ index.html
Ã¢â€â€š       Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ styles.css
Ã¢â€â€š       Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ Dockerfile
Ã¢â€â€š
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ docs/
Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ architecture.md
Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ aws-services.md
Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ devops-tools.md
Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ local-setup.md
Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ testing.md
Ã¢â€â€š
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ tools/
Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ dynamodb-local/
Ã¢â€â€š
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ .env.example
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ .gitignore
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ Dockerfile
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ compose.yaml
Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ README.md
```

## 7. Project Documentation

Detailed project documentation is available in the `docs` directory.

| Document | Description |
|---|---|
| [System Architecture](docs/architecture.md) | Application components and architecture |
| [AWS Services](docs/aws-services.md) | Purpose and implementation status of the 12 AWS services |
| [DevOps Tools](docs/devops-tools.md) | DevOps technology stack and automation plans |
| [Local Setup Guide](docs/local-setup.md) | Prerequisites and instructions for running CareFlow locally |
| [Testing Guide](docs/testing.md) | Automated testing and local validation procedures |

## 8. Local Development and Testing

### Prerequisites

- Windows and PowerShell
- Python 3.12
- Git
- Java for the local DynamoDB Local process
- Docker Desktop for container deployment

### Backend Tests

Run the backend test suite from the project root:

```powershell
cd C:\dev\CareFlow

.\.venv\Scripts\python.exe -m pytest .\app\backend\tests -v
```

The latest recorded full backend test run completed with **224 passed** on 13 November 2026.

Run the command again to verify the current code.

### Local Development Addresses

The tested local development setup uses:

| Component | Address |
|---|---|
| Frontend development server | http://127.0.0.1:5500 |
| Backend API | http://127.0.0.1:8001 |
| DynamoDB Local | http://127.0.0.1:8000 |

### API Health Endpoints

| Endpoint | Purpose |
|---|---|
| `/health/live` | Check whether the API is running |
| `/health/ready` | Check application and database readiness |
| `/docs` | Open interactive FastAPI API documentation |

## 9. Docker Deployment

CareFlow uses separate Docker containers for the backend and frontend.

### Docker Architecture

| Component | Configuration |
|---|---|
| Frontend | Apache HTTP Server container |
| Frontend address | http://localhost:8080 |
| Backend | FastAPI container |
| Backend internal port | 8000 |
| Database | Separate DynamoDB Local process |
| Database host port | 8002 |
| Backend database endpoint | `http://host.docker.internal:8002` |

Apache serves the frontend and proxies API requests to the backend container.

### Start the Application

The Docker Compose configuration requires the following environment variables:

- `CARE_FLOW_BOOTSTRAP_ADMIN_PASSWORD`
- `CARE_FLOW_JWT_SECRET`

Supply these securely through the local environment or an appropriate ignored environment file. Never commit their values.

Run:

```powershell
cd C:\dev\CareFlow

docker compose build
docker compose up -d
docker compose ps
```

### Verify the Application

Check the health endpoints:

```powershell
Invoke-RestMethod http://localhost:8080/health/live

Invoke-RestMethod http://localhost:8080/health/ready
```

Open the frontend in a browser:

```text
http://localhost:8080
```

### Stop the Containers

When you intentionally want to stop the Docker application:

```powershell
docker compose down
```

This stops the Compose containers but does not automatically stop the separate DynamoDB Local Java process.

**Important:** The Docker DynamoDB Local instance uses in-memory storage. Its data is lost when that Java process stops.

## 10. Security Considerations

- Use synthetic demonstration data only.
- Never commit `.env`, passwords, JWT secrets, or AWS credentials.
- Use least-privilege IAM policies for AWS resources.
- Do not expose local DynamoDB or development API ports publicly.
- Configure HTTPS before making the application publicly accessible.
- Use secure secret management for production deployments.
- Review container images and dependencies for vulnerabilities.
- Review AWS costs, quotas, and free-tier eligibility before provisioning resources.

## 11. Project Status

### Completed and Verified

- Role-based patient, doctor, and administrator workflows.
- User registration and authentication.
- Doctor profile and account management.
- Appointment creation, viewing, cancellation, and status updates.
- FastAPI backend and browser-based frontend.
- In-memory and DynamoDB repository implementations.
- DynamoDB transactional outbox and processed-events repositories.
- Outbox dispatcher and worker.
- Lambda-compatible event consumer.
- Backend automated test suite: latest recorded run **224 passed**.
- Dockerfiles for backend and frontend.
- Apache reverse proxy configuration.
- Docker Compose deployment.
- Local and Docker application testing.
- AWS CloudFormation infrastructure templates.
- AWS DynamoDB tables deployed.
- AWS SQS main queue and dead-letter queue deployed.
- AWS Lambda function and SQS event-source mapping deployed.
- Private S3 artefact bucket deployed.
- EC2 application host deployed.
- Secure EC2 administration using AWS Systems Manager.
- Successful demonstration appointment event processing verified through DynamoDB, SQS, and CloudWatch logs.
- Project documentation.

### Optional Improvements / Not Implemented

- GitHub Actions CI/CD pipeline.
- Trivy container vulnerability scanning.
- Ansible deployment automation.
- Kind and Helm local Kubernetes deployment.
- Prometheus, Grafana, and Loki monitoring stack.
- SNS notification integration.
- EventBridge integration.
- Dedicated CloudTrail project configuration.
- Public HTTPS access with a domain and TLS certificate.

These are optional extensions and should not be described as completed features.
## 12. Important Project Limitations

- CareFlow is an educational demonstration application, not a production healthcare platform.
- Use synthetic demonstration data only.
- Do not enter real patient records or sensitive medical information.
- The application is not intended for diagnosis, treatment, or emergency care.
- AWS deployment verification demonstrates a working project environment, not production readiness.
- The EC2 application is accessed through Systems Manager port forwarding; public inbound application access is not configured.
- SNS, EventBridge, and a dedicated CloudTrail project configuration remain unimplemented.
- GitHub Actions, Trivy, Ansible, Kubernetes, Helm, Prometheus, Grafana, and Loki remain optional planned improvements.
- AWS services may incur charges. Free Tier eligibility and available credits vary by account and service.
- Stop the EC2 instance when it is no longer required for demonstrations. Stopping EC2 does not necessarily eliminate charges for associated storage or other retained resources.
## 13. Conclusion

CareFlow demonstrates how a clinic appointment management application can be developed using Python, FastAPI, frontend web technologies, DynamoDB, Docker, and asynchronous event-processing patterns.

The project also provides a foundation for exploring AWS cloud infrastructure, DevOps automation, container security, monitoring, and infrastructure as code through a cost-conscious deployment approach.
