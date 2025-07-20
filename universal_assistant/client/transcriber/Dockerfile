FROM python:3.12-slim

# Install system dependencies required for audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install uv package manager
RUN pip install uv

# Copy dependency files first for better caching
COPY pyproject.toml .
COPY .python-version .

# Install Python dependencies
RUN uv pip install --system -e .

# Create directory for Whisper models
RUN mkdir -p /app/models

# Copy application code
COPY . .

# Make startup script executable
RUN chmod +x start.sh

# Expose the port the app runs on
EXPOSE 7777

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7777/health || exit 1

# Run the application using startup script
CMD ["./start.sh"]
