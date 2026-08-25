FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY paths.py /app/paths.py
COPY demo /app/demo
COPY investigator /app/investigator

RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn>=0.30.0" \
    "httpx>=0.27.0" \
    "psycopg[binary]>=3.2.0" \
    "prometheus-client>=0.21.0" \
    "opentelemetry-api>=1.27.0" \
    "opentelemetry-sdk>=1.27.0" \
    "opentelemetry-exporter-otlp>=1.27.0" \
    "opentelemetry-instrumentation-fastapi>=0.48b0" \
    "opentelemetry-instrumentation-httpx>=0.48b0"

ENV PYTHONPATH=/app
EXPOSE 8000
