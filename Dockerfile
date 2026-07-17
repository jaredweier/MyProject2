# Chronos Command — online host image (Weierworks Technologies, LLC)
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SCHEDULER_UI_MODE=web \
    SCHEDULER_HOST=0.0.0.0 \
    SCHEDULER_PORT=8080 \
    SCHEDULER_SKIP_STARTUP_GATES=1 \
    SCHEDULER_DB_PATH=/app/persist/dodgeville_scheduler.db

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/persist /app/photos /app/logs /app/backups /app/exports /app/tenants

# Persist via compose volumes (see docker-compose.yml)
VOLUME ["/app/persist", "/app/photos", "/app/logs", "/app/backups", "/app/exports", "/app/tenants"]

EXPOSE 8080

CMD ["python", "main.py", "--web", "--host", "0.0.0.0", "--port", "8080"]
