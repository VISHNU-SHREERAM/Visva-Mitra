FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY main.py .

RUN pip install --no-cache-dir . httpx

EXPOSE 8003

CMD ["python", "main.py"]