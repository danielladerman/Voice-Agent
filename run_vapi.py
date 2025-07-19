import os
import asyncio
import argparse  # Import argparse
from vapi_python import Vapi
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the Vapi API Key from the environment variables
# The user's .env file uses VAPI_PUBLIC_KEY, so we will use that.
VAPI_API_KEY = os.getenv("VAPI_PUBLIC_KEY")
if not VAPI_API_KEY:
    raise ValueError("VAPI_PUBLIC_KEY is not set in the .env file. Please check your .env file.")

# --- Main Vapi Runner ---
async def main(ngrok_url: str, business_name: str):  # Accept business_name
    """
    This script starts a new Vapi call with a custom assistant that is
    configured to use our local RAG server for its responses.
    """
    print(f"Using ngrok URL: {ngrok_url}")
    print(f"For business: {business_name}")

    # Initialize the Vapi client
    vapi = Vapi(api_key=VAPI_API_KEY)

    # By setting the model to None, we force Vapi to rely exclusively on the
    # responses provided by our server webhook. This prevents Vapi from
    # "freeballing" with its own generic LLM.
    assistant_config = {
        "model": None,
        "server": {
            # Construct the correct URL with the business name
            "url": f"{ngrok_url}/{business_name}/vapi-webhook"
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
        print("\nCall started successfully. A browser window should open to join the call.")
        print("Press Ctrl+C to stop the script.")
        
        # Keep the script running until the user stops it
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping Vapi call...")
        # vapi.stop() is not a valid method in the vapi-python library.
        # The call is managed on the server side and will time out.
        print("Script stopped. You can close the browser window.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Run the Vapi voice agent.")
    parser.add_argument("ngrok_url", type=str, help="The ngrok forwarding URL for the backend server.")
    parser.add_argument("business_name", type=str, help="The name of the business to connect to (used in the webhook URL).")
    
    args = parser.parse_args()
    
    # Run the main async function with the provided URL and business name
    asyncio.run(main(args.ngrok_url, args.business_name)) 