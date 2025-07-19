import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables at the very top
load_dotenv()

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser
from src.stt.whisper_stt import transcribe_audio
from src.tts.eleven_labs_tts import text_to_speech_stream

# Load environment variables from .env file
# load_dotenv()

# --- 1. Initialize FastAPI App ---
app = FastAPI(
    title="AI Voice Agent API",
    description="API for the AI Voice Agent to handle questions using a knowledge base.",
    version="1.0.0"
)

# --- Add CORS middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# --- 2. Load Vector Store and Set Up RAG Chain ---
FAISS_STORE_PATH = "faiss_vector_store"
LLM_MODEL = "gpt-4o"

try:
    # Load the vector store with the embeddings model
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vector_store = FAISS.load_local(FAISS_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
    
    # Create a retriever from the vector store
    retriever = vector_store.as_retriever(
        search_type="mmr",  # Use Maximal Marginal Relevance for diverse results
        search_kwargs={'k': 5} # Retrieve top 5 most relevant chunks
    )

    # Define the prompt template for the LLM
    template = """
    You are an AI assistant for a business. Answer the user's question by prioritizing the information found in the following context.
    If the context doesn't contain the answer, use your general knowledge, but clearly state that the information is not from the provided source.

    Context:
    {context}

    Question:
    {question}
    """
    prompt = ChatPromptTemplate.from_template(template)

    # Initialize the LLM
    llm = ChatOpenAI(model=LLM_MODEL, temperature=0.7)

    # Create the RAG (Retrieval-Augmented Generation) chain
    rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    print("Successfully loaded vector store and created RAG chain.")

except Exception as e:
    print(f"Error loading vector store or creating RAG chain: {e}")
    rag_chain = None

# --- 3. Define API Endpoints ---
class QuestionRequest(BaseModel):
    query: str

@app.post("/ask")
async def ask_question(request: QuestionRequest):
    """
    Receives a question, processes it through the RAG chain, and returns the answer.
    """
    if not rag_chain:
        return {"error": "RAG chain is not available. Please check server logs."}
    
    if not request.query:
        return {"error": "Query cannot be empty."}

    try:
        print(f"Received query: {request.query}")
        answer = rag_chain.invoke(request.query)
        print(f"Generated answer: {answer}")
        return {"answer": answer}
    except Exception as e:
        print(f"Error invoking RAG chain: {e}")
        return {"error": "Failed to process the question."}

# --- 4. Add WebSocket Endpoint for Real-Time Interaction ---
@app.websocket("/ws/talk")
async def websocket_talk(websocket: WebSocket):
    """
    Handles real-time voice interaction over a WebSocket connection.
    - Receives audio stream from the client.
    - Orchestrates the STT -> RAG -> TTS pipeline.
    - Streams audio response back to the client.
    """
    await websocket.accept()
    print("WebSocket connection established for real-time talk.")
    audio_buffer = []

    try:
        while True:
            data = await websocket.receive_bytes()

            # A zero-byte message indicates the end of the audio stream
            if len(data) == 0:
                print("End of stream message received.")
                if audio_buffer:
                    full_audio_bytes = b''.join(audio_buffer)
                    print(f"Processing {len(full_audio_bytes)} bytes of audio for transcription...")
                    
                    transcribed_text = await transcribe_audio(full_audio_bytes)
                    audio_buffer = []  # Clear buffer for next turn
                    
                    print(f"Transcription: {transcribed_text}")
                    
                    if transcribed_text and rag_chain:
                        print("Sending transcription to RAG chain...")
                        answer = rag_chain.invoke(transcribed_text)
                        print(f"RAG chain answer: {answer}")
                        
                        print("Streaming TTS response...")
                        async for chunk in text_to_speech_stream(answer):
                            if chunk:
                                await websocket.send_bytes(chunk)
                        print("Finished streaming TTS response.")
                        # Send a completion message to the client
                        await websocket.send_text("TTS_COMPLETE")

                    elif not rag_chain:
                        print("RAG chain is not available.")
                        # We can't send a text message on a bytes-only connection,
                        # so we'll just log it on the server.
                    else:
                        print("Transcription was empty.")
                continue

            audio_buffer.append(data)
            print(f"Received audio chunk of size: {len(data)} bytes")

    except WebSocketDisconnect:
        print("WebSocket connection closed.")
            
    except Exception as e:
        print(f"An error occurred in the WebSocket connection: {e}")
        await websocket.close(code=1011)

# This root endpoint is removed to prevent conflict with the static file server
# --- 5. Add a root endpoint for health checks ---
# @app.get("/")
# def read_root():
#     return {"status": "AI Voice Agent API is running"}

# --- Mount Static Files ---
# This must be mounted after all other routes
app.mount("/", StaticFiles(directory="html", html=True), name="static")

# --- 6. Make the app runnable with uvicorn ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 