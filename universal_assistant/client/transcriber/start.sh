#!/bin/bash

echo "Starting transcriber service..."

# Pre-download Whisper model to cache it
echo "Pre-downloading Whisper model..."
python -c "
import whisper
try:
    model = whisper.load_model('medium.en')
    print('Whisper model downloaded successfully')
except Exception as e:
    print(f'Warning: Could not pre-download model: {e}')
"

# Start the FastAPI application
echo "Starting FastAPI application..."
exec uvicorn transcriber:APP --host 0.0.0.0 --port 7777
