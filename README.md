# CareFlow - Clinic Appointment Management Platform

CareFlow is a containerized clinic appointment and management demonstration platform developed using Python, FastAPI, HTML, CSS, JavaScript, Docker, and AWS technologies. It provides separate workflows for patients, doctors, and administrators.

> **Important:** CareFlow is an educational demonstration project. Use synthetic data only. It is not intended for real patient records, medical diagnosis, treatment, or emergency care.

## 1. Project Overview

CareFlow aims to simplify basic clinic appointment management by providing a centralized platform for patients, doctors, and administrators.

The project demonstrates backend API development, role-based authentication, database integration, containerization, asynchronous event processing, and a proposed AWS cloud deployment architecture.

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
| AWS CLI | Manage AWS resources | Installed |
| GitHub Actions | CI/CD automation | Planned |
| Trivy | Container vulnerability scanning | Planned |
| Ansible | EC2 configuration and deployment automation | Planned |
| Kubernetes (Kind) | Local Kubernetes environment | Planned |
| Helm | Kubernetes package management | Planned |
| Prometheus | Metrics collection | Planned |
| Grafana | Monitoring dashboards | Planned |
| Loki | Log aggregation | Planned |
| CloudFormation | Infrastructure as code | Planned |

## 4. AWS Cloud Architecture

The proposed CareFlow cloud architecture uses **12 AWS services, excluding IAM**. IAM is required for identity and access management but is not included in the service count.

| No. | AWS Service | Purpose | Current Status |
|---:|---|---|---|
| 1 | Amazon EC2 | Host the containerized CareFlow application | Planned |
| 2 | Amazon VPC | Provide network isolation and configuration | Planned |
| 3 | Amazon S3 | Store selected static assets and deployment artefacts | Planned |
| 4 | Amazon DynamoDB | Store application and event-processing data | Repository implementation and local testing completed |
| 5 | Amazon SQS | Queue appointment events for asynchronous processing | Dispatcher logic tested locally; AWS integration pending |
| 6 | AWS Lambda | Process queued appointment events | Handler logic tested locally; AWS deployment pending |
| 7 | Amazon SNS | Support notification delivery | Planned |
| 8 | Amazon EventBridge | Support event routing and scheduled automation | Planned |
| 9 | Amazon CloudWatch | Monitor application logs, metrics, and alarms | Planned |
| 10 | AWS CloudTrail | Record AWS account activity | Planned |
| 11 | AWS Systems Manager | Support secure EC2 administration | Planned |
| 12 | AWS CloudFormation | Provision infrastructure as code | Planned |

**Note:** This table represents the target AWS architecture. It does not mean all 12 services have been deployed. Current development and testing have been performed locally. AWS resource provisioning will be a separate deployment phase.

### IAM

AWS IAM will be used to manage permissions and assign least-privilege access to users, EC2 instances, Lambda functions, and other AWS services. IAM is excluded from the 12-service count.

## 5. Application Architecture

CareFlow follows a layered application structure:

1. **Frontend:** Provides the patient, doctor, and administrator interfaces.
2. **Web server:** Apache serves frontend files and forwards API requests.
3. **Backend:** FastAPI handles authentication, authorization, validation, and application operations.
4. **Repository layer:** Provides storage interfaces and implementations.
5. **Database:** DynamoDB stores application records when the DynamoDB backend is selected.
6. **Event processing:** Outbox and consumer components support asynchronous appointment event processing.

### Appointment Event Processing

CareFlow implements an outbox-based event design.

- Appointment creation and supported status changes can write an outbox event in the same DynamoDB transaction as the appointment update.
- The dispatcher claims pending events and sends them to an SQS-compatible client.
- The Lambda-compatible consumer validates incoming event records.
- A processed-events repository tracks event IDs to prevent duplicate processing.
- Failed records can be returned for retry through SQS partial-batch failure handling.

The dispatcher, handler, and event-processing logic have been tested locally. An actual AWS SQS queue, Lambda function, and event source mapping have not yet been deployed.

## 6. Repository Structure

```text
CareFlow/
â”‚
â”œâ”€â”€ app/
â”‚   â”œâ”€â”€ backend/
â”‚   â”‚   â”œâ”€â”€ careflow_api/
â”‚   â”‚   â”‚   â”œâ”€â”€ routers/
â”‚   â”‚   â”‚   â”œâ”€â”€ main.py
â”‚   â”‚   â”‚   â”œâ”€â”€ storage.py
â”‚   â”‚   â”‚   â”œâ”€â”€ dynamodb_repositories.py
â”‚   â”‚   â”‚   â”œâ”€â”€ dynamodb_tables.py
â”‚   â”‚   â”‚   â”œâ”€â”€ outbox_dispatcher.py
â”‚   â”‚   â”‚   â”œâ”€â”€ outbox_worker.py
â”‚   â”‚   â”‚   â”œâ”€â”€ lambda_handler.py
â”‚   â”‚   â”‚   â””â”€â”€ event_processor.py
â”‚   â”‚   â”‚
â”‚   â”‚   â”œâ”€â”€ tests/
â”‚   â”‚   â”œâ”€â”€ requirements.txt
â”‚   â”‚   â””â”€â”€ requirements-runtime.txt
â”‚   â”‚
â”‚   â””â”€â”€ frontend/
â”‚       â”œâ”€â”€ apache/
â”‚       â”‚   â””â”€â”€ httpd.conf
â”‚       â”œâ”€â”€ app.js
â”‚       â”œâ”€â”€ index.html
â”‚       â”œâ”€â”€ styles.css
â”‚       â””â”€â”€ Dockerfile
â”‚
â”œâ”€â”€ docs/
â”‚   â”œâ”€â”€ architecture.md
â”‚   â”œâ”€â”€ aws-services.md
â”‚   â”œâ”€â”€ devops-tools.md
â”‚   â”œâ”€â”€ local-setup.md
â”‚   â””â”€â”€ testing.md
â”‚
â”œâ”€â”€ tools/
â”‚   â””â”€â”€ dynamodb-local/
â”‚
â”œâ”€â”€ .env.example
â”œâ”€â”€ .gitignore
â”œâ”€â”€ Dockerfile
â”œâ”€â”€ compose.yaml
â””â”€â”€ README.md
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

### Completed

- Role-based patient, doctor, and administrator workflows.
- User registration and authentication.
- Doctor profile and account management.
- Appointment creation, viewing, cancellation, and status updates.
- FastAPI backend and browser-based frontend.
- In-memory and DynamoDB repository implementations.
- DynamoDB outbox and processed-events repository logic.
- Appointment event dispatcher and Lambda-compatible consumer logic.
- Backend automated test suite.
- Dockerfiles for backend and frontend.
- Apache reverse proxy configuration.
- Docker Compose deployment.
- Local end-to-end application testing.
- Docker end-to-end application testing.
- Five project documentation files.

### Remaining Work

- Capture application screenshots.
- Configure GitHub Actions CI/CD.
- Integrate Trivy security scanning.
- Configure Ansible deployment automation.
- Set up Kind and Helm for local Kubernetes practice.
- Integrate Prometheus, Grafana, and Loki.
- Prepare AWS CloudFormation templates.
- Review AWS security and expected costs.
- Obtain approval before creating AWS resources.
- Deploy and test the AWS architecture in a separate phase.

## 12. Important Project Limitations

- CareFlow is a demonstration application, not a production healthcare platform.
- All user and appointment data must be synthetic.
- Local DynamoDB testing does not establish that AWS DynamoDB has been deployed.
- Local dispatcher and Lambda handler tests do not establish that AWS SQS or Lambda has been deployed.
- Planned DevOps tools and AWS services must not be described as completed until they have been configured and tested.

## 13. Conclusion

CareFlow demonstrates how a clinic appointment management application can be developed using Python, FastAPI, frontend web technologies, DynamoDB, Docker, and asynchronous event-processing patterns.

The project also provides a foundation for exploring AWS cloud infrastructure, DevOps automation, container security, monitoring, and infrastructure as code through a cost-conscious deployment approach.
