FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-containerapp.txt ./
RUN pip install --no-cache-dir -r requirements-containerapp.txt

COPY azure_anomaly ./azure_anomaly
COPY shared ./shared

EXPOSE 8002

CMD ["python", "-m", "uvicorn", "azure_anomaly.main:app", "--host", "0.0.0.0", "--port", "8002"]
