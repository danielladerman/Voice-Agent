import asyncio
import websockets
import sounddevice as sd
import numpy as np
import logging
import time

# --- Configuration ---
SERVER_URI = "ws://localhost:8000/ws/talk"
SAMPLE_RATE = 16000  # 16kHz for speech recognition
CHANNELS = 1
DTYPE = 'int16'
CHUNK_DURATION_MS = 100  # Send audio in 100ms chunks
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
RECORD_SECONDS = 5  # Duration of the recording

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def record_and_stream():
    """
    Records audio from the microphone, streams it to the WebSocket server,
    and plays back the audio response from the server.
    """
    logger.info("Waiting for server to start...")
    time.sleep(3) # Wait 3 seconds for the server to initialize
    
    logger.info(f"Connecting to WebSocket server at {SERVER_URI}")
    
    try:
        async with websockets.connect(SERVER_URI) as websocket:
            logger.info("Connection successful. Starting to record and stream audio...")

            loop = asyncio.get_running_loop()
            
            # This queue will hold the audio chunks received from the server
            audio_queue = asyncio.Queue()

            async def stream_to_server():
                """Callback to send microphone data to the server."""
                def callback(indata, frames, time, status):
                    if status:
                        logger.warning(status)
                    loop.create_task(websocket.send(indata.tobytes()))

                with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE, callback=callback, blocksize=CHUNK_SIZE):
                    logger.info(f"Recording for {RECORD_SECONDS} seconds. Speak into the microphone.")
                    await asyncio.sleep(RECORD_SECONDS)
                
                logger.info("Finished recording. Signaling server to process.")
                # Send a special message to indicate the end of audio stream
                await websocket.send("EOS")


            async def receive_from_server():
                """Receives messages from the server and puts audio in the queue."""
                while True:
                    try:
                        message = await websocket.recv()
                        if isinstance(message, bytes):
                            await audio_queue.put(message)
                        else:
                            logger.info(f"Server message: {message}")
                    except websockets.exceptions.ConnectionClosed:
                        logger.info("Connection closed by server.")
                        await audio_queue.put(None)  # Signal end of audio
                        break

            async def play_audio():
                """Plays audio from the queue."""
                with sd.OutputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16') as stream:
                    logger.info("Audio playback started.")
                    while True:
                        chunk = await audio_queue.get()
                        if chunk is None:
                            break
                        stream.write(np.frombuffer(chunk, dtype=np.int16))
                    logger.info("Audio playback finished.")

            # Start all tasks
            stream_task = asyncio.create_task(stream_to_server())
            receive_task = asyncio.create_task(receive_from_server())
            play_task = asyncio.create_task(play_audio())

            # Wait for the streaming to finish
            await stream_task
            # Wait for the other tasks to complete
            await receive_task
            await play_task


    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(record_and_stream())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.") 