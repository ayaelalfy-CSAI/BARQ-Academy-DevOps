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

<img src="/assets/flowReqest.png" alt="flowRequest" width="900">


## Prerequisites

Install:

- Git
- Docker
- Docker Compose
- Python 3

Verify:

- git --version
- docker --version
- docker compose version
- python3 --version


## Setup

Clone the repository:

- git clone <REPOSITORY_URL>
- cd barq-academy

Create the environment file:

- cp .env.example .env

Edit .env and provide the required configuration:

- nano .env

Do not commit .env to Git.

Verify:

- git status

The .env file should not appear as a tracked file.


## Validate Docker Compose Configuration

Before starting the application:

- docker compose config

This verifies that the Compose configuration is valid and that the required environment variables are available.


## Build

Build all application images:

- docker compose build

To rebuild without using the Docker build cache:

- docker compose build --no-cache