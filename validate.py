#!/usr/bin/env python3

"""Validate the BARQ assessment environment."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")
MAX_WAIT = 30
REQUEST_TIMEOUT = 5
INSTANCE_CHECKS = 10

failed = False

def passed(message):
    print(f"PASS: {message}")


def failed_check(message):
    global failed
    failed = True
    print(f"FAIL: {message}")


def run_command(command):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
        )

        return result.returncode, result.stdout.strip(), result.stderr.strip()

    except (subprocess.TimeoutExpired, OSError) as exc:
        return 1, "", str(exc)


def http_request(method, path, data=None):
    url = f"{BASE_URL}{path}"

    headers = {
        "Content-Type": "application/json"
    }

    body = None

    if data is not None:
        body = json.dumps(data).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT
        ) as response:

            response_body = response.read().decode(
                "utf-8",
                errors="replace"
            )

            return response.status, response_body

    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(
            "utf-8",
            errors="replace"
        )

    except (urllib.error.URLError, socket.timeout) as exc:
        return None, str(exc)


def wait_for_endpoint(path):
    deadline = time.time() + MAX_WAIT

    while time.time() < deadline:

        status, body = http_request("GET", path)

        if status == 200:
            return status, body

        time.sleep(2)

    return None, "timeout"


def check_public_access():
    status, body = wait_for_endpoint("/")

    if status == 200 and body.strip():
        passed("Public access through NGINX is working")
        return True

    failed_check(
        f"Public access failed: HTTP {status} - {body}"
    )

    return False


def check_endpoint(path):
    status, body = wait_for_endpoint(path)

    if status == 200:
        passed(f"{path} returned HTTP 200")
        return True

    failed_check(
        f"{path} failed: HTTP {status} - {body}"
    )

    return False


def check_ready():
    status, body = wait_for_endpoint("/ready")

    if status != 200:
        failed_check(
            f"/ready failed: HTTP {status} - {body}"
        )
        return False

    passed(f"/ready returned HTTP 200: {body.strip()}")

    # If /ready returns JSON, inspect PostgreSQL and Redis states.
    try:
        data = json.loads(body)

        if isinstance(data, dict):

            postgres_status = str(
                data.get("postgres", "")
            ).lower()

            redis_status = str(
                data.get("redis", "")
            ).lower()

            if postgres_status:
                if postgres_status in (
                    "ready",
                    "healthy",
                    "ok",
                    "up",
                ):
                    passed("PostgreSQL readiness reported as healthy")
                else:
                    failed_check(
                        f"PostgreSQL readiness is: {postgres_status}"
                    )

            if redis_status:
                if redis_status in (
                    "ready",
                    "healthy",
                    "ok",
                    "up",
                ):
                    passed("Redis readiness reported as healthy")
                else:
                    failed_check(
                        f"Redis readiness is: {redis_status}"
                    )

    except json.JSONDecodeError:
        pass

    return True


def check_instance():
    status, body = http_request("GET", "/instance")

    if status == 200 and body.strip():
        passed(f"/instance returned: {body.strip()}")
        return body.strip()

    failed_check(
        f"/instance failed: HTTP {status} - {body}"
    )

    return None


def check_both_backends():
    instances = set()

    print(
        f"Checking backend distribution using "
        f"{INSTANCE_CHECKS} requests..."
    )

    for _ in range(INSTANCE_CHECKS):

        status, body = http_request("GET", "/instance")

        if status == 200 and body.strip():
            instances.add(body.strip())

        time.sleep(0.2)

    if "app-01" in instances:
        passed("app-01 served requests")
    else:
        failed_check(
            f"app-01 was not observed. Instances: {sorted(instances)}"
        )

    if "app-02" in instances:
        passed("app-02 served requests")
    else:
        failed_check(
            f"app-02 was not observed. Instances: {sorted(instances)}"
        )

    return "app-01" in instances and "app-02" in instances


def check_records():
    status, body = http_request(
        "POST",
        "/records",
        {
            "message": "validation-test"
        }
    )

    if status in (200, 201):
        passed(
            f"POST /records succeeded: HTTP {status}"
        )
        return True

    failed_check(
        f"POST /records failed: HTTP {status} - {body}"
    )

    return False


def check_counter():
    status, body = http_request(
        "GET",
        "/counter"
    )

    if status == 200 and body.strip():
        passed(
            f"/counter returned: {body.strip()}"
        )
        return True

    failed_check(
        f"/counter failed: HTTP {status} - {body}"
    )

    return False


def check_container_running(container):
    code, output, error = run_command(
        [
            "docker",
            "inspect",
            "-f",
            "{{.State.Running}}",
            container,
        ]
    )

    if code != 0:
        failed_check(
            f"container {container} does not exist or cannot be inspected"
        )
        return False

    if output == "true":
        passed(f"container {container} is running")
        return True

    failed_check(
        f"container {container} is not running"
    )

    return False


def check_container_health(container):
    code, output, error = run_command(
        [
            "docker",
            "inspect",
            "-f",
            "{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}",
            container,
        ]
    )

    if code != 0:
        failed_check(
            f"could not inspect health of {container}"
        )
        return False

    if output == "healthy":
        passed(f"{container} is healthy")
        return True

    if output == "no-healthcheck":
        failed_check(
            f"{container} has no Docker healthcheck"
        )
        return False

    failed_check(
        f"{container} health status is {output}"
    )

    return False


def check_host_ports():
    containers = [
        "nginx",
        "app-01",
        "app-02",
        "postgres",
        "redis",
    ]

    for container in containers:

        code, output, error = run_command(
            [
                "docker",
                "port",
                container,
            ]
        )

        if code != 0:
            failed_check(
                f"could not inspect ports for {container}"
            )
            continue

        if container == "nginx":

            if any(
                "127.0.0.1:8080" in line
                or "0.0.0.0:8080" in line
                or "[::]:8080" in line
                for line in output.splitlines()
            ):
                passed(
                    "NGINX publishes host port 8080"
                )
            else:
                failed_check(
                    f"NGINX does not publish host port 8080: {output}"
                )

        else:

            if output:
                failed_check(
                    f"{container} has a prohibited host port: {output}"
                )
            else:
                passed(
                    f"{container} has no published host port"
                )


def get_networks(container):
    code, output, error = run_command(
        [
            "docker",
            "inspect",
            "-f",
            "{{range $name, $network := .NetworkSettings.Networks}}{{$name}} {{end}}",
            container,
        ]
    )

    if code != 0:
        return set()

    return set(output.split())


def check_network_isolation():
    expected = {
        "nginx": {"frontend"},
        "app-01": {"frontend", "backend"},
        "app-02": {"frontend", "backend"},
        "postgres": {"backend"},
        "redis": {"backend"},
    }

    for container, expected_networks in expected.items():

        actual_networks = get_networks(container)

        if not actual_networks:
            failed_check(
                f"could not determine networks for {container}"
            )
            continue

        if actual_networks == expected_networks:
            passed(
                f"{container} networks are correct: "
                f"{sorted(actual_networks)}"
            )
        else:
            failed_check(
                f"{container} networks are incorrect. "
                f"Expected: {sorted(expected_networks)}, "
                f"Actual: {sorted(actual_networks)}"
            )

    nginx_networks = get_networks("nginx")

    if "backend" not in nginx_networks:
        passed(
            "NGINX is isolated from the backend network"
        )
    else:
        failed_check(
            "NGINX is connected to the backend network"
        )

    for container in ("postgres", "redis"):

        networks = get_networks(container)

        if "frontend" not in networks:
            passed(
                f"{container} is isolated from the frontend network"
            )
        else:
            failed_check(
                f"{container} is connected to the frontend network"
            )


def main():

    print("=" * 60)
    print("BARQ Assessment Environment Validation")
    print(f"Base URL: {BASE_URL}")
    print(f"Maximum wait: {MAX_WAIT} seconds")
    print("=" * 60)

    print("\n[1] PUBLIC ACCESS")

    check_public_access()

    print("\n[2] APPLICATION ENDPOINTS")

    check_endpoint("/health")
    check_ready()
    check_instance()
    check_records()
    check_counter()

    print("\n[3] BOTH BACKEND INSTANCES")

    check_both_backends()

    print("\n[4] DOCKER CONTAINERS")

    containers = [
        "nginx",
        "app-01",
        "app-02",
        "postgres",
        "redis",
    ]

    for container in containers:
        if check_container_running(container):
            check_container_health(container)

    print("\n[5] HOST PORT ISOLATION")

    check_host_ports()

    print("\n[6] NETWORK ISOLATION")

    check_network_isolation()

    print("\n" + "=" * 60)

    if failed:
        print("VALIDATION FAILED")
        sys.exit(1)

    print("VALIDATION PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()

