import uvicorn
import os
from fastapi import FastAPI, Request
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables at the very top
load_dotenv()

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser

# --- 1. Initialize FastAPI App ---
app = FastAPI(
    title="AI Voice Agent Backend",
    description="This server provides responses to a Vapi voice agent.",
    version="1.0.0"
)

# --- 2. Load Vector Store and Set Up RAG Chain ---
FAISS_STORE_PATH = "faiss_vector_store"
LLM_MODEL = "gpt-4o"

try:
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vector_store = FAISS.load_local(FAISS_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
    
    retriever = vector_store.as_retriever(
        search_type="mmr",
        search_kwargs={'k': 5}
    )

    template = """
    You are an AI assistant for a business. Answer the user's question by prioritizing the information found in the following context.
    If the context doesn't contain the answer, use your general knowledge, but clearly state that the information is not from the provided source.

    Context:
    {context}

    Question:
    {question}
    """
    prompt = ChatPromptTemplate.from_template(template)
    llm = ChatOpenAI(model=LLM_MODEL, temperature=0.7)

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

# --- 3. Define Vapi Webhook Endpoint ---
class VapiPayload(BaseModel):
    message: dict

@app.post("/vapi-webhook")
async def handle_vapi_webhook(payload: VapiPayload):
    """
    This endpoint is called by Vapi with the transcribed text of the user's speech.
    It processes the text through the RAG chain and returns the answer.
    """
    if payload.message['type'] == 'transcript' and payload.message['transcriptType'] == 'final':
        transcribed_text = payload.message['transcript']
        print(f"Received transcript: {transcribed_text}")

        if rag_chain and transcribed_text:
            answer = rag_chain.invoke(transcribed_text)
            print(f"Generated answer: {answer}")
            return {"answer": answer}
        
    return {"answer": "I'm sorry, I couldn't process that."}

# --- 4. Make the app runnable with uvicorn ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 