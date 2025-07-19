import uvicorn
import os
from fastapi import FastAPI
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

# --- Global RAG Chain Cache ---
rag_chain_cache = {}
LLM_MODEL = "gpt-4o"
PERSIST_DIRECTORY = "chroma_db"

def get_rag_chain(business_name: str):
    """
    Initializes and caches the RAG chain for a specific business by loading
    their ChromaDB collection. If the chain is already in the cache, returns it.
    """
    if business_name in rag_chain_cache:
        print(f"Returning cached RAG chain for '{business_name}'.")
        return rag_chain_cache[business_name]

    print(f"Initializing RAG chain for business '{business_name}'...")
    try:
        # Sanitize the business name to get the collection name
        collection_name = "".join(e for e in business_name if e.isalnum() or e in ['_', '-']).lower()
        
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        
        vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=PERSIST_DIRECTORY,
        )
        
        # Check if the collection is empty
        # Note: This is a simple check. LangChain's Chroma wrapper doesn't expose a direct count.
        # We try fetching one document. If it fails or returns none, we assume it's empty/missing.
        try:
            test_retrieval = vector_store.similarity_search("", k=1)
            if not test_retrieval:
                print(f"Warning: No documents found for '{business_name}' in collection '{collection_name}'.")
                # We can still proceed, but the RAG chain will have no context.
        except Exception:
             print(f"Error: Collection '{collection_name}' for business '{business_name}' not found or is empty.")
             return None


        retriever = vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={'k': 5}
        )

        def log_retrieved_documents(docs):
            print("\n--- Documents retrieved from vector store ---")
            if not docs:
                print("!!! No documents were retrieved.")
            for i, doc in enumerate(docs):
                clean_doc = doc.page_content[:100].replace('\n', ' ')
                print(f"Doc {i+1}: \"{clean_doc}...\"")
            print("--- End of retrieved documents ---\n")
            return docs

        template = """
        You are the official AI assistant representing {business_name}. Your role is to act as a knowledgeable and helpful member of the team.

        **Core Instructions:**
        1.  **Speak in the First Person Plural:** Always use "we," "our," and "us" when talking about {business_name}. For example, instead of saying "{business_name} provides...", you must say "We provide...".
        2.  **Assert Your Identity:** If asked who you work for, state that you are a proprietary AI assistant developed by {business_name}. Under no circumstances should you mention OpenAI, GPT, or that you are a large language model.
        3.  **Use the Provided Context:** Base your answers on the information from the company's website, which is provided below in the 'Context' section.
        4.  **Handle Unknown Questions:** If the user asks something that isn't covered in the context, politely say that you don't have that information. For example: "I don't have the details on that at the moment, but I can tell you about our main services."

        **Context:**
        {{context}}

        **Question:**
        {{question}}
        """
        prompt = ChatPromptTemplate.from_template(template.format(business_name=business_name))
        llm = ChatOpenAI(model=LLM_MODEL, temperature=0.7)

        rag_chain = (
            {
                "context": retriever | RunnableLambda(log_retrieved_documents), 
                "question": RunnablePassthrough()
            }
            | prompt
            | llm
            | StrOutputParser()
        )
        
        # Cache the newly created chain
        rag_chain_cache[business_name] = rag_chain
        print(f"Successfully initialized and cached RAG chain for '{business_name}'.")
        return rag_chain

    except Exception as e:
        print(f"Error initializing RAG chain for '{business_name}': {e}")
        return None

# --- FastAPI App ---
app = FastAPI(
    title="AI Voice Agent Backend",
    description="This server provides responses to a Vapi voice agent for multiple businesses.",
    version="1.1.0"
)

# The startup event is no longer needed as we initialize chains on-demand.
# @app.on_event("startup")
# async def startup_event(): ...

# --- Vapi Webhook Endpoint ---
class VapiPayload(BaseModel):
    message: dict

@app.post("/{business_name}/vapi-webhook")
async def handle_vapi_webhook(business_name: str, payload: VapiPayload):
    """
    This endpoint is called by Vapi. The `business_name` is extracted from the URL
    to dynamically load the appropriate RAG chain.
    """
    print(f"\n=== WEBHOOK CALLED FOR BUSINESS: {business_name} ===")
    print(f"Payload type: {payload.message.get('type')}")
    print(f"Transcript type: {payload.message.get('transcriptType')}")
    
    # Try to get the RAG chain for the specified business
    rag_chain = get_rag_chain(business_name)

    if not rag_chain:
        print(f"Could not initialize RAG chain for '{business_name}'.")
        return {"answer": f"I'm sorry, the system for {business_name} is not available."}

    if payload.message['type'] == 'transcript' and payload.message['transcriptType'] == 'final':
        transcribed_text = payload.message['transcript']
        print(f"Received transcript: {transcribed_text}")
        
        if transcribed_text:
            print("Invoking RAG chain...")
            try:
                answer = rag_chain.invoke(transcribed_text)
                print(f"Generated answer: {answer}")
                return {"answer": answer}
            except Exception as e:
                print(f"ERROR in RAG chain: {e}")
                return {"answer": "I'm sorry, I encountered an error processing that request."}
        
    print("=== END WEBHOOK ===\n")
    return {"answer": "I'm sorry, I didn't receive a valid transcript. Please try again."}

# --- Main Entry Point ---
if __name__ == "__main__":
    print("This script is not meant to be run directly.")
    print("Please run the FastAPI server using uvicorn.")
    print('Example: python3 -m uvicorn src.core_api.main:app --reload') 