# CareFlow - DevOps Tools



## 1. Overview



CareFlow uses containerization, automation, version control, security scanning, and monitoring tools to support the development and deployment lifecycle.



The project prioritizes free and open-source tools wherever practical.



## 2. DevOps Technology Stack



| No. | Tool | Purpose | Status |

|---|---|---|---|

| 1 | Git | Version control | Installed and used |

| 2 | GitHub | Source code hosting | Repository available |

| 3 | Python | Backend development | Implemented |

| 4 | Docker | Application containerization | Implemented and tested |

| 5 | Docker Compose | Multi-container orchestration | Implemented and tested |

| 6 | Apache HTTP Server | Frontend hosting and reverse proxy | Implemented and tested |

| 7 | AWS CLI | AWS command-line management | Installed |

| 8 | GitHub Actions | CI/CD automation | Planned |

| 9 | Trivy | Container and dependency vulnerability scanning | Planned |

| 10 | Ansible | Configuration management | Planned |

| 11 | Kubernetes (Kind) | Local container orchestration practice | Planned |

| 12 | Helm | Kubernetes application packaging | Planned |

| 13 | Prometheus | Metrics collection | Planned |

| 14 | Grafana | Monitoring dashboards | Planned |

| 15 | Loki | Log aggregation | Planned |

| 16 | CloudFormation | AWS infrastructure as code | Planned |



## 3. Development Workflow



1\. Develop application features locally.

2\. Track source changes using Git.

3\. Run backend automated tests using pytest.

4\. Build backend and frontend Docker images.

5\. Run the application using Docker Compose.

6\. Verify application health and role-based workflows.

7\. Introduce automated CI/CD and security scanning.

8\. Deploy to AWS after reviewing cost, security, and infrastructure requirements.



## 4. Testing and Quality



\- Pytest is used for backend automated testing.

\- Docker builds verify container configurations.

\- Docker Compose supports local integration testing.

\- Git diff checks help identify whitespace errors.

\- Trivy is planned for vulnerability scanning.



## 5. Monitoring and Logging



The planned monitoring stack includes:



\- Prometheus for metrics collection.

\- Grafana for dashboards.

\- Loki for centralized log aggregation.

\- Amazon CloudWatch for AWS-side monitoring after cloud deployment.



## 6. Automation



GitHub Actions is planned for automated testing and build workflows.



Ansible is planned for configuration management, while CloudFormation will be used for AWS infrastructure provisioning.



## 7. Current Status



Docker-based application execution, backend tests, and local integration workflows have been implemented and tested. CI/CD, Kubernetes, vulnerability scanning, monitoring, and AWS infrastructure automation remain planned activities.



No cloud deployment or production CI/CD pipeline is currently active.
