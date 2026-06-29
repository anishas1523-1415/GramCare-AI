FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

# We use python 3.11 in docker to ensure maximum compatibility with pre-built wheels
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
