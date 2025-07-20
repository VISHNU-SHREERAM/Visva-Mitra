"""Audio transcription and command extraction service using FastAPI and PyYAML."""

import logging
from io import BytesIO
from typing import Annotated

import numpy as np
import torch
import uvicorn
import whisper
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydub.audio_segment import AudioSegment

from pydantic import BaseModel

from models import FinalResponse
from speak import initialize_tts_models, speak

# Add request model for TTS
class TTSRequest(BaseModel):
    """Request model for text-to-speech endpoint."""
    text: str

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP = FastAPI()
APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auto-detect device (GPU if available, otherwise CPU)
if torch.cuda.is_available():
    DEVICE = "cuda"
    logger.info("Using GPU: %s", torch.cuda.get_device_name(0))
else:
    DEVICE = "cpu"
    logger.info("Using CPU for inference")

try:
    MODEL = whisper.load_model("medium.en", device=DEVICE)
    logger.info("Whisper model loaded successfully on %s", DEVICE)
except (OSError, RuntimeError):
    logger.exception("Error loading Whisper model on %s", DEVICE)
    # Fall back to CPU and try again
    DEVICE = "cpu"
    MODEL = whisper.load_model("medium.en", device="cpu")

# Initialize TTS models
TTS_AVAILABLE = initialize_tts_models()
if TTS_AVAILABLE:
    logger.info("TTS models initialized successfully")
else:
    logger.warning("TTS models failed to initialize - speech synthesis unavailable")

@APP.post("/transcribe")
async def transcribe(recording: Annotated[UploadFile, File(...)]) -> FinalResponse:
    """Handle audio transcription requests.

    Args:
        recording (UploadFile): The audio file upload.

    Returns:
        FinalResponse: An object containing transcription text and matched commands.
    """
    # Read the uploaded audio content
    audio = await recording.read()
    audio_buffer = BytesIO(audio)

    # Convert the audio to single-channel, 16kHz
    audio_segment = AudioSegment.from_file(audio_buffer).set_frame_rate(16000).set_channels(1).set_sample_width(2)

    # Convert samples to float32 in range [-1,1]
    samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32) / 32768

    # Perform transcription
    result = MODEL.transcribe(
        samples,
        temperature=0,
        condition_on_previous_text=False,
        word_timestamps=True,
    )
    transcription = result["text"]

    return FinalResponse(response=transcription, message=transcription)


@APP.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model_loaded": MODEL is not None,
        "device": DEVICE,
        "gpu_available": torch.cuda.is_available(),
        "tts_available": TTS_AVAILABLE,
    }


@APP.post("/speak")
async def text_to_speech_form(text: str = None):
    """Convert text to speech via form data."""
    if not TTS_AVAILABLE:
        return {"error": "TTS models not available"}
    
    if not text or not text.strip():
        return {"error": "No text provided"}
    
    audio_buffer = speak(text.strip())
    if audio_buffer is None:
        return {"error": "Failed to generate speech"}
    
    return StreamingResponse(
        BytesIO(audio_buffer.getvalue()),
        media_type="audio/wav",
        headers={
            "Content-Disposition": "attachment; filename=speech.wav",
            "Access-Control-Allow-Origin": "*",
        },
    )


@APP.post("/speak_json")
async def text_to_speech_json(request: TTSRequest):
    """Convert text to speech via JSON request."""
    if not TTS_AVAILABLE:
        return {"error": "TTS models not available"}
    
    if not request.text.strip():
        return {"error": "No text provided"}
    
    # Use the original non-streaming approach for now
    audio_buffer = speak(request.text.strip())
    if audio_buffer is None:
        return {"error": "Failed to generate speech"}
    
    return StreamingResponse(
        BytesIO(audio_buffer.getvalue()),
        media_type="audio/wav",
        headers={
            "Content-Disposition": "attachment; filename=speech.wav",
            "Access-Control-Allow-Origin": "*",
        },
    )


if __name__ == "__main__":
    uvicorn.run("__main__:APP", host="0.0.0.0", port=7777, reload=True)
