## 1 / 2026-09-08 / 14:00 pm

- Symptom:
  Running `docker compose -p barq-assessment up --build -d` failed after 
  images were built and networks/volumes were created. Container creation 
  stopped with: "Conflict. The container name "/redis" is already in use by container "12683831cd105a9386ff8bd9b44b4253e6de2cfbf5bcaa0a6d8894d6f549c3c4". You have to remove (or rename) that container to be able to reuse that name.

- Hypothesis:
  A container named `redis` already exists on this machine from a previous 
  run or session, occupying the name required by this project's compose file.

- Command or test:
  docker ps -a --filter "name=redis"


- Actual output:
  12683831cd10   redis:7-alpine                        "docker-entrypoint.s…"   4 months ago     Exited (0) 13 days ago                                                                                                     redis


- Failed attempt and what changed your thinking:
  None - resolved on first fix attempt

- Root cause:
  Leftover container `redis` from a prior local run was not removed, 
  causing a name conflict with Docker's container-name uniqueness constraint.

- Fix:
  docker rm -f redis
  (then re-ran: docker compose -p barq-assessment up --build -d)

- Retest evidence:
   RUN : docker compose -p barq-assessment ps -a 
   the output is : redis      redis:7.4-alpine@sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf     "docker-entrypoint.s…"   redis      46 minutes ago      Up 27 minutes (healthy)     6379/tcp
  mean that redis is running and the error is solved.
 

- Related commit:
  N/A — environment-only change.

- Remaining uncertainty:
  None. The Redis container-name conflict was resolved and Redis connectivity was verified successfully.



## 2 / 2026-09-08  /  14:05 pm 

- Symptom:
  Running `docker compose -p barq-assessment up --build -d` failed after 
  images were built and networks/volumes were created. Container creation 
  stopped with: "Conflict. The container name "/nginx" is already in use by container "ddc4ca29b4c85fe551f42b32b805113ac8e7512f5cb7029d376f28e25beba23c". You have to remove (or rename) that container to be able to reuse that name.

- Hypothesis:
  A container named `nginx` already exists on this machine from a previous 
  run or session, occupying the name required by this project's compose file.

- Command or test:
  docker ps -a --filter "name=nginx"


- Actual output:
  ddc4ca29b4c8   nginx:alpine                          "/docker-entrypoint.…"   4 months ago     Exited (0) 13 days ago                                                                                                     nginx


- Failed attempt and what changed your thinking:
  None - resolved on first fix attempt

- Root cause:
  Leftover container `nginx` from a prior local run was not removed, 
  causing a name conflict with Docker's container-name uniqueness constraint.

- Fix:
  docker rm -f nginx
  (then re-ran: docker compose -p barq-assessment up --build -d)

- Retest evidence:
   RUN : docker compose -p barq-assessment up --build -d
   the output is : Error response from daemon: Conflict. The container name "/postgres" is already in use by container "98a15d79f00f6bcb6362c5eadc4ad2b5c44172e88118daa8033201fd733c4c27". You have to remove (or rename) that container to be able to reuse that name. 0.0s
Error response from daemon: Conflict. The container name "/postgres" is already in use by container "98a15d79f00f6bcb6362c5eadc4ad2b5c44172e88118daa8033201fd733c4c27". You have to remove (or rename) that container to be able to reuse that name.
(that mean i have a different error occure)
 

- Related commit:
  N/A — environment-only change.

- Remaining uncertainty:
  the port of the nginx 8080 i used for other container.


## 3 / 2026-09-08 / 14:10 pm

- Symptom:
  Running `docker compose -p barq-assessment up --build -d` failed after 
  images were built and networks/volumes were created. Container creation 
  stopped with: "Conflict.  The container name "/postgres" is already in use by container "98a15d79f00f6bcb6362c5eadc4ad2b5c44172e88118daa8033201fd733c4c27". You have to remove (or rename) that container to be able to reuse that name.

- Hypothesis:
  A container named `postgres` already exists on this machine from a previous 
  run or session, occupying the name required by this project's compose file.

- Command or test:
  docker ps -a --filter "name=postgres"


- Actual output:
  98a15d79f00f   postgres:16-alpine                 "docker-entrypoint.s…"   4 months ago   Up 43 hours (healthy)   0.0.0.0:5433->5432/tcp, [::]:5433->5432/tcp                                                    postgres


- Failed attempt and what changed your thinking:
  None - resolved on first fix attempt

- Root cause:
  Leftover container `postgres` from a prior local run was not removed, 
  causing a name conflict with Docker's container-name uniqueness constraint.

- Fix:
  docker rename postgres postgres-old

- Retest evidence:
   RUN : docker compose -p barq-assessment ps -a 
   the output is : postgres   postgres:16-alpine@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685   "docker-entrypoint.s…"   postgres   27 minutes ago      Up 27 minutes (healthy)     5432/tcp
  mean that redis is running and the error is solved.
 

- Related commit:
  N/A — environment-only change.

- Remaining uncertainty:
  None. The postgres container-name conflict was resolved and postgres connectivity was verified successfully.


## 4 / 2026-09-08  /  14:15 pm 

- Symptom:
  Running `docker compose -p barq-assessment up --build -d` failed after 
  images were built and networks/volumes were created. Container creation 
  stopped with: Error response from daemon: failed to set up container networking: driver failed programming external connectivity on endpoint nginx (effc197a120c2305631c7179167c26e52b9c89ac1d6950aea2b7bbed2f279831): Bind for 0.0.0.0:8080 failed: port is already allocated


- Hypothesis:
  there is a container uses this port

- Command or test:
  docker ps 


- Actual output:
  da335ff9f1d75   jenkins/jenkins:lts                "/usr/bin/tini -- /u…"   5 months ago   Up 43 hours             0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp, 0.0.0.0:50000->50000/tcp, [::]:50000->50000/tcp   jenkins


- Failed attempt and what changed your thinking:
  None - resolved on first fix attempt

- Root cause:
  the jenkins container used the same port 8080

- Fix:
  docker stop jenkins
  docker rm jenkins
  (then re-ran: docker compose -p barq-assessment up --build -d)

- Retest evidence:
  ✔ Image barq-assessment-app-01 Built                                              4.6s
 ✔ Image barq-assessment-app-02 Built                                              5.0s
 ✔ Container postgres           Running                                            0.0s
 ✔ Container redis              Running                                            0.0s
 ✔ Container app-01             Running                                            0.0s
 ✔ Container app-02             Running                                            0.0s
 ✔ Container nginx              Started  
 

- Related commit:
  N/A — environment-only change.

- Remaining uncertainty:
  None 


## 5 / 2026-09-08 / 16:40

- Symptom:
  `app-01` and `app-02` were running but reported as `unhealthy`.

- Hypothesis:
  The Docker healthcheck may be calling an endpoint that does not exist in the application.

- Command or test:
  `docker logs app-01`

- Actual output:
  {"timestamp": "2026-09-08T11:16:05.598+00:00", "level": "WARN", "service": "barq-api", "event": "http_request", "instance_id": "app-01", "request_id": "a1c07475a36b4a29ac4ed0dd80f74e00", "method": "GET", "path": "/healthz", "status": 404, "duration_ms": 0.953}
127.0.0.1 - - [08/Sep/2026 11:16:05] "GET /healthz HTTP/1.1" 404 -


- Failed attempt and what changed your thinking:
  The initial container status showed that the application containers were running, but they remained `unhealthy`. Inspecting the healthcheck output showed that the failure was an HTTP 404 rather than a container or dependency failure.

- Root cause:
  The Docker Compose healthcheck was configured to call `/healthz`, but `app/server.py` defines `/health` and does not define `/healthz`.

- Fix:
  Update the Docker Compose healthcheck endpoint from `/healthz` to `/health`.

- Retest evidence:
  first Ran `docker compose -p barq-assessment up -d` to recreate the app-01 and app-02 
  and then Ran  `docker compose -p barq-assessment ps -a`
  and this is the output 
NAME       IMAGE                                                                                        COMMAND                  SERVICE    CREATED          STATUS                    PORTS
app-01     barq-assessment-app-01                                                                       "python -m app.server"   app-01     20 seconds ago   Up 18 seconds (healthy)   8080/tcp
app-02     barq-assessment-app-02                                                                       "python -m app.server"   app-02     20 seconds ago   Up 18 seconds (healthy)   8080/tcp
nginx      nginx:1.28-alpine@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236    "/docker-entrypoint.…"   nginx      19 seconds ago   Up 17 seconds             80/tcp, 127.0.0.1:8080->81/tcp
postgres   postgres:16-alpine@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685   "docker-entrypoint.s…"   postgres   3 hours ago      Up 3 hours (healthy)      5432/tcp
redis      redis:7.4-alpine@sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf     "docker-entrypoint.s…"   redis      3 hours ago      Up 3 hours (healthy)      6379/tcp


- Related commit:
  5fb5fb8   fix: change healthcheck endpoint from healthz to health

- Remaining uncertainty:
  `APP_HOST` is currently configured as `127.0.0.1`. Whether this prevents NGINX from reaching the application over the Docker network still needs to be tested separately.
