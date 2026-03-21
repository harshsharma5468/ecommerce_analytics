#!/bin/bash
# Startup script for Docker container

set -e

# Wait for PostgreSQL if DB_HOST is specified
if [ ! -z "$DB_HOST" ] && [ "$DB_HOST" != "localhost" ]; then
    echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
    until nc -z "$DB_HOST" "${DB_PORT:-5432}" 2>/dev/null; do
        echo "PostgreSQL is unavailable - sleeping"
        sleep 1
    done
    echo "PostgreSQL is up!"
fi

# Run migrations or initial setup if needed
# python -c "from config.settings import *; print('Config loaded')" || true

# Start Streamlit dashboard
exec streamlit run src/dashboard/app.py \
    --server.port="${STREAMLIT_SERVER_PORT:-8501}" \
    --server.address="${STREAMLIT_SERVER_ADDRESS:-0.0.0.0}" \
    --logger.level="${LOG_LEVEL:-info}"
