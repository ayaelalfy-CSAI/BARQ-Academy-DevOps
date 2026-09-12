# Security and Production-Readiness Review

This review evaluates the security and production-readiness of the final BARQ Systems deployment. Completed work is separated from planned production follow-up items.

## 1. Secrets Management

* **Risk and evidence:** Database credentials are required by Docker Compose and the application. Keeping real credentials in `.env` or `config/app.env` could expose secrets if these files are committed or copied into an image.
* **Impact:** Exposed database credentials could allow unauthorized access to PostgreSQL.
* **Implemented fix / commit:** Removed `COPY config/app.env /srv/app.env` from the Dockerfile so application secrets are not embedded in the image. Secret files are also excluded through `.gitignore`.
  Commit: `fix: secure application configuration`
* **Production follow-up:** Use a dedicated secrets manager such as Docker secrets, Kubernetes Secrets, or a cloud secret-management service instead of local environment files.
* **How to verify:** Run:
  `git ls-files .env config/app.env`
  and verify that no secret files are tracked. Also inspect the Dockerfile and image contents to confirm that `config/app.env` is not copied into the image.

## 2. Host Port Exposure

* **Risk and evidence:** Exposing application, PostgreSQL, or Redis ports directly to the host would bypass NGINX and increase the attack surface.
* **Impact:** Attackers could directly access backend services or application endpoints.
* **Implemented fix / commit:** Only NGINX publishes the application entry point:
  `127.0.0.1:${PUBLIC_PORT:-8080}:80`. PostgreSQL and Redis have no host port mappings.
* **Production follow-up:** In a production deployment, expose NGINX through a controlled firewall/load balancer and use TLS.
* **How to verify:** Run:
  `docker compose ps`
  and verify that only `nginx` has a host port mapping.

## 3. Container User and Privileges

* **Risk and evidence:** Running the application as root would increase the impact of a container compromise.
* **Impact:** A successful application exploit could provide unnecessary root privileges inside the container.
* **Implemented fix / commit:** The Dockerfile creates a dedicated non-root user with UID/GID `10001` and switches to it using:
  `USER app`.
* **Production follow-up:** Apply additional container hardening such as a read-only root filesystem, dropped Linux capabilities, `no-new-privileges`, and stricter seccomp/AppArmor policies where compatible.
* **How to verify:** Run:
  `docker compose exec app-01 id`
  and verify that the process is running as the non-root `app` user.

## 4. Container Image Selection and Pinning

* **Risk and evidence:** Using untrusted, outdated, or mutable image tags can introduce supply-chain or reproducibility risks.
* **Impact:** A changed upstream image could introduce vulnerabilities or unexpected behavior.
* **Implemented fix / commit:** The final Compose configuration pins the PostgreSQL, Redis, and NGINX images using SHA256 digests. The Python application base image in the Dockerfile is also pinned by digest.
* **Production follow-up:** Continuously scan images for vulnerabilities, maintain an approved base-image policy, and regularly update pinned digests after security review.
* **How to verify:** Run:
  `docker compose config`
  and verify that the final images contain SHA256 digests.

## 5. Network Segmentation

* **Risk and evidence:** Allowing all containers to communicate on one unrestricted network would increase lateral movement opportunities.
* **Impact:** A compromised frontend component could potentially communicate directly with database/cache services.
* **Implemented fix / commit:** NGINX and applications use the `frontend` network. Applications, PostgreSQL, and Redis use the `backend` network. The backend network is marked `internal: true`.
* **Production follow-up:** Apply more granular network policies in production, such as Kubernetes NetworkPolicies or equivalent firewall controls.
* **How to verify:** Run:
  `docker network inspect barq-assessment_frontend`
  and:
  `docker network inspect barq-assessment_backend`
  and verify the expected container membership.

## 6. PostgreSQL Persistence and Backup

* **Risk and evidence:** Database data stored only inside a container filesystem would be lost when the container is removed.
* **Impact:** Container recreation could cause permanent application data loss.
* **Implemented fix / commit:** PostgreSQL uses the named `postgres-data` volume. Backup and restore scripts are also included to provide a reproducible recovery procedure.
* **Production follow-up:** Use scheduled automated backups, encrypted off-host storage, retention policies, and periodic restore testing.
* **How to verify:** Create a record through `/records`, recreate the PostgreSQL container while preserving the named volume, and verify that the record remains available. Execute the backup and restore procedures and verify the restored record.

## 7. Redis Persistence

* **Risk and evidence:** Redis-backed state such as the application counter could be lost if Redis has no persistence.
* **Impact:** Restarting or recreating Redis could reset application state.
* **Implemented fix / commit:** Redis uses a named `redis-data` volume with both RDB snapshots and AOF persistence
* **Production follow-up:** Decide whether Redis data is business-critical. For critical state, define backup/restore and replication requirements. For disposable cache data, persistence may not be necessary.
* **How to verify:** Increment `/counter`, restart/recreate Redis while preserving its volume, and verify the expected persisted state.

## 8. Availability and Failure Recovery

* **Risk and evidence:** A backend instance failure can reduce application capacity or cause errors if the reverse proxy cannot reach a healthy replacement.
* **Impact:** Users may experience failed requests or reduced availability.
* **Implemented fix / commit:** Two application instances run behind NGINX. Application healthchecks and restart policies are configured. A dedicated failure test verifies continued traffic and recovery after stopping one backend.
* **Production follow-up:** Use multiple availability zones, external load balancing, autoscaling, and stronger service-level monitoring for production workloads.
* **How to verify:** Stop one backend with:
  `docker compose stop app-01`
  then generate traffic through NGINX, measure successful/failed requests, restore the backend, and verify that `app-01` serves traffic again.

## 9. Health and Readiness Checks

* **Risk and evidence:** A process can be running while PostgreSQL or Redis is unavailable.
* **Impact:** Traffic may be sent to an application that cannot serve requests correctly.
* **Implemented fix / commit:** Application healthcheck verifies `/health`, while `/ready` verifies PostgreSQL and Redis readiness. PostgreSQL and Redis also have container healthchecks.
* **Production follow-up:** Use orchestration-aware readiness/liveness/startup probes and avoid sending traffic to instances that are not ready.
* **How to verify:** Run:
  `curl http://127.0.0.1:8080/health`
  and:
  `curl http://127.0.0.1:8080/ready`
  and confirm that `/ready` reports both PostgreSQL and Redis as ready.

## Completed Work vs Production Follow-up

### Completed

* Secrets are no longer copied into the application image.
* Secret files are ignored by Git.
* Application runs as a non-root user.
* Only NGINX is exposed on the host.
* PostgreSQL and Redis remain internal services.
* Frontend/backend network segmentation is configured.
* PostgreSQL uses persistent storage.
* Redis persistence is enabled.
* Images are pinned by digest.
* Resource limits and restart policies are configured.
* Application, PostgreSQL, and Redis health checks are configured.
* Historical logs are analyzed and correlated.
* Backend failure and recovery are tested.

### Planned Production Improvements

* Use a dedicated production secrets manager.
* Enable HTTPS/TLS with certificate management.
* Add metrics, dashboards, and alerting.
* Add automated scheduled PostgreSQL backups and off-host storage.
* Regularly perform restore drills.
* Add image vulnerability and dependency scanning to CI.
* Apply stronger container hardening such as dropped capabilities and read-only filesystems.
* Use multi-zone deployment and external load balancing for higher availability.
* Add network policies with least-privilege communication rules.
