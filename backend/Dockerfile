# ==============================================================================
# BhumiSetu Backend Container Image (Production & Staging)
# ==============================================================================
# Multi-stage, unprivileged non-root user container with GDAL/GEOS & Tesseract
# ==============================================================================

# Stage 1: Build & Dependency Resolution
FROM python:3.14-slim AS builder

WORKDIR /build

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install build dependencies for C-extensions (psycopg2, shapely, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgeos-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv

# Create virtual environment and sync dependencies
COPY pyproject.toml uv.lock ./
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN uv sync --frozen --no-install-project

# Stage 2: Minimal Distroless-like Runtime Image
FROM python:3.14-slim AS runner

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

# Install runtime shared libraries only (PostgreSQL client, GEOS geometry, OCR engines)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgeos-c1v5 \
    tesseract-ocr \
    tesseract-ocr-hin \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy prebuilt virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

# Create unprivileged application user
RUN groupadd -g 10001 bhumisetu && \
    useradd -u 10001 -g bhumisetu -s /bin/bash -m bhumisetu

# Prepare directories with correct permissions
RUN mkdir -p /app/storage/documents /app/logs && \
    chown -R bhumisetu:bhumisetu /app

# Copy application source code
COPY --chown=bhumisetu:bhumisetu . /app/

# Switch to non-root user
USER bhumisetu

# Container healthcheck
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/live || exit 1

EXPOSE 8000

# Default command: Run ASGI production server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
