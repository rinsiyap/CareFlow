# CareFlow - Local Setup Guide



## 1. Prerequisites



Install the following tools before running CareFlow:



\- Windows 10 or 11

\- Python 3.12

\- Git

\- Docker Desktop

\- Docker Compose

\- Visual Studio Code (recommended)



AWS CLI is installed for future AWS integration but is not required to run the local Docker demonstration.



## 2. Project Directory



Clone or open the CareFlow project:



```powershell

cd C:\\dev\\CareFlow

```



The project contains:



\- `app/backend` - FastAPI application

\- `app/frontend` - HTML, CSS, and JavaScript frontend

\- `docs` - Project documentation

\- `compose.yaml` - Docker Compose configuration

\- `Dockerfile` - Backend container configuration



## 3. Python Environment



Create and activate the virtual environment if it does not already exist:



```powershell

python -m venv .venv

.\\.venv\\Scripts\\Activate.ps1

```



Install development dependencies using the project's requirements files.



## 4. Environment Configuration



Configure the required environment variables using the existing local `.env` file.



The configuration includes:

\- Bootstrap administrator settings

\- JWT signing secret

\- Storage backend settings

\- DynamoDB configuration



Never commit `.env` files or expose passwords, tokens, or secret keys.



## 5. Run with Docker Compose



Ensure Docker Desktop is running.



Start the local DynamoDB-compatible service and configure the Docker environment variables required by `compose.yaml`.



Build and start the application:



```powershell

docker compose up --build -d

```



Check container status:



```powershell

docker compose ps

```



View application logs:



```powershell

docker compose logs --tail 100

```



## 6. Access the Application



Open the frontend:



`http://localhost:8080`



Backend health endpoints through the frontend proxy:



\- `http://localhost:8080/health/live`

\- `http://localhost:8080/health/ready`



## 7. Local Testing



Run backend tests from the project root:



```powershell

.\\.venv\\Scripts\\python.exe -m pytest .\\app\\backend\\tests -v

```



The tests cover API functionality, authentication, repositories, DynamoDB integration, and event processing.



## 8. Troubleshooting



### Docker containers are not running



```powershell

docker compose ps

docker compose logs --tail 100

```



### Backend readiness check fails



Verify that the DynamoDB-compatible service is running and that the configured endpoint and table names are correct.



### Frontend cannot reach the backend



Check the Apache reverse proxy configuration and backend container status.



### Port is already in use



Identify the process using the required port before changing application configuration. Avoid terminating processes without confirming their purpose.



## 9. Data and Security



\- Use synthetic demonstration data only.

\- Do not enter real patient information.

\- Keep credentials and secrets private.

\- Local DynamoDB Local data may be lost when its in-memory process stops.

\- Do not use this demonstration setup for production healthcare operations.
