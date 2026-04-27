# Single Python image used by every QuantIAN peer.
# docker-compose overrides CMD per service.
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# system packages we need (curl for healthchecks; build-essential is not needed
# thanks to manylinux wheels for numpy/scipy/sklearn on python:3.13-slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
    && rm -rf /var/lib/apt/lists/*

# deps first for layer caching
COPY requirements.txt ./
RUN pip install -r requirements.txt

# app code
COPY shared ./shared
COPY registry_service ./registry_service
COPY aws_ingestion ./aws_ingestion
COPY azure_anomaly ./azure_anomaly
COPY gcp_risk ./gcp_risk
COPY iot ./iot
COPY simulator ./simulator
COPY dashboard ./dashboard
COPY scripts ./scripts
COPY pytest.ini README.md ./
# tests optional (not needed at runtime but useful for `docker compose run`)
COPY tests ./tests

# default: fail loudly so the user knows they need to pick a service
CMD ["python", "-c", "raise SystemExit('Override CMD: choose a service, e.g. uvicorn registry_service.main:app --host 0.0.0.0 --port 8000')"]
