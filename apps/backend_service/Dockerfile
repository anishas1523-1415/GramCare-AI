FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Run schema migrations before serving. Previously the schema was only ever
# created via ad-hoc create_all() calls, so containers could boot against a
# stale or empty schema.
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
