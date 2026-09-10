#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")
MAX_WAIT = 30
REQUEST_TIMEOUT = 5
INSTANCE_CHECKS = 10

failures = []


def passed(message):
    print(f"PASS: {message}")


def failed_check(message):
    print(f"FAIL: {message}")
    failures.append(message)


def http_request(method, path, payload=None):
    url = f"{BASE_URL}{path}"

    data = None

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT
        ) as response:
            body = response.read().decode("utf-8")
            return response.status, body

    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        return error.code, body

    except Exception as error:
        return 0, str(error)


def wait_for_endpoint(path):
    deadline = time.time() + MAX_WAIT

    while time.time() < deadline:
        status, body = http_request("GET", path)

        if status == 200:
            return status, body

        time.sleep(1)

    return status, body


def check_public_access():
    status, body = wait_for_endpoint("/health")

    if status == 200:
        passed("Public access through NGINX is working")
        return True

    failed_check(
        f"Public access failed: HTTP {status} - {body}"
    )
    return False



def check_application_endpoints():
    success = True

    # /health
    status, body = http_request("GET", "/health")

    if status == 200:
        passed("/health returned HTTP 200")
    else:
        failed_check(
            f"/health failed: HTTP {status} - {body}"
        )
        success = False

    # /ready
    status, body = http_request("GET", "/ready")

    if status == 200:
        try:
            data = json.loads(body)

            postgres_status = data.get(
                "dependencies", {}
            ).get("postgres")

            redis_status = data.get(
                "dependencies", {}
            ).get("redis")

            if postgres_status == "ready":
                passed("PostgreSQL readiness check passed")
            else:
                failed_check(
                    f"PostgreSQL is not ready: {postgres_status}"
                )
                success = False

            if redis_status == "ready":
                passed("Redis readiness check passed")
            else:
                failed_check(
                    f"Redis is not ready: {redis_status}"
                )
                success = False

            passed(f"/ready returned HTTP 200: {body}")

        except json.JSONDecodeError:
            failed_check(
                f"/ready returned invalid JSON: {body}"
            )
            success = False

    else:
        failed_check(
            f"/ready failed: HTTP {status} - {body}"
        )
        success = False

    # /instance
    status, body = http_request("GET", "/instance")

    if status == 200:
        try:
            data = json.loads(body)
            instance_id = data.get("instance_id")

            if instance_id:
                passed(
                    f"/instance returned: {body}"
                )
            else:
                failed_check(
                    f"/instance missing instance_id: {body}"
                )
                success = False

        except json.JSONDecodeError:
            failed_check(
                f"/instance returned invalid JSON: {body}"
            )
            success = False

    else:
        failed_check(
            f"/instance failed: HTTP {status} - {body}"
        )
        success = False

    # /records
    status, body = http_request(
        "POST",
        "/records",
        {
            "title": "validation-test"
        }
    )

    if status in (200, 201):
        passed(
            f"POST /records succeeded: HTTP {status}"
        )
    else:
        failed_check(
            f"POST /records failed: HTTP {status} - {body}"
        )
        success = False

    # /counter
    status, body = http_request("GET", "/counter")

    if status == 200:
        passed(
            f"/counter returned: {body}"
        )
    else:
        failed_check(
            f"/counter failed: HTTP {status} - {body}"
        )
        success = False

    return success


def check_both_backends():
    instances = set()

    print(
        f"Checking backend distribution using "
        f"{INSTANCE_CHECKS} requests..."
    )

    for _ in range(INSTANCE_CHECKS):
        status, body = http_request(
            "GET",
            "/instance"
        )

        if status == 200 and body.strip():

            try:
                data = json.loads(body)

                instance_id = data.get("instance_id")

                if instance_id:
                    instances.add(instance_id)

            except json.JSONDecodeError:
                failed_check(
                    f"/instance returned invalid JSON: {body}"
                )

        time.sleep(0.2)

    if "app-01" in instances:
        passed("app-01 served requests")
    else:
        failed_check(
            f"app-01 was not observed. "
            f"Instances: {sorted(instances)}"
        )

    if "app-02" in instances:
        passed("app-02 served requests")
    else:
        failed_check(
            f"app-02 was not observed. "
            f"Instances: {sorted(instances)}"
        )

    return (
        "app-01" in instances
        and "app-02" in instances
    )


def docker_inspect(container, format_string):
    try:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                format_string,
                container
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return None

        return result.stdout.strip()

    except Exception:
        return None


def check_containers():
    containers = [
        "nginx",
        "app-01",
        "app-02",
        "postgres",
        "redis"
    ]

    success = True

    for container in containers:

        running = docker_inspect(
            container,
            "{{.State.Running}}"
        )

        if running == "true":
            passed(
                f"container {container} is running"
            )
        else:
            failed_check(
                f"container {container} is not running"
            )
            success = False

        health = docker_inspect(
            container,
            "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}"
        )

        if health == "healthy":
            passed(
                f"{container} is healthy"
            )
        else:
            failed_check(
                f"{container} health status: {health}"
            )
            success = False

    return success


def get_ports(container):
    try:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{json .NetworkSettings.Ports}}",
                container
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return None

        return json.loads(result.stdout)

    except Exception:
        return None


def check_host_ports():
    success = True

    # NGINX must publish 8080
    nginx_ports = get_ports("nginx")

    if nginx_ports and nginx_ports.get("80/tcp"):
        passed("NGINX publishes host port 8080")
    else:
        failed_check(
            "NGINX does not publish host port 8080"
        )
        success = False

    # These services must NOT publish host ports
    for container in [
        "app-01",
        "app-02",
        "postgres",
        "redis"
    ]:

        ports = get_ports(container)

        has_published_ports = any(
            value
            for value in (ports or {}).values()
            if value
        )

        if not has_published_ports:
            passed(
                f"{container} has no published host port"
            )
        else:
            failed_check(
                f"{container} has published host ports: "
                f"{ports}"
            )
            success = False

    return success


def get_networks(container):
    try:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{json .NetworkSettings.Networks}}",
                container
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return set()

        networks = json.loads(result.stdout)

        return set(networks.keys())

    except Exception:
        return set()


def normalize_networks(networks):
    logical_networks = set()

    for network in networks:

        if network.endswith("_frontend"):
            logical_networks.add("frontend")

        elif network.endswith("_backend"):
            logical_networks.add("backend")

        else:
            logical_networks.add(network)

    return logical_networks


def check_network_isolation():

    expected = {
        "nginx": {"frontend"},
        "app-01": {"frontend", "backend"},
        "app-02": {"frontend", "backend"},
        "postgres": {"backend"},
        "redis": {"backend"},
    }

    success = True

    for container, expected_networks in expected.items():

        actual_networks = get_networks(container)

        logical_networks = normalize_networks(
            actual_networks
        )

        if logical_networks == expected_networks:

            passed(
                f"{container} networks are correct: "
                f"{sorted(logical_networks)}"
            )

        else:

            failed_check(
                f"{container} networks are incorrect. "
                f"Expected: {sorted(expected_networks)}, "
                f"Actual: {sorted(logical_networks)}"
            )

            success = False

    # NGINX must NOT access backend
    nginx_networks = get_networks("nginx")

    nginx_has_backend = any(
        network.endswith("_backend")
        for network in nginx_networks
    )

    if not nginx_has_backend:

        passed(
            "NGINX is isolated from the backend network"
        )

    else:

        failed_check(
            "NGINX is connected to the backend network"
        )

        success = False

    # PostgreSQL and Redis must NOT access frontend
    for container in ("postgres", "redis"):

        networks = get_networks(container)

        has_frontend = any(
            network.endswith("_frontend")
            for network in networks
        )

        if not has_frontend:

            passed(
                f"{container} is isolated from the frontend network"
            )

        else:

            failed_check(
                f"{container} is connected to the frontend network"
            )

            success = False

    return success


def main():

    print("=" * 60)
    print("BARQ Assessment Environment Validation")
    print(f"Base URL: {BASE_URL}")
    print(f"Maximum wait: {MAX_WAIT} seconds")
    print("=" * 60)
    print()

    print("[1] PUBLIC ACCESS")
    check_public_access()
    print()

    print("[2] APPLICATION ENDPOINTS")
    check_application_endpoints()
    print()

    print("[3] BOTH BACKEND INSTANCES")
    check_both_backends()
    print()

    print("[4] DOCKER CONTAINERS")
    check_containers()
    print()

    print("[5] HOST PORT ISOLATION")
    check_host_ports()
    print()

    print("[6] NETWORK ISOLATION")
    check_network_isolation()
    print()

    print("=" * 60)

    if failures:
        print("VALIDATION FAILED")
        print(f"Total failures: {len(failures)}")
        sys.exit(1)

    print("VALIDATION PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()