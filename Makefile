# ──────────────────────────────────────────────────────────────────────────────
# NexaCommerce Analytics Platform - Makefile
# ──────────────────────────────────────────────────────────────────────────────
# Docker-focused commands for easy development and deployment
#
# Usage:
#   make [target]
#
# Examples:
#   make up          - Start all services
#   make down        - Stop all services
#   make logs        - View logs
#   make test        - Run tests
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: help up down restart logs build clean test shell pipeline dbt streaming

# ──────────────────────────────────────────────────────────────────────────────
# Variables
# ──────────────────────────────────────────────────────────────────────────────

DOCKER_COMPOSE := docker compose
DOCKER := docker
IMAGE_NAME := nexacommerce-analytics
CONTAINER_NAME := nexacommerce-app

# ──────────────────────────────────────────────────────────────────────────────
# Default Target
# ──────────────────────────────────────────────────────────────────────────────

help: ## Show this help message
	@echo "NexaCommerce Analytics Platform - Available Commands"
	@echo "═══════════════════════════════════════════════════════════════════"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m  %s\n", $$1, $$2}'
	@echo ""
	@echo "═══════════════════════════════════════════════════════════════════"

# ──────────────────────────────────────────────────────────────────────────────
# Docker Compose Commands
# ──────────────────────────────────────────────────────────────────────────────

up: ## Start all services in background
	@echo "Starting all services..."
	$(DOCKER_COMPOSE) up -d
	@echo ""
	@echo "Dashboard will be available at: http://localhost:8501"
	@echo "PostgreSQL: localhost:5432"
	@echo "Redis: localhost:6379"

up-streaming: ## Start with streaming simulation
	@echo "Starting services with streaming..."
	$(DOCKER_COMPOSE) --profile streaming up -d

up-dev: ## Start in foreground with logs
	$(DOCKER_COMPOSE) up

down: ## Stop all services
	@echo "Stopping all services..."
	$(DOCKER_COMPOSE) down

down-clean: ## Stop and remove volumes (reset data)
	@echo "Stopping all services and removing volumes..."
	$(DOCKER_COMPOSE) down -v

restart: ## Restart all services
	@echo "Restarting all services..."
	$(DOCKER_COMPOSE) restart

logs: ## View logs (follow mode)
	$(DOCKER_COMPOSE) logs -f

logs-app: ## View app logs only
	$(DOCKER_COMPOSE) logs -f app

logs-db: ## View database logs
	$(DOCKER_COMPOSE) logs -f postgres

# ──────────────────────────────────────────────────────────────────────────────
# Build Commands
# ──────────────────────────────────────────────────────────────────────────────

build: ## Build Docker image
	@echo "Building Docker image..."
	$(DOCKER) build -t $(IMAGE_NAME):latest .

build-no-cache: ## Build without cache
	@echo "Building Docker image (no cache)..."
	$(DOCKER) build --no-cache -t $(IMAGE_NAME):latest .

build-prod: ## Build production image (smaller size)
	@echo "Building production image..."
	$(DOCKER) build --target production -t $(IMAGE_NAME):prod .

build-dev: ## Build development image
	@echo "Building development image..."
	$(DOCKER) build --target development -t $(IMAGE_NAME):dev .

rebuild: down build up ## Rebuild and restart

# ──────────────────────────────────────────────────────────────────────────────
# Testing Commands
# ──────────────────────────────────────────────────────────────────────────────

test: ## Run tests in Docker
	@echo "Running tests..."
	$(DOCKER_COMPOSE) --profile test up --abort-on-container-exit test

test-cov: ## Run tests with coverage report
	@echo "Running tests with coverage..."
	$(DOCKER_COMPOSE) --profile test up --abort-on-container-exit test
	@echo "Coverage report generated in htmlcov/"

test-fast: ## Run tests quickly (no coverage)
	@echo "Running tests (fast mode)..."
	$(DOCKER_COMPOSE) --profile test up --abort-on-container-exit test -- -v

# ──────────────────────────────────────────────────────────────────────────────
# Pipeline Commands
# ──────────────────────────────────────────────────────────────────────────────

pipeline: ## Run data pipeline
	@echo "Running data pipeline..."
	$(DOCKER_COMPOSE) --profile pipeline up --abort-on-container-exit pipeline

pipeline-force: ## Force re-run data pipeline
	@echo "Force running data pipeline (removing existing data)..."
	$(DOCKER_COMPOSE) down -v
	$(DOCKER_COMPOSE) --profile pipeline up --abort-on-container-exit pipeline

# ──────────────────────────────────────────────────────────────────────────────
# dbt Commands
# ──────────────────────────────────────────────────────────────────────────────

dbt: ## Run dbt models
	@echo "Running dbt models..."
	$(DOCKER_COMPOSE) --profile dbt up --abort-on-container-exit dbt

dbt-test: ## Run dbt tests
	@echo "Running dbt tests..."
	$(DOCKER_COMPOSE) --profile dbt run dbt test

dbt-docs: ## Generate and serve dbt docs
	@echo "Generating dbt documentation..."
	$(DOCKER_COMPOSE) --profile dbt run dbt docs generate
	$(DOCKER_COMPOSE) --profile dbt up -d dbt-docs

# ──────────────────────────────────────────────────────────────────────────────
# Streaming Commands
# ──────────────────────────────────────────────────────────────────────────────

streaming: ## Start streaming simulation
	@echo "Starting streaming simulation..."
	$(DOCKER_COMPOSE) --profile streaming up -d streaming

streaming-stop: ## Stop streaming simulation
	@echo "Stopping streaming simulation..."
	$(DOCKER_COMPOSE) stop streaming

# ──────────────────────────────────────────────────────────────────────────────
# Shell/Debug Commands
# ──────────────────────────────────────────────────────────────────────────────

shell: ## Open shell in app container
	@echo "Opening shell in app container..."
	$(DOCKER_COMPOSE) exec app bash

shell-root: ## Open shell as root
	@echo "Opening shell as root..."
	$(DOCKER_COMPOSE) exec --user root app bash

ps: ## Show running containers
	$(DOCKER_COMPOSE) ps

stats: ## Show resource usage
	$(DOCKER_COMPOSE) top

# ──────────────────────────────────────────────────────────────────────────────
# Clean Commands
# ──────────────────────────────────────────────────────────────────────────────

clean: ## Remove containers and networks
	@echo "Cleaning up containers and networks..."
	$(DOCKER_COMPOSE) down

clean-all: ## Remove everything including volumes
	@echo "Removing everything (containers, networks, volumes)..."
	$(DOCKER_COMPOSE) down -v
	$(DOCKER) system prune -f

clean-images: ## Remove all images
	@echo "Removing all Docker images..."
	$(DOCKER) image prune -a -f

# ──────────────────────────────────────────────────────────────────────────────
# Development Commands
# ──────────────────────────────────────────────────────────────────────────────

lint: ## Run linters
	@echo "Running linters..."
	$(DOCKER_COMPOSE) --profile test run --rm test flake8 src/

format: ## Format code
	@echo "Formatting code..."
	$(DOCKER_COMPOSE) --profile test run --rm test black src/
	$(DOCKER_COMPOSE) --profile test run --rm test isort src/

type-check: ## Run type checking
	@echo "Running type checking..."
	$(DOCKER_COMPOSE) --profile test run --rm test mypy src/

# ──────────────────────────────────────────────────────────────────────────────
# Deployment Commands
# ──────────────────────────────────────────────────────────────────────────────

push: ## Push image to registry (set REGISTRY variable)
ifndef REGISTRY
	$(error REGISTRY is not set. Usage: make push REGISTRY=your-registry.com)
endif
	@echo "Pushing image to $(REGISTRY)..."
	$(DOCKER) tag $(IMAGE_NAME):latest $(REGISTRY)/$(IMAGE_NAME):latest
	$(DOCKER) push $(REGISTRY)/$(IMAGE_NAME):latest

deploy: build-prod ## Deploy to production (build prod image)
	@echo "Production image built: $(IMAGE_NAME):prod"
	@echo "To deploy, push to your registry and update deployment config"

# ──────────────────────────────────────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────────────────────────────────────

health: ## Check service health
	@echo "Checking service health..."
	@echo ""
	@echo "App Container:"
	$(DOCKER_COMPOSE) ps app
	@echo ""
	@echo "PostgreSQL:"
	$(DOCKER_COMPOSE) ps postgres
	@echo ""
	@echo "Redis:"
	$(DOCKER_COMPOSE) ps redis
	@echo ""
	@echo "Dashboard Health Check:"
	@curl -s http://localhost:8501/_stcore/health && echo "✓ Healthy" || echo "✗ Unhealthy"

# ──────────────────────────────────────────────────────────────────────────────
# Version Info
# ──────────────────────────────────────────────────────────────────────────────

version: ## Show version info
	@echo "Docker Version:"
	$(DOCKER) --version
	@echo ""
	@echo "Docker Compose Version:"
	$(DOCKER_COMPOSE) version
	@echo ""
	@echo "Image Info:"
	$(DOCKER) images $(IMAGE_NAME) || echo "Image not built yet"
