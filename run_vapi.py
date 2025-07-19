import os
import asyncio
from vapi_python import Vapi
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the Vapi Public Key from the environment variables
VAPI_PUBLIC_KEY = os.getenv("VAPI_PUBLIC_KEY")
if not VAPI_PUBLIC_KEY:
    raise ValueError("VAPI_PUBLIC_KEY is not set in the .env file")

# --- Main Vapi Runner ---
async def main():
    """
    This script starts a new Vapi call with a custom assistant that is
    configured to use our local RAG server for its responses.
    """
    # Prompt the user for the ngrok URL
    ngrok_url = input("Please enter your ngrok forwarding URL (e.g., https://xxxxx.ngrok.io): ")
    if not ngrok_url:
        print("ngrok URL is required.")
        return

    # Initialize the Vapi client
    vapi = Vapi(api_key=VAPI_PUBLIC_KEY)

    # Define the assistant that will use our local RAG server
    assistant_config = {
        "model": {
            "provider": "openai",
            "model": "gpt-3.5-turbo",
        },
        "server": {
            "url": f"{ngrok_url}/vapi-webhook"
        },
        "voice": {
            "provider": "playht",
            "voiceId": "jennifer"
        },
        "firstMessage": "Hello, I am your AI business assistant. How can I help you today?"
    }

    try:
        print("Starting Vapi call...")
        # Start the call. Vapi will provide a web link to join the conversation.
        vapi.start(assistant=assistant_config)
        print("\nCall started successfully. Check the Vapi output for a link to join the call.")
        print("Press Ctrl+C to stop the call.")
        
        # Keep the script running until the user stops it
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping Vapi call...")
        vapi.stop()
        print("Call stopped.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 