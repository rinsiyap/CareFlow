# CareFlow - AWS Services



## 1. Overview



CareFlow is designed to use AWS infrastructure for hosting, storage, event processing, monitoring, and deployment automation.



The project documents 12 AWS services. Core infrastructure and application services have been deployed in us-east-2; optional services remain planned.



## 2. AWS Services



| No. | AWS Service | Planned Purpose | Status |

|---|---|---|---|

| 1 | Amazon EC2 | Host the containerized application | Deployed and running |

| 2 | Amazon VPC | Provide network isolation | Deployed |

| 3 | Amazon S3 | Store the Lambda deployment artifact in a private bucket | Deployed |

| 4 | Amazon DynamoDB | Store users, doctors, appointments, and events | Deployed and integrated |

| 5 | Amazon SQS | Queue appointment events | Deployed and verified |

| 6 | AWS Lambda | Process queued events | Deployed and verified |

| 7 | Amazon SNS | Send event notifications | Planned |

| 8 | Amazon EventBridge | Support event routing and integration | Planned |

| 9 | Amazon CloudWatch | Collect logs, metrics, and alarms | Lambda logs verified; additional monitoring optional |

| 10 | AWS CloudTrail | Record account and API activity | Planned |

| 11 | AWS Systems Manager | Support instance administration and configuration | Used for secure instance access |

| 12 | AWS CloudFormation | Automate infrastructure provisioning | Used; five stacks deployed |



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



The tests above describe local implementation and test coverage. AWS resources were deployed separately, and the cloud appointment event-processing flow was verified.



## 5. Cost Management



The project prioritizes AWS Free Tier eligibility and available credits where applicable.



Before deploying any service:

\- Check current pricing and Free Tier eligibility.

\- Review service limits and regional availability.

\- Avoid unnecessary always-on resources.

\- Stop or delete resources when they are no longer required.

\- Monitor AWS billing and budgets.



## 6. Deployment Status



AWS infrastructure has been deployed in us-east-2 using five CloudFormation stacks covering DynamoDB, SQS, the Lambda artifact bucket, Lambda processing, and the EC2 application host. SNS, EventBridge, and a dedicated CloudTrail configuration have not been deployed.



CareFlow uses synthetic demonstration data only and is not intended for real healthcare data or clinical use.
