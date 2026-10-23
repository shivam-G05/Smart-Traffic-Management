# Backend image: simulation + decision engine + FastAPI.
# Build from the REPO ROOT, not from backend/:
#   docker build -f backend/Dockerfile -t smart-traffic-backend .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# curl is used by the container healthcheck; libglib2.0-0 is needed by
# opencv-python-headless at import time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Each package is copied explicitly so an unrelated file at the repo root
# cannot silently end up inside the image.
COPY simulation/ simulation/
COPY decision_engine/ decision_engine/
COPY analytics/ analytics/
COPY database/ database/
COPY vision/ vision/
COPY shared/ shared/
COPY backend/ backend/

# Run as a non-root user; /data holds the SQLite file (mounted as a volume).
RUN useradd --create-home --uid 1000 stms \
    && mkdir -p /data \
    && chown -R stms:stms /data /app
USER stms

ENV PYTHONPATH=/app:/app/backend \
    STMS_DATABASE_URL=sqlite+aiosqlite:////data/traffic.db

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
