FROM python:3.11-alpine

WORKDIR /dgg-relay
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN adduser -D appuser
RUN mkdir -p /dgg-relay/config && chown -R appuser:appuser /dgg-relay/config
USER appuser

ENTRYPOINT ["python", "main.py"]