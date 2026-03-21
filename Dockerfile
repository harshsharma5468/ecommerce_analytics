# ==============================================================================
# 1. BASE STAGE (OS & Compilers) - Only runs once
# ==============================================================================
FROM python:3.12-slim-bookworm as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUTF8=1

WORKDIR /app

# Install system dependencies once. 
# We use 'bookworm' (stable) for faster, more reliable mirrors.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    libpq-dev \
    libpq5 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# ==============================================================================
# 2. HEAVY DEPENDENCIES (The "Slow" ML Libraries)
# ==============================================================================
FROM base as dependencies

# CRITICAL: Install these FIRST and SEPARATELY. 
# These take 5-10 mins to compile. By putting them here, 
# they stay cached even if you change your requirements.txt.
RUN pip install --no-cache-dir \
    xgboost>=2.0.0 \
    lightgbm>=4.0.0 \
    shap>=0.44.0 \
    lifetimes>=0.11.3 \
    implicit>=0.7.0

# Now install your specific project requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# 3. DEVELOPMENT STAGE
# ==============================================================================
FROM dependencies as development

# Security: Create non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Create directories
RUN mkdir -p /app/data/raw /app/data/processed /app/models /app/logs \
    && chown -R appuser:appgroup /app

# Copy all project files
COPY --chown=appuser:appgroup . .

WORKDIR /app
USER appuser

# ==============================================================================
# 4. PRODUCTION STAGE (The "Fast" Layer)
# ==============================================================================
FROM dependencies as production

# Security: Create non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Create directories and set permissions BEFORE copying code
RUN mkdir -p /app/data/raw /app/data/processed /app/models /app/logs \
    && chown -R appuser:appgroup /app

# Copy only the files needed for production
COPY --chown=appuser:appgroup config/ ./config/
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup run_pipeline.py .
COPY --chown=appuser:appgroup dbt_project.yml .
COPY --chown=appuser:appgroup docker-startup.sh /app/docker-startup.sh

RUN chmod +x /app/docker-startup.sh && chown appuser:appgroup /app/docker-startup.sh

USER appuser
EXPOSE 8501

# Health check to ensure Streamlit is up
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["/app/docker-startup.sh"]
