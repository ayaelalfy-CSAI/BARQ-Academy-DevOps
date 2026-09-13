# Technical Decisions

## Decision 1 — Base image for the application containers

- **Choice:** `python:3.12-slim-bookworm` (pinned by digest).
- **Why:** Debian-slim provides a small, well-maintained image with `apt` available if a native dependency is ever needed, while remaining significantly smaller than the full `python:3.12` image. Pinning by digest instead of only using a tag guarantees the exact same base image across builds and avoids silent upstream image changes.
- **Alternative:** `python:3.12-alpine`.
- **Trade-off:** Alpine is smaller, but uses musl libc, which can cause compatibility or build issues with Python packages that contain C extensions. Slim-bookworm is slightly larger but provides better compatibility and simpler builds.
- **Evidence / commit:** Dockerfile, `FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`.
- **Production improvement:** Use a multi-stage build to keep build dependencies out of the final image and reduce the final image size.

---

## Decision 2 — Running the application as a non-root user

- **Choice:** Create a dedicated `app` user/group with UID/GID `10001` and run the container using `USER app`.
- **Why:** Running the application as a non-root user follows the assessment's security requirement and limits the impact if the application process is compromised.
- **Alternative:** Run the container as the default root user.
- **Trade-off:** The non-root configuration requires a few additional Dockerfile instructions and correct file ownership using `--chown=app:app`, but it significantly reduces the risk of privilege escalation.
- **Evidence / commit:** Dockerfile, `useradd ... app` and `USER app`. This was also verified after an earlier draft incorrectly ended with `USER root`.
commit: `fix: run application as non-root user`
- **Production improvement:** Add a read-only root filesystem using `read_only: true` in Compose and provide an explicit writable `tmpfs` only for required runtime scratch space.

---

## Decision 3 — Health-check tooling per service

- **Choice:** Use tools already available in each image:
  - `python -c "import urllib.request..."` for `app-01` and `app-02`
  - `pg_isready` for PostgreSQL
  - `redis-cli ping` for Redis
  - `wget --spider` for NGINX
- **Why:** Python's `urllib` is part of the standard library, while `pg_isready`, `redis-cli`, and BusyBox `wget` are already available in their respective official images.
- **Alternative:** Install `curl` in every image and use it for all health checks.
- **Trade-off:** Using one common tool would make the health checks more uniform, but installing `curl` increases image size and adds another package that must be patched and scanned.
- **Evidence / commit:** `docker-compose.yml`, `healthcheck:` configuration for all services. Retested with `docker compose ps -a`, showing all five services as `(healthy)`.
- **Production improvement:** Use separate liveness and readiness probes at the orchestrator level, such as Kubernetes liveness and readiness probes, instead of relying on a single health endpoint for both purposes.

---

## Decision 4 — Fixing the health-check endpoint mismatch instead of changing the application

- **Choice:** When `app-01` and `app-02` reported `unhealthy`, change the Compose health-check target from `/healthz` to `/health` instead of adding a new `/healthz` endpoint to the Flask application.
- **Why:** `server.py` already defines `/health`, and `/health` is the required liveness endpoint specified by the assessment.
- **Alternative:** Add a `/healthz` alias route to `server.py`.
- **Trade-off:** Updating the Compose configuration is a one-line, low-risk fix that keeps the API surface unchanged. Adding another route would create two endpoints serving the same purpose without providing additional value.
- **Evidence / commit:** `fix: change healthcheck endpoint from healthz to health`. Retested through container logs showing successful `200` responses and `docker compose ps -a` showing `(healthy)`.
- **Production improvement:** No additional improvement is required because this was a configuration mismatch rather than a design limitation.

---

## Decision 5 — Network segmentation and isolating the database tier

- **Choice:** Use two Docker networks:
  - `barq-assessment_frontend` for NGINX and the application containers.
  - `barq-assessment_backend` for the application containers, PostgreSQL, and Redis.
  
  The backend network is configured with `internal: true`.
- **Why:** The assessment requires preventing NGINX from directly accessing PostgreSQL and Redis. NGINX is connected only to the frontend network, while PostgreSQL and Redis are connected only to the backend network. The `internal: true` configuration additionally prevents external network access through the backend network.
- **Alternative:** Use a single flat network for all five services and rely on NGINX configuration to prevent access to PostgreSQL and Redis.
- **Trade-off:** Multiple networks add a small amount of Compose configuration, but the isolation is enforced at the Docker network layer rather than relying only on configuration or convention.
- **Evidence / commit:** `docker-compose.yml`, `networks:` configuration. Verified that NGINX is not attached to the backend network and therefore cannot directly resolve or reach PostgreSQL or Redis.
- **Production improvement:** Add host-level firewall rules or Kubernetes NetworkPolicies to provide another layer of network isolation.

---

## Decision 6 — Keeping secrets out of docker-compose.yml

- **Choice:** Reference `${POSTGRES_USER}`, `${POSTGRES_PASSWORD}`, and `${POSTGRES_DB}` from a git-ignored `.env` file. Application secrets such as `DATABASE_URL` and `REDIS_URL` are loaded through the separate git-ignored `config/app.env` using `env_file:`.
- **Why:** The assessment requires keeping real secrets out of source code, Docker images, and `docker-compose.yml`. Safe example files are committed instead, such as `.env.example` and `config/app.env.example`.
- **Alternative:** Hardcode the PostgreSQL password directly in `docker-compose.yml`, as it was in the original starter configuration.
- **Trade-off:** Environment files keep real credentials out of Git, but they are not a complete secrets-management solution. Users with sufficient Docker access may still inspect environment variables through commands such as `docker inspect` or `docker exec`. The application also initially logged the full `DATABASE_URL`, including the password, which was fixed by redacting the password before logging.
- **Evidence / commit:** `docker-compose.yml` uses environment-variable interpolation; `.gitignore` excludes `.env` and `config/app.env`; `.env.example` and `config/app.env.example` are committed as safe templates.
- **Production improvement:** Use a dedicated secrets-management solution such as Docker Secrets, Kubernetes Secrets, HashiCorp Vault, or a cloud secrets manager.

---

## Decision 7 — Resource limits and restart policy per service

- **Choice:** Configure memory and CPU limits for each service and use `restart: unless-stopped`.
  
  Example limits:
  - `app-01`: `256m` / `0.50 CPU`
  - `app-02`: `256m` / `0.50 CPU`
  - `nginx`: `128m` / `0.25 CPU`
  - `redis`: `128m` / `0.25 CPU`
  - `postgres`: `256m` / `0.50 CPU`
- **Why:** Resource limits prevent a runaway container from consuming all host resources. The `unless-stopped` restart policy allows services to recover automatically after failures or host restarts while respecting an operator's explicit `docker stop`.
- **Alternative:** Leave containers without resource limits and use `restart: always` or `restart: "no"`.
- **Trade-off:** Fixed resource limits protect the host, but they may need adjustment as application traffic, concurrency, or database size increases.
- **Evidence / commit:** `docker-compose.yml`, with `mem_limit`, `cpus`, and `restart:` configured for every service.
- **Production improvement:** Use orchestrator-managed resource requests/limits and autoscaling, such as Kubernetes HPA, based on real application and infrastructure metrics.

---

## Decision 8 — PostgreSQL storage: named volume mounted to the real data directory

- **Choice:** Mount the named volume `postgres-data` to PostgreSQL's actual data directory:

  `postgres-data:/var/lib/postgresql/data`

  Redis also uses a persistent named volume:

  `redis-data:/data`

  Redis persistence is enabled using `--appendonly yes`.
- **Why:** The assessment requires proving that database records survive container and PostgreSQL recreation. `/var/lib/postgresql/data` is PostgreSQL's actual data directory. An earlier configuration incorrectly mounted the named volume to `/var/lib/postgresql/backup`, which is not PostgreSQL's active data directory, while the real data directory was stored in a temporary filesystem. That configuration could cause data loss during container recreation.
- **Alternative:** Use a host bind mount instead of a Docker named volume.
- **Trade-off:** Named volumes are portable and managed by Docker, but they are less convenient to inspect directly from the host filesystem than bind mounts.
- **Evidence / commit:** `docker-compose.yml`, `postgres-data:/var/lib/postgresql/data`. Persistence was retested by creating a record through `POST /records`, stopping and removing the PostgreSQL and application containers, starting them again, and confirming the same record through `GET /records`.
- **Production improvement:** Add automated scheduled backups and store backup copies in off-host or object storage. The existing manual `backup.sh` should be supplemented with an automated backup and retention strategy.