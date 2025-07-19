import os
import sys
import argparse
import chromadb
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.data_ingestion.scraper import scrape_website
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

# --- Configuration ---
load_dotenv()

# We will use a local, persistent ChromaDB instance.
# The data will be stored in the 'chroma_db' directory.
PERSIST_DIRECTORY = "chroma_db"
TEXT_CHUNK_SIZE = 1000
TEXT_CHUNK_OVERLAP = 100

def ingest_for_business(business_name: str, url: str):
    """
    Scrapes a website, processes the text, and stores it in a dedicated
    ChromaDB collection for a specific business.
    """
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found. Please set it in your .env file.")
        return

    # --- 1. Sanitize business_name to be a valid collection name ---
    # ChromaDB collection names must be >2 chars, alphanumeric, and can contain _ or -
    collection_name = "".join(e for e in business_name if e.isalnum() or e in ['_', '-']).lower()
    if len(collection_name) < 3:
        raise ValueError(f"Sanitized business name '{collection_name}' is too short. Must be at least 3 characters.")
    print(f"Using sanitized collection name: {collection_name}")

    # --- 2. Scrape Content ---
    print(f"Scraping content from {url}...")
    text_content = scrape_website(url)
    if not text_content:
        print("No content was scraped. Aborting.")
        return

    # --- 3. Split Text into Chunks ---
    print("Splitting text into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=TEXT_CHUNK_SIZE,
        chunk_overlap=TEXT_CHUNK_OVERLAP
    )
    documents = text_splitter.split_text(text_content)
    print(f"Created {len(documents)} text chunks.")

    # --- 4. Initialize ChromaDB in Persistent Mode ---
    print(f"Initializing ChromaDB in persistent mode at '{PERSIST_DIRECTORY}'...")
    try:
        # This will create the directory if it doesn't exist and load the DB.
        client = chromadb.PersistentClient(path=PERSIST_DIRECTORY)
        
        # If the collection already exists, delete it first.
        try:
            client.delete_collection(name=collection_name)
            print(f"Existing collection '{collection_name}' deleted.")
        except Exception:
            pass # Collection didn't exist, which is fine.

        # Create the collection.
        collection = client.create_collection(name=collection_name)

    except Exception as e:
        print(f"Error initializing or preparing ChromaDB: {e}")
        return

    # --- 5. Generate Embeddings and Add to Collection ---
    print("Generating embeddings and adding to ChromaDB collection...")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    embedded_documents = embeddings.embed_documents(documents)
    
    # ChromaDB requires a list of IDs for each document
    ids = [str(i) for i in range(len(documents))]
    
    collection.add(
        embeddings=embedded_documents,
        documents=documents,
        ids=ids
    )

    print(f"\nSuccessfully ingested data for '{business_name}' into collection '{collection_name}'.")
    print(f"Total items in collection: {collection.count()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest data for a specific business into ChromaDB.")
    parser.add_argument("--name", type=str, required=True, help="The name of the business (e.g., 'Retell AI').")
    parser.add_argument("--url", type=str, required=True, help="The URL of the business's website to scrape.")
    
    args = parser.parse_args()
    
    ingest_for_business(business_name=args.name, url=args.url) 