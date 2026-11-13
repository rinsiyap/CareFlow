# CareFlow - AWS Services



## 1. Overview



CareFlow is designed to use AWS infrastructure for hosting, storage, event processing, monitoring, and deployment automation.



The project targets 12 AWS services. The current implementation has been tested locally; AWS cloud deployment remains future work.



## 2. AWS Services



| No. | AWS Service | Planned Purpose | Status |

|---|---|---|---|

| 1 | Amazon EC2 | Host the containerized application | Planned |

| 2 | Amazon VPC | Provide network isolation | Planned |

| 3 | Amazon S3 | Store static assets and project files | Planned |

| 4 | Amazon DynamoDB | Store users, doctors, appointments, and events | Local implementation tested |

| 5 | Amazon SQS | Queue appointment events | Local dispatcher logic tested |

| 6 | AWS Lambda | Process queued events | Local handler logic tested |

| 7 | Amazon SNS | Send event notifications | Planned |

| 8 | Amazon EventBridge | Support event routing and integration | Planned |

| 9 | Amazon CloudWatch | Collect logs, metrics, and alarms | Planned |

| 10 | AWS CloudTrail | Record account and API activity | Planned |

| 11 | AWS Systems Manager | Support instance administration and configuration | Planned |

| 12 | AWS CloudFormation | Automate infrastructure provisioning | Planned |



## 3. IAM and Security



AWS IAM is used as a supporting security service for access management. It is not included in the 12-service count.



Planned security practices:

\- Apply least-privilege IAM policies.

\- Use separate roles for application components.

\- Avoid hardcoding AWS credentials.

\- Keep application secrets outside source control.

\- Restrict network access to required ports and services.



## 4. Local Development and Testing



The following components have local implementations:



\- DynamoDB Local for database development.

\- SQS-compatible dispatcher logic tested with local test infrastructure.

\- Lambda-compatible event handler tested locally.

\- Docker Compose for running the application containers.



These tests do not mean that actual AWS resources have been deployed.



## 5. Cost Management



The project prioritizes AWS Free Tier eligibility and available credits where applicable.



Before deploying any service:

\- Check current pricing and Free Tier eligibility.

\- Review service limits and regional availability.

\- Avoid unnecessary always-on resources.

\- Stop or delete resources when they are no longer required.

\- Monitor AWS billing and budgets.



## 6. Deployment Status



No AWS cloud infrastructure has been deployed as part of the current implementation. CloudFormation templates and cloud deployment steps are planned future work.



CareFlow uses synthetic demonstration data only and is not intended for real healthcare data or clinical use.
