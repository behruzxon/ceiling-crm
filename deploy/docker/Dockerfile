# =============================================================================
# CeilingCRM — Multi-stage Dockerfile
# =============================================================================
# Stage 1: builder  — installs dependencies
# Stage 2: runtime  — minimal production image
# =============================================================================

# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="CeilingCRM Team" \
      service="ceiling-crm"

# Install runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local /usr/local

# Copy application source
COPY . .

# Ensure local packages are on PATH
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create media directory and make entrypoint executable
RUN mkdir -p /app/media && chown appuser:appuser /app/media && \
    chmod +x /app/deploy/docker/entrypoint.sh

USER appuser

ENTRYPOINT ["/app/deploy/docker/entrypoint.sh"]

# Health check: lightweight Python connectivity check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import asyncio; asyncio.run(__import__('infrastructure.database.session', fromlist=['check_database_health']).check_database_health())" || exit 1

CMD ["python", "-m", "apps.bot.main"]
