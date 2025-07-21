import os
from dotenv import load_dotenv
from retell_sdk import RetellClient

# Load environment variables from .env file
load_dotenv()

# Initialize the Retell client with your API key
retell = RetellClient(api_key=os.environ["RETELL_API_KEY"])

# --- 1. Define the Agent ---
# This is where we set the system prompt and define our custom tool.
# Replace <YOUR_RENDER_URL> and <BUSINESS_NAME> with your actual deployment details.
agent = retell.agent.create(
    llm_websocket_url="wss://api.retellai.com/llm-websocket/openai-gpt-4o",
    voice_id="11labs-Adrian",
    agent_name="HVAC Receptionist",
    general_prompt=(
        "You are a helpful AI receptionist for an HVAC company. "
        "Your goal is to answer questions accurately based on the information "
        "provided to you by the get_context tool. Never make up information. "
        "If you don't know the answer, say so. Always use the get_context tool "
        "to answer any user questions."
    ),
    custom_tools=[
        {
            "name": "get_context",
            "description": "Fetches context from the knowledge base to answer user questions.",
            "url": "https://voice-agent-backend-vsdg.onrender.com/examplehvac/retell-get-context",
            "method": "POST",
            "speak_during_execution": True,
            "speak_after_execution": False,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user's question to be used for information retrieval."
                    }
                },
                "required": ["query"]
            }
        }
    ]
)

if not agent:
    print("Failed to create agent.")
    exit()

print(f"Successfully created agent: {agent.agent_id}")
print(f"Agent Name: {agent.agent_name}")

# --- 2. Create a Phone Number ---
# You only need to do this once. If you already have a number, you can use its ID.
try:
    phone_number = retell.phone_number.create(
        agent_id=agent.agent_id,
    )
    print(f"Successfully created phone number: {phone_number.phone_number}")
    print(f"Phone Number SID: {phone_number.sid}")

    # --- 3. Initiate a Call (for testing) ---
    # This shows how you would programmatically start a call.
    # Replace <YOUR_PHONE_NUMBER> with your actual phone number in E.164 format.
    call = retell.call.register(
        agent_id=agent.agent_id,
        direction="outbound",
        to_number="+14153598777",
        from_number=phone_number.phone_number,
    )
    print(f"Call initiated. Call ID: {call.call_id}")

except Exception as e:
    print(f"An error occurred during phone number creation or call registration: {e}") 