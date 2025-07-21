import uvicorn
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import google.auth.transport.requests
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
import json

# Load environment variables
load_dotenv()

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnableLambda

# Import the new database functions
from src.database import database as db_utils
from src.tools import google_calendar as calendar_tool

# --- Environment Variables ---
GOOGLE_CLIENT_SECRET_JSON = os.getenv("GOOGLE_CLIENT_SECRET_JSON")
SECRET_KEY = os.getenv("SECRET_KEY", "a_very_secret_key") # It's better to use a more secure key in production

if not GOOGLE_CLIENT_SECRET_JSON or not os.path.exists(GOOGLE_CLIENT_SECRET_JSON):
    print("!!! WARNING: `GOOGLE_CLIENT_SECRET_JSON` path not found. Google Calendar features will be disabled.")
    # You might want to handle this more gracefully

# --- Global Retriever Cache ---
retriever_cache = {}
LLM_MODEL = "gpt-4o"
INDEX_NAME = "voice-agent-data"


def get_retriever(business_name: str):
    """
    Initializes and caches a retriever for a specific business's namespace in Pinecone.
    """
    if business_name in retriever_cache:
        return retriever_cache[business_name]

    try:
        # Sanitize the business_name to match the namespace format
        namespace = "".join(e for e in business_name if e.isalnum() or e in ['_', '-']).lower()
        
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            dimensions=512  # Specify the dimension to match Pinecone index
        )
        
        vector_store = PineconeVectorStore(
            index_name=INDEX_NAME,
            embedding=embeddings,
            namespace=namespace
        )
        
        retriever = vector_store.as_retriever(search_type="mmr", search_kwargs={'k': 5})
        retriever_cache[business_name] = retriever
        return retriever

    except Exception as e:
        print(f"Error initializing retriever for '{business_name}': {e}")
        return None

# --- Function Schemas for the Agent ---
# This defines the structure of the functions the AI agent can call.

get_context_tool = {
    "type": "function",
    "function": {
        "name": "get_context",
        "description": "Fetches real-time, context-aware information based on the user's query to answer questions. Also returns the status of the Google Calendar integration.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The user's question or statement to be used for the information retrieval."
                }
            },
            "required": ["query"]
        }
    }
}

schedule_appointment_tool = {
    "type": "function",
    "function": {
        "name": "schedule_appointment",
        "description": "Schedules a new appointment or event in the calendar.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "A brief title or summary for the event (e.g., 'Service Appointment for John Doe')."
                },
                "start_time": {
                    "type": "string",
                    "description": "The start time of the event in ISO 8601 format (e.g., '2024-07-29T10:00:00-07:00')."
                },
                "end_time": {
                    "type": "string",
                    "description": "The end time of the event in ISO 8601 format (e.g., '2024-07-29T11:00:00-07:00')."
                },
                "description": {
                    "type": "string",
                    "description": "A more detailed description of the event or appointment."
                }
            },
            "required": ["summary", "start_time", "end_time"]
        }
    }
}

check_calendar_availability_tool = {
    "type": "function",
    "function": {
        "name": "check_calendar_availability",
        "description": "Checks the Google Calendar for a specific time range to see if there are any existing events (i.e., if the time is busy).",
        "parameters": {
            "type": "object",
            "properties": {
                "start_time": {
                    "type": "string",
                    "description": "The start of the time range to check, in ISO 8601 format."
                },
                "end_time": {
                    "type": "string",
                    "description": "The end of the time range to check, in ISO 8601 format."
                }
            },
            "required": ["start_time", "end_time"]
        }
    }
}


# --- App Lifespan Events ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events for the application.
    """
    print("--- SERVER: Application startup ---")
    await db_utils.init_db_pool()
    yield
    print("--- SERVER: Application shutdown ---")
    await db_utils.close_db_pool()


# --- FastAPI App ---
app = FastAPI(
    title="AI Voice Agent Backend",
    description="This server provides real-time context to a Vapi voice agent.",
    version="1.3.0",
    lifespan=lifespan
)

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

@app.get("/")
async def health_check():
    """A simple endpoint to confirm the server is running."""
    return {"status": "ok", "message": "Server is running"}

# --- Google Calendar OAuth 2.0 Flow ---

@app.get("/connect-google-calendar/{business_name}")
async def connect_google_calendar(request: Request, business_name: str):
    """
    Initiates the OAuth 2.0 flow to get permission for Google Calendar.
    Redirects the user to Google's consent screen.
    """
    if not GOOGLE_CLIENT_SECRET_JSON:
        return JSONResponse(status_code=500, content={"error": "Google Calendar integration is not configured."})

    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRET_JSON,
        scopes=['https://www.googleapis.com/auth/calendar.events', 'https://www.googleapis.com/auth/calendar.readonly'],
        redirect_uri=str(request.url_for('oauth2callback'))
    )
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    # Store the state and business_name to verify in the callback
    request.session['state'] = state
    request.session['business_name'] = business_name
    
    return JSONResponse(content={"authorization_url": authorization_url})


@app.get("/oauth2callback")
async def oauth2callback(request: Request):
    """
    Handles the callback from Google after user consent.
    Exchanges the authorization code for credentials and saves them.
    """
    state = request.session.get('state')
    business_name = request.session.get('business_name')
    
    if not state or not business_name:
        return JSONResponse(status_code=400, content={"error": "Invalid state or missing business name."})

    if not GOOGLE_CLIENT_SECRET_JSON:
        return JSONResponse(status_code=500, content={"error": "Google Calendar integration is not configured."})

    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRET_JSON,
        scopes=['https://www.googleapis.com/auth/calendar.events', 'https://www.googleapis.com/auth/calendar.readonly'],
        redirect_uri=str(request.url_for('oauth2callback')),
        state=state
    )

    # Use the full URL from the request to fetch the token
    authorization_response = str(request.url)
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    
    # Save the credentials to the database
    await db_utils.save_google_auth(business_name, credentials)
    
    return JSONResponse(content={"status": "success", "message": f"Successfully authenticated Google Calendar for {business_name}."})


# --- VAPI Tool Endpoint ---
class UserQuery(BaseModel):
    query: str

@app.post("/{business_name}/get-context")
async def get_context_for_vapi(business_name: str, user_query: UserQuery):
    """
    This endpoint is called by the Vapi assistant as a tool.
    It performs a RAG lookup and returns the context.
    """
    try:
        retriever = get_retriever(business_name)
        if not retriever:
            return JSONResponse(status_code=500, content={"error": f"Retriever not found for {business_name}"})

        # Get context from Pinecone
        docs = retriever.invoke(user_query.query)
        context = "\n\n".join([doc.page_content for doc in docs])

        # Check for Google Calendar auth to provide calendar status
        google_auth_creds = await db_utils.get_google_auth(business_name)
        calendar_status = "enabled" if google_auth_creds else "disabled"

        # Combine the context and calendar status into a single result
        combined_result = f"CONTEXT:\n{context}\n\nCALENDAR_STATUS:\n{calendar_status}"

        # The key in the response must be "result"
        return {"result": combined_result}

    except Exception as e:
        print(f"!!! TOOL ERROR in get_context_for_vapi: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# --- Retell AI Tool Endpoint ---
class RetellUserQuery(BaseModel):
    query: str

@app.post("/{business_name}/retell-get-context")
async def get_context_for_retell(business_name: str, request: Request):
    """
    This endpoint is called by the Retell assistant as a tool.
    It performs a RAG lookup and returns the context in a format
    that Retell expects.
    """
    try:
        # Retell sends the tool parameters in the request body as a JSON object.
        # The 'query' will be inside the 'parameters' key.
        body = await request.json()
        user_query_params = body.get("parameters", {})
        user_query = user_query_params.get("query")

        if not user_query:
            return JSONResponse(status_code=400, content={"error": "Missing 'query' in parameters"})

        retriever = get_retriever(business_name)
        if not retriever:
            return JSONResponse(status_code=500, content={"error": f"Retriever not found for {business_name}"})

        # Get context from Pinecone
        docs = retriever.invoke(user_query)
        context = "\n\n".join([doc.page_content for doc in docs])
        
        # Retell expects the output of the tool in a specific JSON format.
        # We will return the context as a JSON object with a key like "context".
        # This can be customized based on what the Retell prompt expects.
        return {"context": context}

    except Exception as e:
        print(f"!!! TOOL ERROR in get_context_for_retell: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# --- VAPI Unified Webhook ---
@app.post("/{business_name}/vapi-webhook")
async def handle_vapi_webhook(request: Request, business_name: str):
    """
    This single endpoint handles all VAPI events.
    - It logs call data to the database.
    - For user turns, it retrieves context and provides it to Vapi's LLM.
    """
    payload = await request.json()
    message = payload.get('message', {})
    event_type = message.get('type')

    # (Database logging remains the same)
    if event_type in ['status-update', 'end-of-call-report', 'function-call']:
        try:
            if event_type == 'status-update':
                if message.get('status') == 'in-progress':
                    await db_utils.create_call_record(message)
            elif event_type == 'end-of-call-report':
                await db_utils.finalize_call_record(message)
                if message.get('conversation'):
                    call_id = message.get('call', {}).get('id')
                    for turn in message['conversation']:
                        if turn.get('role') == 'assistant' and turn.get('content'):
                            await db_utils.save_transcript_turn(
                                call_id=call_id,
                                speaker=turn['role'],
                                content=turn.get('content')
                            )
            elif event_type == 'function-call':
                function_call = message.get('functionCall', {})
                tool_call_id = function_call.get('id')

                if function_call.get('name') == 'schedule_appointment':
                    params = function_call.get('parameters', {})
                    result = await calendar_tool.create_calendar_event(
                        business_name=business_name,
                        summary=params.get('summary'),
                        start_time=params.get('start_time'),
                        end_time=params.get('end_time'),
                        description=params.get('description', '')
                    )
                    # Vapi expects a specific format for tool call responses.
                    return JSONResponse(content={
                        "tool_outputs": [{
                            "tool_call_id": tool_call_id,
                            "output": result
                        }]
                    })
                
                elif function_call.get('name') == 'check_calendar_availability':
                    params = function_call.get('parameters', {})
                    result = await calendar_tool.get_available_slots(
                        business_name=business_name,
                        start_time=params.get('start_time'),
                        end_time=params.get('end_time')
                    )
                    # Vapi expects a specific format for tool call responses.
                    return JSONResponse(content={
                        "tool_outputs": [{
                            "tool_call_id": tool_call_id,
                            "output": result
                        }]
                    })

        except Exception as e:
            print(f"!!! DATABASE/TOOL ERROR: {e}")
        
        # We don't need to send a model response for these event types
        return JSONResponse(content={"status": "success"})


    # --- For 'conversation-update', provide the static model config ---
    if event_type == 'conversation-update':
        # Log the latest turn to the database
        conversation = message.get('conversation', [])
        if conversation:
            latest_turn = conversation[-1]
            call_id = message.get('call', {}).get('id')
            if call_id and latest_turn.get('content') and latest_turn.get('role') in ['user', 'assistant']:
                 try:
                    await db_utils.save_transcript_turn(
                        call_id=call_id,
                        speaker=latest_turn['role'],
                        content=latest_turn['content']
                    )
                 except Exception as e:
                    print(f"!!! TRANSCRIPT LOGGING ERROR: {e}")

        # This is the static prompt that will be used for every turn.
        static_system_prompt = f"""
        You are "Riley," a world-class AI receptionist and scheduling assistant for **{business_name}**.

        Your primary objectives are to provide exceptional, professional customer service by answering questions and to efficiently schedule service appointments using a strict, step-by-step process.

        Your tone is professional, warm, and highly competent. You are helpful and proactive, but also concise and to the point. Emulate the best human receptionist you can imagine.

        ---

        ### **Core Directives & Rules of Engagement**

        1.  **Identity & Persona:**
            *   Always speak on behalf of the business. Use "we," "our," and "us."
            *   Never reveal you are an AI unless directly asked. If a user asks "Are you a robot?" or similar, respond calmly with: "I'm a proprietary AI assistant developed to help {business_name}." Do not mention OpenAI, Google, or any other company.

        2.  **Knowledge & Information:**
            *   Your knowledge is **strictly and exclusively** limited to the information returned by the `get_context` tool.
            *   For every user question or statement, you **MUST FIRST** call the `get_context` tool with the user's query.
            *   The tool will return a `CONTEXT:` section and a `CALENDAR_STATUS:` section.
            *   If a user asks a question that cannot be answered from the provided `CONTEXT`, you **MUST** respond with: "That's a great question, but I don't have access to that specific information right now." Do not apologize or try to find the answer elsewhere.

        3.  **Tool Use Protocol (CRITICAL):**
            *   You are forbidden from discussing the results or outcome of a tool before you have actually called the tool and received its output.
            *   Do not combine steps. For example, do not say "I will check the calendar and book it for you." You must check, report the result, and then book.

        ---

        ### **Mandatory Scheduling Workflow**

        When a user expresses intent to book or schedule, you **MUST** first call the `get_context` tool with their request to check the `CALENDAR_STATUS`.

        *   If `CALENDAR_STATUS` is **'disabled'**, you **MUST** inform the user that the online scheduling system is unavailable. Say: *"Our online scheduling system is currently unavailable. I can still answer questions, but I can't book appointments at this time."* Do not attempt to proceed with scheduling.
        *   If `CALENDAR_STATUS` is **'enabled'**, you **MUST** follow this sequence precisely:

        *   **Step 1: Get Service Address & Check Jurisdiction**
            *   The very first detail you must ask for is the **complete physical address** for the service call.
            *   Immediately check the `CONTEXT` from your tool call to find our service area.
            *   If the user's address is outside the service area, politely stop the process.
            *   If the address is within the service area, proceed to the next step.

        *   **Step 2: Comprehensive Information Gathering**
            *   Gather the user's **Full Name**, **Phone Number**, the **specific service they require**, and a **valid Email Address**.

        *   **Step 3: Check Availability**
            *   Ask for their desired date and time.
            *   Your next action **MUST** be to use the `check_calendar_availability` tool.

        *   **Step 4: Communicate Results & Ask for Confirmation**
            *   Based on the tool's output, inform the user if the time is available or not. If it is, **ask for explicit permission to book**.

        *   **Step 5: Execute the Booking**
            *   **Only after** user confirmation, use the `schedule_appointment` tool. Include all collected details in the `description`.

        *   **Step 6: Provide Final Confirmation**
            *   Confirm the appointment was successful based on the tool's output.
        """

        # Define the model configuration with the static prompt and tools
        model_config = {
            "provider": "openai",
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": static_system_prompt}
            ],
            "tools": [
                get_context_tool,
                schedule_appointment_tool,
                check_calendar_availability_tool
            ]
        }
        
        # Vapi expects the 'model' key in the JSON response
        return JSONResponse(content={"model": model_config})

    return JSONResponse(content={"status": "unhandled_event"})


# --- Main Entry Point ---
if __name__ == "__main__":
    print("This script is not meant to be run directly.")
    print("Please run the FastAPI server using uvicorn.")
    print('Example: python3 -m uvicorn src.core_api.main:app --reload') 