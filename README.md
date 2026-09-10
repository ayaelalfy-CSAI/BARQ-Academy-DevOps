<img src="assets/barq-logo.svg" alt="BARQ Systems" width="180">

# DevOps Internship Task

A containerized Flask application deployed with Docker Compose, using NGINX as a reverse proxy and load balancer, with PostgreSQL and Redis as backend services.

The project includes automated validation, backend failure/recovery testing, database backup/restore, healthchecks, and GitHub Actions CI.

## Architecture

The application consists of:

- **nginx** — reverse proxy and load balancer
- **app-01** — Flask application instance
- **app-02** — Flask application instance
- **postgres** — PostgreSQL database
- **redis** — Redis service

<img src="assets/flowReqest.png" alt="Request Flow" width="900">

## Prerequisites

Install:

- Git
- Docker
- Docker Compose
- Python 3

Verify:

```bash
git --version
docker --version
docker compose version
python3 --version
```

## Setup

Clone the repository:

```bash
git clone <REPOSITORY_URL>
cd barq-academy
```

Create the environment file:

```bash
cp .env.example .env
```

Edit `.env` and provide the required configuration:

```bash
nano .env
```

> **Important:** Do not commit `.env` to Git.

Verify:

```bash
git status
```

The `.env` file should not appear as a tracked file.

## Validate Docker Compose Configuration

Before starting the application:

```bash
docker compose config
```

This verifies that the Compose configuration is valid and that the required environment variables are available.

## Build

Build all application images:

```bash
docker compose build
```

To rebuild without using the Docker build cache:

```bash
docker compose build --no-cache
```


## Start

Start all services in detached mode:

```bash

docker compose up -d

```

Check the containers:

```bash

docker compose ps -a

```

Expected services:

- nginx

- app-01

- app-02

- postgres

- redis

Check logs:

```bash

docker compose logs

```

For a specific service:

```bash

docker compose logs nginx

docker compose logs app-01

docker compose logs app-02

docker compose logs postgres

docker compose logs redis

```

Follow logs in real time:

```bash

docker compose logs -f

```


## Check Health

Check container status:

```bash

docker compose ps

```

The application services should eventually report **healthy**.

You can also inspect individual containers:

```bash

docker inspect -f '{{.State.Health.Status}}' nginx

docker inspect -f '{{.State.Health.Status}}' app-01

docker inspect -f '{{.State.Health.Status}}' app-02

docker inspect -f '{{.State.Health.Status}}' postgres

docker inspect -f '{{.State.Health.Status}}' redis

```

Expected:

```text

healthy

```

Healthchecks are used because a container being **running** does not necessarily mean that the application inside it is ready to serve requests.


## Test the Application

The main validation script is:

```bash

python3 validate.py

```

It verifies:

- Container availability

- Container health

- Public access through NGINX

- `/health`

- `/ready`

- PostgreSQL readiness

- Redis readiness

- `/instance`

- `/records`

- `/counter`

- Traffic distribution between app-01 and app-02

A successful validation should end with no **FAIL** checks.

You can also verify the public endpoint manually:

Check the health endpoint:

```bash

curl http://localhost:8080/health

```

Check readiness:

```bash

curl http://localhost:8080/ready

```

Check the backend instance:

```bash

curl http://localhost:8080/instance

```


## Backend Load-Balancing Test

The validation script checks that both backend instances receive traffic.

Run:

```bash

python3 validate.py

```

The `/instance` endpoint is requested multiple times.

Example:

```text

Backend distribution:

app-01: 5

app-02: 5

```

The exact distribution is not expected to be perfectly equal because NGINX load balancing does not guarantee an exact 50/50 distribution for a small number of requests.

The important requirement is that **both backends are observed**.


## Backend Failure and Recovery Test

The failure test intentionally stops one backend and verifies that the remaining backend continues serving traffic.

Run:

```bash

python3 failure_test.py

```

The test performs:

1. Verify that app-01 and app-02 are running.
2. Send baseline traffic.
3. Stop app-01.
4. Verify that app-01 is stopped.
5. Verify that NGINX is still running.
6. Send traffic while app-01 is down.
7. Verify that app-02 serves requests.
8. Verify that the service remains available.
9. Restart app-01.
10. Wait until app-01 becomes healthy.
11. Send recovery traffic.
12. Verify that app-01 serves requests again.

Expected flow:

```text

app-01

|

X stopped

|

v

NGINX

|

v

app-02

|

v

Requests continue successfully

```

After recovery:

```text

app-01 → started → healthy → receives traffic again

```

This test demonstrates **backend-level resilience**.

> **Note:** This does not prove complete production high availability because NGINX and PostgreSQL can still be single points of failure.


## Database Backup

The database backup script is:

```bash

./backup.sh

```

If required, make the script executable:

```bash

chmod +x backup.sh

```

Then run:

```bash

./backup.sh

```

The script creates a PostgreSQL backup that can be used for restoration.

Verify the generated backup:

```bash

ls -lh

```


## Database Restore

Make the restore script executable:

```bash

chmod +x restore.sh

```

Run:

```bash

./restore.sh

```

After restoring, verify that the application is available:

```bash

python3 validate.py

```

The `/records` endpoint can be used to verify that persistent application data is still available after the backup/restore procedure.


## Stop Services

To stop the containers without removing them:

```bash

docker compose stop

```

To stop and remove the containers:

```bash

docker compose down

```

The persistent volumes are not removed by the normal `docker compose down` command.


## Cleanup

To remove containers and networks:

```bash

docker compose down

```

To remove containers, networks, and persistent volumes:

```bash

docker compose down -v

```

> **Warning:** `docker compose down -v` deletes the Docker volumes and therefore can delete persistent PostgreSQL/Redis data.

Use it only when a complete cleanup is required.

Optional cleanup of unused Docker resources:

```bash

docker system prune

```

Review the resources before confirming the prune operation.


## CI (Continuous Intergration)

GitHub Actions is configured to run on:

- Push

- Pull request

The CI workflow performs:

Checkout

   ↓

Create CI `.env`

   ↓

Python syntax checks

   ↓

Shell syntax checks

   ↓

Docker Compose validation

   ↓

Docker build

   ↓

Start services

   ↓

Wait for healthchecks

   ↓

Run `validate.py`

   ↓

Trivy security scan

   ↓

Cleanup

The CI environment uses GitHub Actions Secrets for PostgreSQL configuration.

Secrets are referenced through:

```text

CI_POSTGRES_USER

CI_POSTGRES_DB

CI_POSTGRES_PASSWORD

```

Secrets are not stored directly in the repository.

The Trivy image scan is currently configured as a **non-blocking security check** for the assessment.


## Ports and Networks

The public entry point is:

```text

localhost:8080

```

NGINX listens internally on:

```text

80

```

Only NGINX is published to the host.

The application, PostgreSQL, and Redis services communicate through Docker networks.

This reduces the externally exposed attack surface and prevents direct host access to internal services.


## Persistence

PostgreSQL uses persistent storage so that application data survives normal container recreation.

Redis persistence is also configured according to the Compose configuration.

However:

```bash

docker compose down -v

```

removes the volumes.

Therefore, production deployments should additionally use:

- Automated backups

- Off-host backup storage

- Backup retention policies

- Encryption

- Regular restore testing


## Troubleshooting

Investigation details, failed attempts, root causes, fixes, and retests are documented separately in:

[`troubleshooting.md`](troubleshooting.md)

Architecture and design decisions are documented in:

[`decisions.md`](decisions.md)

Security risks and improvements are documented in:

[`security_review.md`](security_review.md)

The log analysis and correlated evidence are documented in:

[`log_analysis.md`](log_analysis.md)
