FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-apprunner.txt ./
RUN pip install --no-cache-dir -r requirements-apprunner.txt

COPY registry_service ./registry_service
COPY shared ./shared

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "exec python -m uvicorn registry_service.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
