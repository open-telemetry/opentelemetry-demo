FROM python:3.12-slim-bookworm AS base

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

RUN opentelemetry-bootstrap -a install 

ENV RECOMMENDATION_PORT 1010

ENTRYPOINT ["python", "recommendation_server.py"]
