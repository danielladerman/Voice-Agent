from elevenlabs.client import ElevenLabs
from elevenlabs import save
import os
import asyncio

# --- Initialize ElevenLabs Client ---
try:
    client = ElevenLabs(
        api_key=os.getenv("ELEVEN_LABS_API_KEY")
    )
    print("ElevenLabs client initialized successfully.")
except Exception as e:
    print(f"Error initializing ElevenLabs client: {e}")
    client = None

async def text_to_speech_stream(text: str):
    """
    Converts text to speech using the ElevenLabs API and streams the audio.

    Args:
        text: The text to convert to speech.

    Yields:
        The audio data in byte chunks.
    """
    if not client:
        print("ElevenLabs client is not available.")
        return

    try:
        # Generate the audio from the text using the streaming-capable method
        response = client.text_to_speech.convert(
            voice_id="EXAVITQu4vr4xnSDxMaL", # Voice ID for "Sarah"
            text=text,
            output_format="mp3_44100_128" # Use a standard MP3 format
        )
        
        # Stream the audio chunks
        for chunk in response:
            yield chunk

    except Exception as e:
        print(f"An error occurred during text-to-speech streaming: {e}")

if __name__ == '__main__':
    # This block allows us to test the TTS streaming directly
    async def main():
        test_text = "Hello, this is a test of the streaming text-to-speech functionality."
        print(f"Generating streaming audio for text: '{test_text}'")
        
        audio_stream = text_to_speech_stream(test_text)
        
        # In a real application, you would stream these chunks to the client.
        # For this test, we'll just collect them.
        all_audio_chunks = []
        async for chunk in audio_stream:
            all_audio_chunks.append(chunk)
            print(f"Received chunk of size: {len(chunk)}")
            
        if all_audio_chunks:
            # For testing, we can save the concatenated chunks to a file.
            # Note: This is not how you would handle it in a real-time scenario.
            full_audio = b"".join(all_audio_chunks)
            try:
                save(full_audio, "test_audio_stream.mp3")
                print("Successfully saved test audio to test_audio_stream.mp3")
            except Exception as e:
                print(f"Error saving audio file: {e}")
        else:
            print("Failed to generate audio data.")
            
    asyncio.run(main()) 