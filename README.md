# 🛒 NexaCommerce Analytics Intelligence Platform

> **Enterprise-Grade E-Commerce Analytics:** Predictive ML · Real-Time Streaming · Causal Inference · Advanced Experimentation · Feature Store

**Python Version:** 3.12.5 | **Container:** Docker & Docker Compose

---

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [All Methods to Run](#-all-methods-to-run)
- [Architecture](#-architecture)
- [Features](#-features)
- [Configuration](#-configuration)
- [Development](#-development)
- [Testing](#-testing)
- [dbt Setup](#-dbt-setup)
- [Deployment](#-deployment)
- [Troubleshooting](#-troubleshooting)

---

## 🚀 Quick Start

### Method 1: Docker Compose (Recommended - Fastest)

```bash
# Start all services (Dashboard + PostgreSQL + Redis)
docker compose up -d

# View logs
docker compose logs -f app

# Access dashboard at http://localhost:8501
```

### Method 2: Makefile (Convenient Commands)

```bash
# Start all services
make up

# View logs
make logs

# Stop all services
make down
```

### Method 3: Local Python Environment

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full pipeline
python run_pipeline.py

# Launch dashboard
streamlit run src/dashboard/app.py --server.port 8501
```

---

## 🎯 All Methods to Run the Project

### Overview Table

| Method | Best For | Commands |
|--------|----------|----------|
| **Docker Compose** | Production-like environment | `docker compose up -d` |
| **Makefile** | Quick development commands | `make up`, `make test` |
| **Local Python** | Development & debugging | `python run_pipeline.py` |
| **Docker Manual** | Custom deployments | `docker build` + `docker run` |
| **Individual Services** | Component testing | See sections below |

---

## 1️⃣ Docker Compose Methods

### 1.1 Start All Services (Background)

```bash
# Start app, postgres, redis
docker compose up -d

# Check status
docker compose ps

# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f app
docker compose logs -f postgres
docker compose logs -f redis
```

### 1.2 Start with Streaming Simulation

```bash
# Enable real-time transaction streaming
docker compose --profile streaming up -d

# Stop streaming only
docker compose stop streaming
```

### 1.3 Run Data Pipeline

```bash
# Run one-time data generation pipeline
docker compose --profile pipeline up --abort-on-container-exit

# Force re-run (removes existing data first)
docker compose down -v
docker compose --profile pipeline up --abort-on-container-exit
```

### 1.4 Run dbt Transformations

```bash
# Execute dbt models
docker compose --profile dbt up --abort-on-container-exit

# Run dbt tests
docker compose --profile dbt run dbt test

# Generate dbt documentation
docker compose --profile dbt run dbt docs generate
```

### 1.5 Run Tests

```bash
# Run all tests with coverage
docker compose --profile test up --abort-on-container-exit

# Run specific test file
docker compose --profile test up --abort-on-container-exit \
  --command "pytest tests/test_analytics.py -v"

# Run tests with HTML coverage report
docker compose --profile test up --abort-on-container-exit \
  --command "pytest tests/ --cov=src --cov-report=html"
```

### 1.6 Stop and Clean

```bash
# Stop all services
docker compose down

# Stop and remove volumes (complete reset)
docker compose down -v

# Remove everything including images
docker compose down -v
docker system prune -f
```

---

## 2️⃣ Makefile Methods

### 2.1 Basic Operations

```bash
# Show all available commands
make help

# Start all services in background
make up

# Start with streaming
make up-streaming

# Stop all services
make down

# Restart services
make restart

# Complete reset (remove volumes)
make down-clean
```

### 2.2 Build Operations

```bash
# Build Docker image
make build

# Build without cache
make build-no-cache

# Build production image (smaller)
make build-prod

# Build development image
make build-dev

# Rebuild and restart
make rebuild
```

### 2.3 Testing Operations

```bash
# Run tests
make test

# Run tests with coverage
make test-cov

# Run tests quickly (no coverage)
make test-fast

# Run linters
make lint

# Format code
make format

# Run type checking
make type-check
```

### 2.4 Pipeline Operations

```bash
# Run data pipeline
make pipeline

# Force re-run pipeline
make pipeline-force

# Run dbt models
make dbt

# Run dbt tests
make dbt-test

# Generate dbt docs
make dbt-docs
```

### 2.5 Streaming Operations

```bash
# Start streaming
make streaming

# Stop streaming
make streaming-stop
```

### 2.6 Debug Operations

```bash
# Open shell in app container
make shell

# Open shell as root
make shell-root

# Show running containers
make ps

# Show resource usage
make stats

# Check service health
make health

# Show version info
make version
```

### 2.7 Logging Operations

```bash
# View all logs
make logs

# View app logs only
make logs-app

# View database logs
make logs-db
```

### 2.8 Clean Operations

```bash
# Remove containers and networks
make clean

# Remove everything including volumes
make clean-all

# Remove all images
make clean-images
```

---

## 3️⃣ Local Python Environment Methods

### 3.1 Prerequisites

```bash
# Check Python version (requires 3.12.5)
python --version

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
.\venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate
```

### 3.2 Install Dependencies

```bash
# Install all dependencies
pip install -r requirements.txt

# Verify installation
pip list
```

### 3.3 Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
# Key variables:
# - DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
# - LOG_LEVEL, STREAMLIT_PORT
```

### 3.4 Run Full Pipeline

```bash
# Execute end-to-end pipeline
python run_pipeline.py

# This runs:
# 1. Data Generation (Bronze Layer)
# 2. Data Validation (Great Expectations)
# 3. RFM Segmentation (Silver Layer)
# 4. A/B Testing Analysis
# 5. Predictive ML Models (Churn, CLV, Survival, Recommendations)
# 6. Feature Store Registration
# 7. Report Generation
```

### 3.5 Launch Dashboard

```bash
# Start Streamlit dashboard
streamlit run src/dashboard/app.py --server.port 8501

# Dashboard will be available at http://localhost:8501
```

### 3.6 Run Individual Components

```bash
# Run data generation only
python -m src.data_generation.generate_data

# Run RFM segmentation
python -m src.rfm_segmentation.rfm_engine

# Run A/B testing analysis
python -m src.ab_testing.ab_engine

# Train churn model
python -c "from src.predictive.churn_model import train_churn_model; train_churn_model()"

# Train CLV model
python -c "from src.predictive.clv_model import train_clv_model; train_clv_model()"

# Train survival model
python -c "from src.predictive.survival_analysis import train_survival_model; train_survival_model()"

# Train recommendation engine
python -c "from src.predictive.recommendation_engine import train_recommendation_model; train_recommendation_model()"

# Start streaming simulation
python -c "from src.streaming import start_streaming; start_streaming()"

# Run dbt transformations
dbt run

# Run dbt tests
dbt test
```

### 3.7 Run Tests Locally

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Run with HTML coverage report
pytest tests/ -v --cov=src --cov-report=html

# Run specific test file
pytest tests/test_analytics.py -v

# Run specific test function
pytest tests/test_analytics.py::test_specific_function -v

# Run only unit tests
pytest tests/ -v -m unit

# Run only integration tests
pytest tests/ -v -m integration

# Skip slow tests
pytest tests/ -v -m "not slow"
```

### 3.8 Code Quality Checks

```bash
# Run linters
flake8 src/
black src/ --check
isort src/ --check

# Format code
black src/
isort src/

# Run type checking
mypy src/
```

---

## 4️⃣ Manual Docker Build & Run Methods

### 4.1 Build and Run Manually

```bash
# Build the Docker image
docker build -t nexacommerce-analytics:latest .

# Run the container
docker run -d \
  -p 8501:8501 \
  -v app_data:/app/data \
  -v app_models:/app/models \
  --name nexacommerce \
  nexacommerce-analytics:latest

# Access dashboard at http://localhost:8501

# Stop and remove container
docker stop nexacommerce
docker rm nexacommerce
```

### 4.2 Build Production Image

```bash
# Build production-only image (smaller size)
docker build --target production -t nexacommerce-analytics:prod .

# Check image size
docker images nexacommerce-analytics:prod

# Scan for vulnerabilities
docker scan nexacommerce-analytics:prod
```

### 4.3 Build Development Image

```bash
# Build development image with all tools
docker build --target development -t nexacommerce-analytics:dev .
```

### 4.4 Run with Custom Configuration

```bash
# Run with custom environment variables
docker run -d \
  -p 8502:8502 \
  -e STREAMLIT_SERVER_PORT=8502 \
  -e DB_HOST=my-postgres-server \
  -e DB_PASSWORD=custom_password \
  --name nexacommerce-custom \
  nexacommerce-analytics:latest
```

### 4.5 Run Interactive Container

```bash
# Run interactive bash session
docker run -it --rm \
  -v $(pwd):/app \
  nexacommerce-analytics:latest \
  bash

# Run single command
docker run --rm \
  nexacommerce-analytics:latest \
  python run_pipeline.py
```

---

## 5️⃣ Hybrid Methods (Docker + Local)

### 5.1 Docker Database + Local Application

```bash
# Start only database services
docker compose up -d postgres redis

# Run application locally (will connect to Docker containers)
export DB_HOST=localhost
export REDIS_HOST=localhost
python run_pipeline.py

# Launch dashboard locally
streamlit run src/dashboard/app.py --server.port 8501
```

### 5.2 Docker Services + Local Code Mounting

```bash
# Start services with local code mounted
docker compose up -d app postgres redis

# The docker-compose.yml already mounts:
# - ./config:/app/config:ro
# - ./src:/app/src:ro
# - ./run_pipeline.py:/app/run_pipeline.py:ro

# Changes to local files will be reflected in the container
```

---

## 🏗️ Architecture

### Complete Stack Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Docker Compose Stack                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │   Streamlit  │────▶│   PostgreSQL │     │    Redis     │                │
│  │   Dashboard  │     │   Database   │     │    Cache     │                │
│  │   :8501      │     │    :5432     │     │    :6379     │                │
│  └──────────────┘     └──────────────┘     └──────────────┘                │
│         ▲                    ▲                    ▲                         │
│         │                    │                    │                         │
│  ┌──────┴────────────────────┴────────────────────┴──────┐                │
│  │                  Docker Network                        │                │
│  │              (nexacommerce-network)                    │                │
│  └────────────────────────────────────────────────────────┘                │
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │  Streaming   │     │     dbt      │     │    Test      │                │
│  │   Service    │     │   Runner     │     │    Runner    │                │
│  │  (optional)  │     │  (optional)  │     │  (optional)  │                │
│  └──────────────┘     └──────────────┘     └──────────────┘                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### File Structure

```
ecommerce_analytics/
├── Dockerfile                    # Multi-stage production build
├── docker-compose.yml            # Full stack orchestration
├── Makefile                      # Convenient commands
├── .dockerignore                 # Exclude files from build
├── .env.example                  # Environment template
├── requirements.txt              # Python 3.12.5 dependencies
├── run_pipeline.py               # Main pipeline entry point
├── config/
│   └── settings.py               # Application configuration
├── src/
│   ├── data_generation/          # Synthetic data generation
│   ├── database/                 # Database connections
│   ├── rfm_segmentation/         # RFM customer segmentation
│   ├── ab_testing/               # A/B testing analysis
│   ├── predictive/               # ML models (Churn, CLV, Survival)
│   ├── streaming/                # Real-time processing
│   ├── causal/                   # Causal inference
│   ├── reports/                  # Decision engine
│   ├── pipeline/                 # Orchestration
│   └── dashboard/                # Streamlit UI
├── dbt/                          # dbt transformations
├── tests/                        # pytest suite
└── sql/
    └── init.sql                  # Database initialization
```

---

## 🏆 Features

| Category | Features |
|----------|----------|
| 🤖 **Predictive ML** | Churn Prediction (XGBoost + SHAP), Survival Analysis, BG/NBD + Gamma-Gamma CLV, Product Recommendations (ALS) |
| ⚡ **Real-Time** | Kafka-like streaming simulation, Live RFM updates, Auto-refreshing dashboard |
| 🧪 **Experimentation** | Sequential Testing (mSPRT), Thompson Sampling Bandits, CUPED Variance Reduction, SRM Detection |
| 🔬 **Causal Inference** | Propensity Score Matching, Difference-in-Differences, Synthetic Control |
| 📊 **Decision Engine** | CUSUM Anomaly Detection, What-If Simulator, Cohort Retention, Auto-Narratives |
| 🏗️ **Engineering** | Prefect Orchestration, dbt Transformations, Feast Feature Store, Great Expectations |

---

## 🔧 Configuration

### Environment Variables

```bash
# Copy template
cp .env.example .env
```

### Key Variables

```bash
# PostgreSQL Database
DB_HOST=localhost          # Use 'postgres' in Docker network
DB_PORT=5432
DB_NAME=ecommerce_analytics
DB_USER=analytics_user
DB_PASSWORD=analytics_pass

# Redis Cache
REDIS_HOST=localhost       # Use 'redis' in Docker network
REDIS_PORT=6379

# Streamlit Dashboard
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Logging
LOG_LEVEL=INFO

# Data Generation
N_CUSTOMERS=15000
N_PRODUCTS=500
N_TRANSACTIONS=180000
```

---

## 🗄️ dbt Setup

### Prerequisites

dbt (data build tool) is used for data transformation pipelines. You need:
- PostgreSQL database running
- dbt Core installed

### Install dbt

```bash
# Add dbt to requirements (already included)
pip install dbt-core==1.8.0 dbt-postgres==1.8.0

# Or reinstall requirements
pip install -r requirements.txt
```

### Configure dbt Profile

dbt needs a `profiles.yml` file to connect to your database.

**Option 1: Copy the provided profile (Recommended)**

```bash
# Windows (PowerShell)
Copy-Item profiles.yml $env:USERPROFILE\.dbt\profiles.yml

# Windows (Command Prompt)
copy profiles.yml %USERPROFILE%\.dbt\profiles.yml

# Linux/Mac
cp profiles.yml ~/.dbt/profiles.yml
```

**Option 2: Use local profile with --profiles-dir**

```bash
# Run dbt commands from project root
dbt run --profiles-dir .
dbt test --profiles-dir .
```

**Option 3: Create your own profile**

Create `~/.dbt/profiles.yml` (or `%USERPROFILE%\.dbt\profiles.yml` on Windows):

```yaml
ecommerce_analytics:
  target: dev
  outputs:
    dev:
      type: postgres
      host: localhost
      port: 5432
      user: analytics_user
      password: analytics_pass
      dbname: ecommerce_analytics
      schema: public
      threads: 4
```

### Verify dbt Connection

```bash
# Test database connection
dbt debug

# Should output: All checks passed!
```

### Run dbt Models

```bash
# Run all models
dbt run

# Run specific model
dbt run --select model_name

# Run models by tag
dbt run --select tag:staging
dbt run --select tag:intermediate
dbt run --select tag:marts

# Run with full refresh (drop and recreate tables)
dbt run --full-refresh
```

### Test dbt Models

```bash
# Run all tests
dbt test

# Run tests on specific model
dbt test --select model_name

# Run tests immediately after building
dbt run && dbt test
```

### Generate Documentation

```bash
# Generate documentation
dbt docs generate

# Serve documentation locally
dbt docs serve

# Open in browser
# http://localhost:8080
```

### Build dbt Models (Run + Test)

```bash
# Build all models (run + test)
dbt build

# Build specific models
dbt build --select model_name
```

### Common dbt Commands

| Command | Description |
|---------|-------------|
| `dbt run` | Execute SQL models |
| `dbt test` | Run data quality tests |
| `dbt build` | Run + test |
| `dbt docs generate` | Generate documentation |
| `dbt docs serve` | Host documentation |
| `dbt debug` | Test connection |
| `dbt ls` | List models |
| `dbt source freshness` | Check source data freshness |

### dbt with Docker

```bash
# Run dbt in Docker container
docker compose --profile dbt up --abort-on-container-exit

# Or exec into running container
docker compose exec app dbt run
```

### dbt with Makefile

```bash
# Run dbt models
make dbt

# Run dbt tests
make dbt-test

# Generate and serve docs
make dbt-docs
```

### dbt Project Structure

```
dbt/
├── models/
│   ├── staging/          # Raw data transformations
│   ├── intermediate/     # Business logic
│   └── marts/            # Final tables for analytics
├── tests/
│   ├── generic/          # Schema tests
│   └── singular/         # SQL tests
├── seeds/                # Static CSV data
├── macros/               # Reusable SQL functions
├── analyses/             # Exploratory queries
└── snapshots/            # Slowly changing dimensions
```

### Materialization Strategies

| Type | Use Case | Performance |
|------|----------|-------------|
| `view` | Staging, intermediate | Fast, no storage |
| `table` | Final marts, large datasets | Fast queries, more storage |
| `incremental` | Large, growing datasets | Best for production |

---

## 🧪 Testing

### Run Tests with Docker

```bash
# Using docker compose
docker compose --profile test up --abort-on-container-exit

# Using make
make test
make test-cov       # with coverage
make test-fast      # without coverage
```

### Run Tests Locally

```bash
# All tests
pytest tests/ -v --cov=src

# Specific test file
pytest tests/test_analytics.py -v

# Specific test function
pytest tests/test_analytics.py::test_specific_function -v

# By marker
pytest tests/ -m unit -v
pytest tests/ -m integration -v
pytest tests/ -m "not slow" -v
```

### Code Quality

```bash
# Linters
flake8 src/
black src/ --check
isort src/ --check

# Type checking
mypy src/

# Auto-format
black src/
isort src/
```

---

## 📈 Production Deployment

### Cloud Deployments

#### AWS ECS

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag nexacommerce-analytics:prod \
  <account>.dkr.ecr.us-east-1.amazonaws.com/nexacommerce:latest

docker push <account>.dkr.ecr.us-east-1.amazonaws.com/nexacommerce:latest
```

#### Google Cloud Run

```bash
gcloud run deploy nexacommerce \
  --image gcr.io/<project>/nexacommerce:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

#### Azure Container Apps

```bash
az containerapp create \
  --name nexacommerce \
  --resource-group my-resource-group \
  --environment my-environment \
  --image nexacommerce-analytics:prod \
  --target-port 8501 \
  --ingress external
```

---

## 🛠️ Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs app

# Rebuild without cache
docker compose build --no-cache

# Complete reset
docker compose down -v
docker compose up -d
```

### Port Already in Use

```bash
# Option 1: Change port in .env
STREAMLIT_SERVER_PORT=8502

# Option 2: Use different port in docker-compose override
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d

# Option 3: Find and kill process using the port
# Windows:
netstat -ano | findstr :8501
taskkill /PID <PID> /F
# Linux/Mac:
lsof -ti:8501 | xargs kill -9
```

### Database Connection Issues

```bash
# Check PostgreSQL health
docker compose ps postgres

# View PostgreSQL logs
docker compose logs postgres

# Reset database
docker compose down -v
docker compose up -d postgres

# Test connection locally
psql -h localhost -U analytics_user -d ecommerce_analytics
```

### Out of Memory

```bash
# Increase Docker memory (Docker Desktop)
# Settings → Resources → Memory → 4GB+

# Or limit in docker-compose.yml
# See deploy.resources.limits
```

### Module Import Errors (Local)

```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=/path/to/ecommerce_analytics

# Or install in development mode
pip install -e .

# Verify installation
python -c "import src; print(src.__file__)"
```

### Streaming Not Working

```bash
# Check Redis is running
docker compose ps redis

# Test Redis connection
docker compose exec redis redis-cli ping

# Start streaming profile
docker compose --profile streaming up -d
```

---

## 📚 Additional Documentation

- [Feature Reference](FEATURES.md) - Complete API documentation
- [dbt Documentation](dbt/docs/index.html) - Data transformation docs

---

## 🤝 Contributing

### Development Workflow

```bash
# Clone repository
git clone https://github.com/your-org/nexacommerce-analytics.git
cd nexacommerce-analytics

# Start development environment
docker compose up -d app postgres redis

# Make changes to code (mounted in container)

# Run tests before committing
make test

# Check code quality
make lint
make format
make type-check

# Commit changes
git add .
git commit -m "feat: add new feature"
```

---

## 📊 Key Metrics

| Metric | Value |
|--------|-------|
| Python Version | 3.12.5 |
| Docker Base Image | python:3.12-slim |
| Image Size (prod) | ~800MB |
| Image Size (dev) | ~2.5GB |
| Startup Time | ~60 seconds |
| Memory Required | 4GB minimum |
| CPU Cores | 2 recommended |

---

## 🔗 Quick Reference

### Most Common Commands

```bash
# Start everything
docker compose up -d
# or
make up

# View dashboard
# Open http://localhost:8501

# View logs
docker compose logs -f
# or
make logs

# Run pipeline
python run_pipeline.py
# or
make pipeline

# Run tests
pytest tests/ -v
# or
make test

# Stop everything
docker compose down
# or
make down
```

### Service Ports

| Service | Port | URL |
|---------|------|-----|
| Streamlit Dashboard | 8501 | http://localhost:8501 |
| PostgreSQL | 5432 | localhost:5432 |
| Redis | 6379 | localhost:6379 |

---

*Built to senior/principal data scientist standards with production-ready Docker deployment.*
