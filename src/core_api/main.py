import uvicorn
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnableLambda

# Import the new database functions
from src.database import database as db_utils

# --- Global Retriever Cache ---
retriever_cache = {}
LLM_MODEL = "gpt-4o"
PERSIST_DIRECTORY = "chroma_db"

def get_retriever(business_name: str):
    """
    Initializes and caches a retriever for a specific business's ChromaDB collection.
    """
    if business_name in retriever_cache:
        return retriever_cache[business_name]

    try:
        collection_name = "".join(e for e in business_name if e.isalnum() or e in ['_', '-']).lower()
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=PERSIST_DIRECTORY,
        )
        
        retriever = vector_store.as_retriever(search_type="mmr", search_kwargs={'k': 5})
        retriever_cache[business_name] = retriever
        return retriever

    except Exception as e:
        print(f"Error initializing retriever for '{business_name}': {e}")
        return None

# --- FastAPI App ---
app = FastAPI(
    title="AI Voice Agent Backend",
    description="This server provides real-time context to a Vapi voice agent.",
    version="1.3.0"
)

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
    
    # --- TEMPORARY DEBUGGING ---
    # print(f"RAW MESSAGE PAYLOAD: {message}") # Cleaned up
    # --------------------------
    
    # print(f"\n=== WEBHOOK CALLED FOR: {business_name} | EVENT: {event_type} ===") # Cleaned up

    # (Database logging remains the same)
    try:
        if event_type == 'status-update':
            if message.get('status') == 'in-progress':
                await db_utils.create_call_record(message)
        elif event_type == 'end-of-call-report':
            # This event contains the full transcript and final call details.
            await db_utils.finalize_call_record(message)
            if message.get('transcript'):
                await db_utils.save_transcript(message['call']['id'], message['transcript'])
        elif event_type == 'function-call':
            if message.get('functionCall', {}).get('name') == 'book_appointment':
                await db_utils.create_appointment(message['call']['id'], message['functionCall']['parameters'])
    except Exception as e:
        print(f"!!! DATABASE LOGGING ERROR: {e}")

    # --- Context Injection Section ---
    # We trigger the RAG chain on a 'conversation-update' when the last turn is from the user.
    if event_type == 'conversation-update':
        conversation = message.get('conversation', [])
        # Ensure the conversation is not empty and the last message is from the user
        if conversation and conversation[-1].get('role') == 'user':
            transcribed_text = conversation[-1].get('content')

            if transcribed_text:
                # Get the retriever for the specific business
                retriever = get_retriever(business_name)
                
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

                **Context:**
                {context}
                """
                
                # We are overriding the model configuration for this turn
                return JSONResponse(content={
                    "model": {
                        "provider": "openai",
                        "model": "gpt-4o",
                        "messages": [
                            {"role": "system", "content": system_prompt_template}
                        ] + conversation
                    }
                })

    return JSONResponse(content={"status": "success"})


# --- Main Entry Point ---
if __name__ == "__main__":
    print("This script is not meant to be run directly.")
    print("Please run the FastAPI server using uvicorn.")
    print('Example: python3 -m uvicorn src.core_api.main:app --reload') 