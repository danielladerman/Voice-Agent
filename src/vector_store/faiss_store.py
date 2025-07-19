import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

# Load environment variables from .env file
load_dotenv()

def create_and_save_vector_store(text_content: str, file_path: str):
    """
    Creates a FAISS vector store from text content and saves it to a file.

    Args:
        text_content: The text content to process.
        file_path: The path to save the FAISS index file.
    """
    if not text_content:
        print("Error: Text content is empty. Cannot create vector store.")
        return

    try:
        # 1. Split the text into manageable chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # The size of each chunk in characters
            chunk_overlap=200, # The number of characters to overlap between chunks
            length_function=len
        )
        chunks = text_splitter.split_text(text_content)

        if not chunks:
            print("Error: Failed to split text into chunks.")
            return

        print(f"Split text into {len(chunks)} chunks.")

        # 2. Create embeddings for the chunks using OpenAI
        # This will use the OPENAI_API_KEY from the .env file
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        
        # 3. Create the FAISS vector store from the text chunks
        print("Creating FAISS vector store...")
        vector_store = FAISS.from_texts(texts=chunks, embedding=embeddings)
        
        # 4. Save the vector store locally
        vector_store.save_local(file_path)
        print(f"Successfully saved vector store to {file_path}")

    except Exception as e:
        print(f"An error occurred while creating the vector store: {e}")


if __name__ == '__main__':
    # This block allows us to test the vector store creation directly
    from src.data_ingestion.scraper import scrape_website

    # Define the URL to scrape and the file path for the vector store
    TEST_URL = "https://python.langchain.com/v0.2/docs/introduction/"
    STORE_PATH = "faiss_vector_store"

    print("--- Starting Vector Store Creation Test ---")
    
    # Step 1: Scrape the website content
    print(f"Scraping website: {TEST_URL}")
    content = scrape_website(TEST_URL)

    if content:
        # Step 2: Create and save the vector store from the content
        create_and_save_vector_store(content, STORE_PATH)
    else:
        print("Failed to scrape website content. Aborting vector store creation.")
    
    print("--- Vector Store Creation Test Finished ---") 