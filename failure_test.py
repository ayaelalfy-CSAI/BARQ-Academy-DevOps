#!/usr/bin/env python3

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter


BASE_URL = "http://localhost:8080"
BACKEND_TO_STOP = "app-01"

BASELINE_REQUESTS = 20
FAILURE_REQUESTS = 20
RECOVERY_REQUESTS = 20

REQUEST_TIMEOUT = 3
HEALTH_TIMEOUT = 30


def run_command(command):
    """Run a shell command and return success + output."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15
        )

        return (
            result.returncode == 0,
            result.stdout.strip(),
            result.stderr.strip()
        )

    except Exception as error:
        return False, "", str(error)


def request_instance():
    """Send GET /instance and return status + instance_id."""
    try:
        request = urllib.request.Request(
            f"{BASE_URL}/instance",
            method="GET"
        )

        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT
        ) as response:

            body = response.read().decode("utf-8")

            try:
                data = json.loads(body)
                instance_id = data.get("instance_id")
            except json.JSONDecodeError:
                instance_id = None

            return response.status, instance_id, body

    except urllib.error.HTTPError as error:
        return error.code, None, error.read().decode("utf-8")

    except Exception as error:
        return 0, None, str(error)


def send_traffic(number_of_requests):
    """Send multiple requests and collect traffic/error statistics."""

    results = []

    for _ in range(number_of_requests):
        status, instance_id, body = request_instance()

        results.append(
            {
                "status": status,
                "instance": instance_id,
                "body": body
            }
        )

        time.sleep(0.1)

    successful = [
        result
        for result in results
        if 200 <= result["status"] < 300
    ]

    errors = [
        result
        for result in results
        if not 200 <= result["status"] < 300
    ]

    instances = Counter(
        result["instance"]
        for result in successful
        if result["instance"]
    )

    total = len(results)
    success_count = len(successful)
    error_count = len(errors)

    error_rate = (
        (error_count / total) * 100
        if total
        else 100
    )

    return {
        "total": total,
        "successful": success_count,
        "errors": error_count,
        "error_rate": error_rate,
        "instances": instances,
        "errors_detail": errors
    }


def print_traffic(label, statistics):
    print(f"\n{label}")
    print("-" * 50)

    print(
        f"Total requests: {statistics['total']}"
    )

    print(
        f"Successful: {statistics['successful']}"
    )

    print(
        f"Errors: {statistics['errors']}"
    )

    print(
        f"Error rate: {statistics['error_rate']:.2f}%"
    )

    print("Backend distribution:")

    if statistics["instances"]:
        for instance, count in sorted(
            statistics["instances"].items()
        ):
            print(f"  {instance}: {count}")
    else:
        print("  No backend responses")


def check_container_running(container):
    success, stdout, _ = run_command(
        [
            "docker",
            "inspect",
            "-f",
            "{{.State.Running}}",
            container
        ]
    )

    return success and stdout == "true"


def wait_for_healthy(container):
    """Wait until a container reports healthy."""

    deadline = time.time() + HEALTH_TIMEOUT

    while time.time() < deadline:

        success, stdout, _ = run_command(
            [
                "docker",
                "inspect",
                "-f",
                "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
                container
            ]
        )

        if success and stdout == "healthy":
            return True

        time.sleep(1)

    return False


def stop_backend():
    print(
        f"\nStopping {BACKEND_TO_STOP}..."
    )

    success, _, stderr = run_command(
        [
            "docker",
            "stop",
            BACKEND_TO_STOP
        ]
    )

    if success:
        print(
            f"PASS: {BACKEND_TO_STOP} stopped"
        )
        return True

    print(
        f"FAIL: Could not stop {BACKEND_TO_STOP}"
    )

    if stderr:
        print(stderr)

    return False


def restore_backend():
    print(
        f"\nStarting {BACKEND_TO_STOP}..."
    )

    success, _, stderr = run_command(
        [
            "docker",
            "start",
            BACKEND_TO_STOP
        ]
    )

    if not success:
        print(
            f"FAIL: Could not start {BACKEND_TO_STOP}"
        )

        if stderr:
            print(stderr)

        return False

    print(
        f"PASS: {BACKEND_TO_STOP} started"
    )

    print(
        f"Waiting for {BACKEND_TO_STOP} to become healthy..."
    )

    if wait_for_healthy(BACKEND_TO_STOP):
        print(
            f"PASS: {BACKEND_TO_STOP} is healthy"
        )
        return True

    print(
        f"FAIL: {BACKEND_TO_STOP} did not become healthy "
        f"within {HEALTH_TIMEOUT} seconds"
    )

    return False


def main():

    print("=" * 60)
    print("BARQ Backend Failure / Recovery Test")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Backend to stop: {BACKEND_TO_STOP}")
    print("=" * 60)

    print("\n[1] PRE-CONDITION")

    for container in ("app-01", "app-02"):

        if check_container_running(container):
            print(
                f"PASS: {container} is running"
            )
        else:
            print(
                f"FAIL: {container} is not running"
            )
            sys.exit(1)

    print("\n[2] BASELINE TRAFFIC")

    baseline = send_traffic(
        BASELINE_REQUESTS
    )

    print_traffic(
        "Baseline traffic",
        baseline
    )

    if baseline["successful"] == 0:
        print(
            "FAIL: No successful baseline requests"
        )
        sys.exit(1)


    print("\n[3] FAILURE TEST")

    if not stop_backend():
        sys.exit(1)

    # Give Docker/NGINX a moment to detect the failure.
    time.sleep(2)

    if check_container_running(BACKEND_TO_STOP):
        print(
            f"FAIL: {BACKEND_TO_STOP} is still running"
        )
        sys.exit(1)

    print(
        f"PASS: {BACKEND_TO_STOP} is confirmed stopped"
    )

    print("\n[4] TRAFFIC DURING FAILURE")

    failure = send_traffic(
        FAILURE_REQUESTS
    )

    print_traffic(
        "Traffic while app-01 is stopped",
        failure
    )

    # The surviving backend must serve requests.
    app_02_requests = failure["instances"].get(
        "app-02",
        0
    )

    if app_02_requests > 0:
        print(
            f"PASS: app-02 served {app_02_requests} "
            f"requests while app-01 was down"
        )
    else:
        print(
            "FAIL: app-02 did not serve any requests "
            "during app-01 failure"
        )

        # Try to restore before exiting.
        restore_backend()
        sys.exit(1)

    if failure["successful"] > 0:
        print(
            "PASS: Service remained available "
            "during backend failure"
        )
    else:
        print(
            "FAIL: Service was unavailable "
            "during backend failure"
        )

        restore_backend()
        sys.exit(1)


    print("\n[5] BACKEND RECOVERY")

    if not restore_backend():
        sys.exit(1)


    print("\n[6] RECOVERY VERIFICATION")

    # Give NGINX a moment to recognize the recovered backend.
    time.sleep(2)

    recovery = send_traffic(
        RECOVERY_REQUESTS
    )

    print_traffic(
        "Traffic after app-01 recovery",
        recovery
    )

    app_01_requests = recovery["instances"].get(
        "app-01",
        0
    )

    if app_01_requests > 0:
        print(
            f"PASS: Recovered app-01 served "
            f"{app_01_requests} requests"
        )
    else:
        print(
            "FAIL: Recovered app-01 did not "
            "serve any requests"
        )
        sys.exit(1)

    if recovery["successful"] > 0:
        print(
            "PASS: Service is available after recovery"
        )
    else:
        print(
            "FAIL: Service unavailable after recovery"
        )
        sys.exit(1)


    print("\n" + "=" * 60)
    print("FAILURE TEST PASSED")
    print("=" * 60)

    print(
        "\nSummary:"
    )

    print(
        f"Baseline: {baseline['successful']}/"
        f"{baseline['total']} successful "
        f"({baseline['error_rate']:.2f}% errors)"
    )

    print(
        f"During failure: {failure['successful']}/"
        f"{failure['total']} successful "
        f"({failure['error_rate']:.2f}% errors)"
    )

    print(
        f"After recovery: {recovery['successful']}/"
        f"{recovery['total']} successful "
        f"({recovery['error_rate']:.2f}% errors)"
    )

    sys.exit(0)


if __name__ == "__main__":
    main()
