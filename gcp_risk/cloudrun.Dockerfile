FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-cloudrun.txt ./
RUN pip install --no-cache-dir -r requirements-cloudrun.txt

COPY gcp_risk ./gcp_risk
COPY shared ./shared

ENV PORT=8003
EXPOSE 8003

CMD ["sh", "-c", "exec python -m uvicorn gcp_risk.main:app --host 0.0.0.0 --port ${PORT:-8003}"]
