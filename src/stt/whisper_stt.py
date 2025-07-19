import os
import io
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Initialize OpenAI Client ---
# Make sure your OPENAI_API_KEY is set in your .env file
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Transcribes audio bytes using OpenAI's Whisper API.
    The audio is expected to be in a format that Whisper can process (e.g., WebM, MP3, WAV).

    Args:
        audio_bytes (bytes): The audio data in bytes.

    Returns:
        str: The transcribed text.
    """
    if not audio_bytes:
        return ""

    try:
        # Use an in-memory file-like object
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"  # VAD sends WAV format
        
        # Send the audio data to Whisper API for transcription
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        
        return transcription.text.strip()

    except Exception as e:
        print(f"Error during transcription: {e}")
        return "" 