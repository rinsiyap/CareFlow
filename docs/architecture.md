# CareFlow - System Architecture



## 1. Overview



CareFlow is a containerized clinic appointment management demonstration platform. It provides separate workflows for patients, doctors, and administrators.



The application uses a FastAPI backend, a static web frontend served by Apache HTTP Server, and Amazon DynamoDB-compatible storage.



\*\*Important:\*\* CareFlow uses synthetic demonstration data only. It is not intended for real patient records or clinical use.



## 2. High-Level Architecture



```text

&#x20;                    Users

&#x20;                      |

&#x20;                      v

&#x20;             Web Browser

&#x20;                      |

&#x20;                      v

&#x20;            Apache HTTP Server

&#x20;            (Frontend Container)

&#x20;                      |

&#x20;                Reverse Proxy

&#x20;                      |

&#x20;                      v

&#x20;              FastAPI Backend

&#x20;             (Backend Container)

&#x20;                      |

&#x20;                      v

&#x20;                DynamoDB

&#x20;            (Application Data)

&#x20;                      |

&#x20;                      v

&#x20;             Transactional Outbox

&#x20;                      |

&#x20;                      v

&#x20;                 Amazon SQS

&#x20;                      |

&#x20;                      v

&#x20;             AWS Lambda Consumer

&#x20;                      |

&#x20;                      v

&#x20;             Processed Events

```



The frontend communicates with the FastAPI backend through Apache reverse proxy routes. The backend manages authentication, role-based access, doctor profiles, appointments, and event creation.



## 3. Application Components



### Frontend

\- HTML, CSS, and JavaScript.

\- Patient, doctor, and administrator dashboards.

\- Served through Apache HTTP Server.

\- Uses the backend REST API.



### Backend

\- Python and FastAPI.

\- JWT-based authentication.

\- Role-based access control.

\- Doctor and appointment management.

\- Health and readiness endpoints.



### Database

\- Amazon DynamoDB is the planned cloud database.

\- DynamoDB Local is used for local development and testing.

\- Separate tables store users, doctors, appointments, outbox events, and processed events.



### Event Processing

\- Appointment operations can write events transactionally to an outbox table.

\- An outbox dispatcher sends events to an SQS-compatible queue.

\- A Lambda-compatible consumer validates and processes messages.

\- A processed-events table supports idempotency and retry handling.



## 4. Container Architecture



Docker Compose runs two application containers:



| Container | Responsibility |

|---|---|

| Backend | Runs the FastAPI application |

| Frontend | Runs Apache and serves the web interface |



DynamoDB Local runs separately and provides local database storage for the containers.



## 5. Security Design



\- Passwords are stored as secure password hashes.

\- JWT tokens protect authenticated API routes.

\- Role-based authorization separates patient, doctor, and administrator operations.

\- Environment variables hold configuration and secrets.

\- Docker services communicate over the Compose network.

\- Only the frontend is exposed on the host through the configured local port.

\- Demonstration data must not contain real patient information.



## 6. Deployment Status



| Component | Status |

|---|---|

| FastAPI backend | Implemented |

| Web frontend | Implemented |

| Apache reverse proxy | Implemented |

| Docker containers | Implemented and locally tested |

| DynamoDB repositories | Implemented and locally tested |

| Transactional outbox | Implemented and locally tested |

| SQS dispatcher logic | Implemented and locally tested |

| Lambda consumer logic | Implemented and locally tested |

| AWS cloud deployment | Planned |



## 7. Limitations



The current project has been tested locally using Docker and DynamoDB Local. AWS infrastructure and managed services have not yet been deployed. Cloud deployment, monitoring, and production security configuration remain future work.



CareFlow is an educational demonstration project, not a production healthcare system.
