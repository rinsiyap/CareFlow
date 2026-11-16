# CareFlow - Monitoring and Observability

## 1. Overview

CareFlow uses a separate, local monitoring stack to check backend availability and response time.

The monitoring stack consists of:

- Prometheus - collects and stores monitoring metrics.
- Grafana - displays monitoring dashboards.
- Blackbox Exporter - probes backend HTTP health endpoints.

The monitoring stack runs independently from the main application Compose configuration. It is intended for local development and demonstration, not deployed AWS monitoring.

## 2. Monitoring Architecture

```text
CareFlow Backend
      |
      | HTTP health endpoints
      v
Blackbox Exporter (:9115)
      |
      | probe metrics
      v
Prometheus (:9090)
      |
      | Prometheus data source
      v
Grafana (:3000)
      |
      v
CareFlow Monitoring Dashboard
```

The backend is connected to the `careflow-monitoring` Docker network so the monitoring containers can reach it.

## 3. Monitoring Components

| Component | Purpose | Local address |
|---|---|---|
| Prometheus | Scrapes and stores monitoring metrics | http://localhost:9090 |
| Blackbox Exporter | Performs HTTP health probes | http://localhost:9115 |
| Grafana | Monitoring dashboard | http://localhost:3000 |

Prometheus uses a 15-second scrape interval and a 7-day local data retention period.

## 4. Backend Health Monitoring

Blackbox Exporter checks these backend endpoints:

| Endpoint | Purpose |
|---|---|
| `/health/live` | Checks whether the backend application is alive |
| `/health/ready` | Checks whether the backend is ready and its database is connected |

The `http_2xx` Blackbox module treats HTTP 200 as a successful probe.

Prometheus records probe results and duration metrics, including:

- `probe_success`
- `probe_duration_seconds`

A successful probe returns `probe_success = 1`; a failed probe returns `probe_success = 0`.

The application does not currently expose a Prometheus `/metrics` endpoint. Backend health monitoring is therefore performed through Blackbox HTTP probes.

## 5. Grafana Dashboard

The provisioned dashboard is named **CareFlow Monitoring Overview**.

It contains six panels:

1. Prometheus Availability
2. Prometheus Memory Usage
3. Active Time Series
4. Prometheus HTTP Request Rate
5. Backend Health Status
6. Backend Response Time

Prometheus is configured as the dashboard data source. Dashboard provisioning files are stored under:

`monitoring/grafana/provisioning/`

## 6. Project Configuration Files

```text
monitoring/
|-- compose.monitoring.yaml
|-- blackbox/
|   `-- blackbox.yml
|-- prometheus/
|   `-- prometheus.yml
`-- grafana/
    `-- provisioning/
        |-- dashboards/
        |   |-- careflow-overview.json
        |   `-- provider.yml
        `-- datasources/
            `-- prometheus.yml
```

## 7. Starting the Monitoring Stack

Run these commands from the CareFlow repository root:

```powershell
docker compose -f .\monitoring\compose.monitoring.yaml up -d
```

The external Docker network `careflow-monitoring`, the external Prometheus data volume `careflow-monitoring_prometheus-data`, and the backend container must be available.

If the backend container is not connected to the monitoring network, connect it using:

```powershell
docker network connect careflow-monitoring careflow-backend-1
```

Only run this connection command when the backend is not already connected.

Check the monitoring containers:

```powershell
docker compose -f .\monitoring\compose.monitoring.yaml ps
```

## 8. Accessing the Dashboard

Open Grafana:

http://localhost:3000

The local development configuration initially uses:

- Username: `admin`
- Password: `admin`

Change the default password before using Grafana beyond local development.

Prometheus targets can be inspected at:

http://localhost:9090/targets

The Grafana dashboard can be opened from the CareFlow folder.

## 9. Stopping the Monitoring Stack

To stop the monitoring containers without removing their stored data:

```powershell
docker compose -f .\monitoring\compose.monitoring.yaml stop
```

To start them again:

```powershell
docker compose -f .\monitoring\compose.monitoring.yaml start
```

## 10. Scope and Limitations

- Prometheus, Grafana and Blackbox Exporter currently run locally in Docker.
- Their monitoring data is stored in local Docker volumes.
- Backend availability and response time are monitored through HTTP probes.
- The application does not currently expose its own Prometheus metrics endpoint.
- This monitoring stack is separate from the AWS deployment.
- It does not currently provide AWS-hosted Grafana, centralized log aggregation or production alerting.

## 11. Implementation Status

The local Prometheus, Grafana and Blackbox Exporter stack has been configured and tested.

Prometheus successfully reports the backend liveness endpoint, backend readiness endpoint and its own scrape target as UP.

The Grafana dashboard displays all six configured monitoring panels.
