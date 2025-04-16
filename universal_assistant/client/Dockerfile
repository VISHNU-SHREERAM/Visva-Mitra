FROM python:3.12-slim

WORKDIR /app

# Copy source files
COPY client_gui.py .
COPY pyproject.toml .

# copy everything inside templates folder to /app/templates
COPY templates/ ./templates


# Install dependencies
RUN pip install --no-cache-dir .

# Expose client port (you mentioned 5000)
EXPOSE 5000

CMD ["python", "client_gui.py"]
