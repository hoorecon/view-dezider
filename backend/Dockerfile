# Multi-stage Dockerfile for the Dezider FastAPI backend.
#
# Build: docker build -t dezider/backend:latest -f backend/Dockerfile backend
# Run:   docker run --rm -p 8001:8001 \
#          -e MONGO_URL=mongodb://host.docker.internal:27017/dezider \
#          -e DEZIDER_ENV=stage \
#          -e SECURITY_HEADERS_ENABLED=true \
#          -e HSTS_ENABLED=false \
#          dezider/backend:latest

# ---------- Builder stage ----------
FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Build-time deps: compilers/headers needed to build wheels (psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    gcc \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Emergent-hosted private package (emergentintegrations) lives on a custom index.
# We add it as an --extra-index-url so pip can resolve it alongside public PyPI.
RUN pip install --upgrade pip && \
    pip install --user --no-cache-dir \
    --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ \
    -r requirements.txt

# ---------- Runtime stage ----------
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/appuser/.local/bin:$PATH \
    DEZIDER_ENV=prod \
    HSTS_ENABLED=true

WORKDIR /app

# Runtime-only shared libraries — same packages as builder, minus -dev/compiler
# tooling. These are the actual .so files your Python deps (e.g. opencv,
# psycopg2) dlopen at import time; without them the container builds fine
# but crashes on startup with an ImportError.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libpq5 \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — no reason to run a web server as root.
RUN useradd --create-home --uid 1000 appuser

RUN mkdir -p /app/uploads/meditations /app/uploads/conflict_audio /app/static/eft && \
    chown -R appuser:appuser /app

COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; \
    sys.exit(0 if urllib.request.urlopen('http://localhost:8001/api/health/live', timeout=3).status == 200 else 1)"

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port 8001 --workers ${WEB_CONCURRENCY:-2} --loop uvloop --http httptools --proxy-headers --forwarded-allow-ips '*'"]