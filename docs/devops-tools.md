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

| 7 | AWS CLI | AWS command-line management | Installed and used |

| 8 | GitHub Actions | CI and security automation | Workflows implemented and tested |

| 9 | Trivy | Container image, configuration and filesystem scanning | Security workflow implemented |

| 10 | Ansible | Configuration management | Planned |

| 11 | Kubernetes (Kind) | Local container orchestration practice | Planned |

| 12 | Helm | Kubernetes application packaging | Planned |

| 13 | Prometheus | Metrics collection and health probe metrics | Implemented locally |

| 14 | Grafana | Monitoring dashboards | Implemented locally |

| 15 | Loki | Log aggregation | Planned |

| 16 | CloudFormation | AWS infrastructure as code | Used; five stacks deployed |



## 3. Development Workflow



1\. Develop application features locally.

2\. Track source changes using Git.

3\. Run backend automated tests using pytest.

4\. Build backend and frontend Docker images.

5\. Run the application using Docker Compose.

6\. Verify application health and role-based workflows.

7. Run GitHub Actions CI and security workflows.

8\. Deploy to AWS after reviewing cost, security, and infrastructure requirements.



## 4. Testing and Quality



\- Pytest is used for backend automated testing.

\- Docker builds verify container configurations.

\- Docker Compose supports local integration testing.

\- Git diff checks help identify whitespace errors.

\- Trivy is used in the GitHub Actions security workflow for container and configuration scanning.



## 5. Monitoring and Logging



The local monitoring stack includes:



\- Prometheus for metrics collection and backend probe metrics.

\- Grafana for dashboards and backend health visualization.

\- Loki for centralized log aggregation; not implemented.

\- Amazon CloudWatch for AWS Lambda log inspection; additional metrics and alarms remain optional.



## 6. Automation



GitHub Actions runs the configured CI and security workflows for automated checks.



Ansible remains planned for configuration management. CloudFormation has been used to provision the deployed AWS infrastructure.



## 7. Current Status



Docker-based application execution, backend tests, local integration workflows, AWS deployment, and CloudFormation infrastructure provisioning have been implemented and verified. GitHub Actions workflows, Trivy security scanning, and local Prometheus/Grafana/Blackbox Exporter monitoring have been implemented. Kubernetes, Ansible, and Loki remain planned.



The AWS cloud deployment is active. A production CI/CD pipeline is not currently configured.
