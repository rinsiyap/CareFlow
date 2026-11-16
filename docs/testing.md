# CareFlow - Testing Guide



## 1. Overview



CareFlow uses automated backend tests and local integration testing to verify application functionality.



Testing is performed locally using pytest, Docker, and DynamoDB Local. No production AWS environment is required for the current test suite.



## 2. Testing Tools



| Tool | Purpose |

|---|---|

| Pytest | Backend automated testing |

| FastAPI TestClient | API endpoint testing |

| Moto | AWS service mocking |

| DynamoDB Local | Local DynamoDB integration testing |

| Docker | Container build and execution testing |

| Docker Compose | Multi-container integration testing |



## 3. Run Backend Tests



Open PowerShell in the project root:



```powershell

cd C:\\dev\\CareFlow

```



Run the complete backend test suite:



```powershell

.\\.venv\\Scripts\\python.exe -m pytest .\\app\\backend\\tests -v

```



The test suite covers authentication, authorization, doctor management, appointment workflows, database repositories, and event processing.



## 4. Application Health Tests



With the Docker application running, verify these endpoints:



\- `http://localhost:8080/health/live`

\- `http://localhost:8080/health/ready`



The liveness endpoint checks whether the application is running. The readiness endpoint checks whether required application dependencies are available.



## 5. Docker Tests



Build the containers:



```powershell

docker compose build

```



Start the application:



```powershell

docker compose up -d

```



Check container status:



```powershell

docker compose ps

```



Inspect logs:



```powershell

docker compose logs --tail 100

```



## 6. Functional Testing



The following workflows have been tested locally:



### Administrator

\- Administrator login.

\- Add a doctor profile.

\- Provision a doctor account.

\- View appointment records.



### Doctor

\- Doctor login.

\- View assigned appointments.

\- Update appointment status.



### Patient

\- Patient registration and login.

\- Browse available doctors.

\- Book an appointment.

\- View appointment history.

\- Cancel an appointment.



## 7. Database and Event Testing



Local tests cover:



\- DynamoDB repository operations.

\- Appointment creation and status changes.

\- Transactional outbox event creation.

\- Outbox event dispatch and retry behavior.

\- Event processing and validation.

\- Processed-event idempotency.

\- Event lease and recovery behavior.



## 8. Code Quality Checks



Check the Git diff for whitespace errors:



```powershell

git diff --check

```



Review the current working tree:



```powershell

git status --short

```



## 9. Current Test Status



The latest recorded full backend test run completed with 224 passed tests and 1 warning.



This result reflects the local backend test suite. AWS deployment verification was performed separately.



## 10. Testing Limitations



\- Production load, penetration, and disaster-recovery testing have not been performed.

\- AWS SQS and Lambda resources are deployed; the appointment event-processing flow was verified, but comprehensive production testing remains outstanding.

\- Production load, penetration, and disaster-recovery testing remain future work.

\- Only synthetic demonstration data should be used.



CareFlow is an educational demonstration project and is not intended for real healthcare operations.
