# Multi-stage Dockerfile for the Dezider FastAPI backend.
#
# Build:   docker build -t dezider/backend:latest -f backend/Dockerfile backend
# Run:     docker run --rm -p 8001:8001 \
#            -e MONGO_URL=mongodb://host.docker.internal:27017/dezider \
#            -e DEZIDER_ENV=stage \
#            -e SECURITY_HEADERS_ENABLED=true \
#            -e HSTS_ENABLED=false \
#            dezider/backend:latest

FROM python:3.11-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# Emergent-hosted private package (emergentintegrations) lives on a custom index.
# We add it as an --extra-index-url so pip can resolve it alongside public PyPI.
RUN pip install --user --no-cache-dir \
        --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ \
        -r requirements.txt

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH=/root/.local/bin:$PATH \
    DEZIDER_ENV=prod \
    HSTS_ENABLED=true
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; \
  sys.exit(0 if urllib.request.urlopen('http://localhost:8001/api/health/live', timeout=3).status == 200 else 1)"
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", \
     "--workers", "4", "--loop", "uvloop", "--http", "httptools", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
