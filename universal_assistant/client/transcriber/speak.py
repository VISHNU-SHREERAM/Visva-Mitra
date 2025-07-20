"""Text-to-speech module using NVIDIA Tacotron2 and WaveGlow models."""

import asyncio
import logging
from io import BytesIO

import numpy as np
import torch
from scipy.io.wavfile import write

# Configure logging
logger = logging.getLogger(__name__)

# Global model variables
tacotron2 = None
waveglow = None
utils = None
device = "cuda" if torch.cuda.is_available() else "cpu"


def initialize_tts_models() -> bool:
    """Initialize TTS models. Returns True if successful, False otherwise."""
    global tacotron2, waveglow, utils
    
    try:
        logger.info(f"Loading TTS models on {device}")
        
        # Load Tacotron2
        tacotron2 = torch.hub.load(
            "NVIDIA/DeepLearningExamples:torchhub", 
            "nvidia_tacotron2", 
            model_math="fp16" if device == "cuda" else "fp32"
        )
        tacotron2 = tacotron2.to(device)
        tacotron2.eval()
        
        # Load WaveGlow
        waveglow = torch.hub.load(
            "NVIDIA/DeepLearningExamples:torchhub", 
            "nvidia_waveglow", 
            model_math="fp16" if device == "cuda" else "fp32"
        )
        waveglow = waveglow.remove_weightnorm(waveglow)
        waveglow = waveglow.to(device)
        waveglow.eval()
        
        # Load utilities
        utils = torch.hub.load("NVIDIA/DeepLearningExamples:torchhub", "nvidia_tts_utils")
        
        logger.info("TTS models loaded successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to load TTS models: {e}")
        return False


def speak(text: str, rate: int = 22050) -> BytesIO | None:
    """Generate speech from text and return as BytesIO object."""
    if not all([tacotron2, waveglow, utils]):
        logger.error("TTS models not initialized")
        return None
    
    try:
        # Clean the text to avoid unexpected characters and emojis
        cleaned_text = ''.join(char for char in text if char.isprintable() and ord(char) < 128)
        if not cleaned_text.strip():
            logger.warning("Text became empty after cleaning")
            return None
            
        # Split long text into smaller chunks to avoid decoder step limits
        max_chunk_length = 50  # Smaller chunk size to avoid decoder warnings
        text_chunks = [cleaned_text[i:i+max_chunk_length] 
                      for i in range(0, len(cleaned_text), max_chunk_length)]
        
        all_audio = []
        
        for chunk in text_chunks:
            if not chunk.strip():
                continue
                
            sequences, lengths = utils.prepare_input_sequence([chunk])

            with torch.no_grad():
                # Generate mel spectrogram - removed max_decoder_steps parameter
                mel, _, _ = tacotron2.infer(sequences, lengths)
                audio = waveglow.infer(mel)

            audio_numpy = audio[0].data.cpu().numpy()
            all_audio.append(audio_numpy)
        
        if not all_audio:
            logger.warning("No audio generated from text chunks")
            return None
            
        # Concatenate all audio chunks
        final_audio = np.concatenate(all_audio, axis=0)
        
        # Ensure audio is in the correct format for WAV
        # Normalize audio to prevent clipping and ensure proper range
        if final_audio.dtype == np.float32:
            # Normalize float32 audio to [-1, 1] range
            final_audio = np.clip(final_audio, -1.0, 1.0)
            # Convert to 16-bit PCM
            final_audio = (final_audio * 32767).astype(np.int16)
        elif final_audio.dtype != np.int16:
            # For other types, convert to int16
            final_audio = final_audio.astype(np.int16)

        # Return a BytesIO object with proper WAV format
        audio_buffer = BytesIO()
        write(audio_buffer, rate, final_audio)
        audio_buffer.seek(0)
        return audio_buffer
    
    except Exception as e:
        logger.exception("Failed to generate speech")
        return None


async def speak_streaming(text: str, rate: int = 22050):
    """Generate speech from text and yield audio chunks for streaming."""
    
    if not all([tacotron2, waveglow, utils]):
        logger.error("TTS models not initialized")
        return
    
    try:
        # Clean the text to avoid unexpected characters
        cleaned_text = ''.join(char for char in text if char.isprintable() and ord(char) < 128)
        if not cleaned_text.strip():
            logger.warning("Text became empty after cleaning")
            return
            
        # Split into smaller chunks for streaming (shorter chunks for faster response)
        max_chunk_length = 50  # Shorter chunks for streaming
        text_chunks = [cleaned_text[i:i+max_chunk_length]
                      for i in range(0, len(cleaned_text), max_chunk_length)]
        
        # Process each chunk and yield audio immediately
        for chunk in text_chunks:
            if not chunk.strip():
                continue
                
            # Run TTS inference in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            audio_chunk = await loop.run_in_executor(None, _generate_audio_chunk, chunk, rate)
            
            if audio_chunk:
                yield audio_chunk
                # Small delay to allow smooth streaming
                await asyncio.sleep(0.01)
    
    except Exception as e:
        logger.exception("Failed to generate streaming speech")


def _generate_audio_chunk(chunk: str, rate: int = 22050) -> bytes | None:
    """Generate audio for a single text chunk."""
    try:
        sequences, lengths = utils.prepare_input_sequence([chunk])

        with torch.no_grad():
            # Generate mel spectrogram - removed max_decoder_steps parameter
            mel, _, _ = tacotron2.infer(sequences, lengths)
            audio = waveglow.infer(mel)

        audio_numpy = audio[0].data.cpu().numpy()

        # Create a temporary BytesIO for this chunk
        chunk_buffer = BytesIO()
        write(chunk_buffer, rate, audio_numpy)
        chunk_buffer.seek(0)
        return chunk_buffer.getvalue()
    
    except Exception as e:
        logger.exception("Failed to generate audio chunk")
        return None