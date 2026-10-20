# Backend image: the FastAPI REST API (default command) and, with a different command, the
# MCP server (see compose.yml). All dependencies ship as wheels, so no compiler is needed.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    KPI_DB_DIR=/app/databases

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Run unprivileged; the databases volume is the only path the app writes to.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/databases \
    && chown app:app /app/databases
COPY src ./src
USER app

EXPOSE 8000 8001

# --proxy-headers: the frontend's nginx forwards the real client address (used by the
# login rate limiter). Only trust it because the backend port is not exposed publicly.
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
