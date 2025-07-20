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
    try:
        if event_type == 'status-update':
            if message.get('status') == 'in-progress':
                await db_utils.create_call_record(message)
        elif event_type == 'end-of-call-report':
            # --- TEMPORARY DEBUGGING: Print the full end-of-call report ---
            print(f"END OF CALL REPORT (RAW): {message}")
            # ----------------------------------------------------------------

            # Finalize the main call record
            await db_utils.finalize_call_record(message)
            # Log all assistant turns from the final transcript.
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
            if message.get('functionCall', {}).get('name') == 'book_appointment':
                await db_utils.create_appointment(message['call']['id'], message['functionCall']['parameters'])
            elif message.get('functionCall', {}).get('name') == 'schedule_appointment':
                # Call the Google Calendar tool
                params = message['functionCall']['parameters']
                result = await calendar_tool.create_calendar_event(
                    business_name=business_name,
                    summary=params.get('summary'),
                    start_time=params.get('start_time'),
                    end_time=params.get('end_time'),
                    description=params.get('description', '')
                )
                
                # Here you would typically send the result back to Vapi's LLM
                # For now, we'll just log it.
                print(f"--- CALENDAR: Event creation result: {result}")
            
            elif message.get('functionCall', {}).get('name') == 'check_calendar_availability':
                # Call the Google Calendar availability tool
                params = message['functionCall']['parameters']
                result = await calendar_tool.get_available_slots(
                    business_name=business_name,
                    start_time=params.get('start_time'),
                    end_time=params.get('end_time')
                )
                
                # Send the result of the function call back to the LLM
                return JSONResponse(content={
                    "tool_outputs": [{
                        "tool_call_id": message['functionCall']['id'],
                        "output": result
                    }]
                })


    except Exception as e:
        print(f"!!! DATABASE LOGGING ERROR: {e}")

    # --- Context Injection & Transcript Logging Section ---
    if event_type == 'conversation-update':
        conversation = message.get('conversation', [])
        if not conversation:
            return JSONResponse(content={"status": "no conversation to process"})

        latest_turn = conversation[-1]
        call_id = message.get('call', {}).get('id')

        # Real-time processing for USER turns only.
        if latest_turn.get('role') == 'user':
            # Log user turn to DB
            if call_id and latest_turn.get('content'):
                try:
                    await db_utils.save_transcript_turn(
                        call_id=call_id,
                        speaker=latest_turn['role'],
                        content=latest_turn['content']
                    )
                except Exception as e:
                    print(f"!!! TRANSCRIPT LOGGING ERROR: {e}")

            # Trigger RAG based on the user's turn
            transcribed_text = latest_turn.get('content')
            if transcribed_text:
                # Get the retriever for the specific business
                retriever = get_retriever(business_name)
                
                # Check if the business has Google Calendar auth
                google_auth_creds = await db_utils.get_google_auth(business_name)
                
                tools = []
                if google_auth_creds:
                    tools.append(schedule_appointment_tool)
                    tools.append(check_calendar_availability_tool)
                
                docs = retriever.invoke(transcribed_text)
                
                # Format the documents into a string for the prompt
                context = "\n\n".join([doc.page_content for doc in docs])

                # Build the new system prompt with the retrieved context
                system_prompt_template = f"""
                You are the official AI assistant representing {business_name}. Your role is to act as a knowledgeable and helpful member of the team.
                Your primary goal is to answer questions accurately based on the provided context.

                **Core Instructions:**
                1.  **Speak in the First Person Plural:** Use "we," "our," and "us" when talking about {business_name}.
                2.  **Assert Your Identity:** If asked, state you are a proprietary AI assistant for {business_name}. Do not mention OpenAI or GPT.
                3.  **Use the Provided Context Exclusively:** Base your answers ONLY on the information from the 'Context' section below.
                4.  **Handle Unknown Questions:** If the user asks something not covered in the context, politely say you don't have that information.
                
                **Tool Usage Instructions for Scheduling:**
                - **NEVER** confirm an appointment without using your tools. Do not just say "I will schedule it."
                - **Step 1: Check Availability.** When a user asks to book an appointment, your first action MUST be to use the `check_calendar_availability` tool for the requested time slot.
                - **Step 2: Confirm with the User.** After the tool returns the result, inform the user whether the slot is free or busy. If it is free, ask for confirmation before booking.
                - **Step 3: Schedule the Appointment.** Once the user confirms, you MUST use the `schedule_appointment` tool to create the event in the calendar.
                - **Step 4: Final Confirmation.** After the `schedule_appointment` tool succeeds, and only then, give the final confirmation to the user (e.g., "Okay, I've confirmed that on our calendar for you.").

                **Context:**
                {context}
                """
                
                # We are overriding the model configuration for this turn
                model_config = {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": system_prompt_template}
                    ] + conversation
                }
                
                if tools:
                    model_config["tools"] = tools

                return JSONResponse(content={"model": model_config})

    return JSONResponse(content={"status": "success"})


# --- Main Entry Point ---
if __name__ == "__main__":
    print("This script is not meant to be run directly.")
    print("Please run the FastAPI server using uvicorn.")
    print('Example: python3 -m uvicorn src.core_api.main:app --reload') 