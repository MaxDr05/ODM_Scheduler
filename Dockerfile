FROM python:3.10-slim
LABEL authors="calvin"

WORKDIR /app
COPY requirements.txt .

RUN apt-get update && apt-get install -y --no-install-recommends docker.io \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python", "scheduler.py"]