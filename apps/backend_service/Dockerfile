FROM python:3.11-slim
WORKDIR /app

# Runtime dependencies only — test tooling lives in requirements-dev.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user (healthcare data hardening)
RUN addgroup --system gramcare && adduser --system --ingroup gramcare gramcare \
    && chown -R gramcare:gramcare /app
USER gramcare

EXPOSE 8000

# Container-level liveness probe (docker-compose healthchecks also exist,
# but plain `docker run` deployments get one too)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# Run schema migrations before serving. Previously the schema was only ever
# created via ad-hoc create_all() calls, so containers could boot against a
# stale or empty schema.
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
