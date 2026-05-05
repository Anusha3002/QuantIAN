FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-apprunner.txt ./
RUN pip install --no-cache-dir -r requirements-apprunner.txt

COPY aws_ingestion ./aws_ingestion
COPY shared ./shared

ENV PORT=8001
EXPOSE 8001

CMD ["sh", "-c", "exec python -m uvicorn aws_ingestion.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
