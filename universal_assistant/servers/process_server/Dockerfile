FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY main.py .

RUN pip install --no-cache-dir .

EXPOSE 8004

CMD ["python", "main.py"]