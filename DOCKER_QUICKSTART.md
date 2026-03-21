# 🐳 Docker Quick Start Guide
─────────────────────────────────────────────────────────────────────────────
NexaCommerce Analytics Platform

## ⚡ One-Command Start

```bash
# Start everything (recommended)
docker compose up -d

# Access dashboard at http://localhost:8501
```

## 📋 Common Commands

| Command | Description |
|---------|-------------|
| `docker compose up -d` | Start all services |
| `docker compose down` | Stop all services |
| `docker compose logs -f` | Follow logs |
| `docker compose ps` | Show running containers |
| `docker compose exec app bash` | Shell into container |
| `make help` | Show all make commands |

## 🎯 Using Make (Recommended)

```bash
make help           # Show all commands
make up             # Start services
make down           # Stop services
make logs           # View logs
make test           # Run tests
make build          # Build image
make clean          # Clean up
```

## 🔧 Troubleshooting

### Check if services are running
```bash
docker compose ps
```

### View logs
```bash
# All services
docker compose logs -f

# App only
docker compose logs -f app

# Database only
docker compose logs -f postgres
```

### Restart services
```bash
docker compose restart
```

### Complete reset
```bash
docker compose down -v
docker compose up -d
```

### Port conflicts
If port 8501 is in use, edit `.env.docker`:
```bash
STREAMLIT_SERVER_PORT=8502
```

## 📊 Service Endpoints

| Service | URL | Port |
|---------|-----|------|
| Dashboard | http://localhost:8501 | 8501 |
| PostgreSQL | localhost | 5432 |
| Redis | localhost | 6379 |

## 🔐 Default Credentials

| Service | Username | Password |
|---------|----------|----------|
| PostgreSQL | analytics_user | analytics_pass |

## 📁 Data Persistence

Data is stored in Docker volumes:
- `app_data` - Raw and processed data
- `app_models` - Trained ML models
- `app_logs` - Application logs
- `postgres_data` - Database

To reset all data:
```bash
docker compose down -v
```

## 🚀 Advanced Usage

### Start with streaming
```bash
docker compose --profile streaming up -d
```

### Run tests
```bash
docker compose --profile test up --abort-on-container-exit
```

### Run pipeline
```bash
docker compose --profile pipeline up --abort-on-container-exit
```

### Run dbt
```bash
docker compose --profile dbt up --abort-on-container-exit
```

## 🛠️ Build Options

```bash
# Standard build
docker build -t nexacommerce-analytics .

# Production build (smaller)
docker build --target production -t nexacommerce-analytics:prod .

# Development build (more tools)
docker build --target development -t nexacommerce-analytics:dev .
```

## 📝 Environment Variables

Copy and customize:
```bash
cp .env.docker .env
```

Key variables:
```bash
DB_HOST=postgres
REDIS_HOST=redis
STREAMLIT_SERVER_PORT=8501
N_CUSTOMERS=15000
```

## 💡 Tips

1. **First startup takes longer** - Models are being trained
2. **Check logs for issues** - `docker compose logs -f app`
3. **Use make commands** - Easier to remember
4. **Persist data** - Volumes keep data between restarts
5. **Health check** - Dashboard: http://localhost:8501/_stcore/health

## 🆘 Getting Help

```bash
# Show all make commands
make help

# Show docker compose help
docker compose --help

# View this guide
cat DOCKER_QUICKSTART.md
```

## 📚 More Documentation

- [Main README](README.md) - Full documentation
- [FEATURES.md](FEATURES.md) - Feature reference
- [docker-compose.yml](docker-compose.yml) - Service configuration
