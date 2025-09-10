FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

COPY ./requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python", "recommendation_server.py"]