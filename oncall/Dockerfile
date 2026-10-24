FROM python:3.12-slim

COPY oncall/requirements.txt /app/oncall/requirements.txt
RUN pip install --no-cache-dir -r /app/oncall/requirements.txt

COPY oncall/ /app/oncall/
WORKDIR /app

CMD ["python", "-m", "oncall", "serve"]
