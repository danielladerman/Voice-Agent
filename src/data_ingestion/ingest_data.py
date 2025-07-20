import requests
from bs4 import BeautifulSoup
import argparse
import time
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
INDEX_NAME = "voice-agent-data"

def scrape_website(url: str) -> str:
    """
    Scrapes a JavaScript-rendered website using Selenium and returns the text content.
    """
    print("   ...Using Selenium to load JavaScript content.")
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run Chrome in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        
        # Wait for JavaScript to load. A fixed delay is simple but effective here.
        time.sleep(3)
        
        html = driver.page_source
        driver.quit()
        
        soup = BeautifulSoup(html, 'html.parser')
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        for tag in main_content(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        text = ' '.join(main_content.get_text(separator=' ', strip=True).split())
        return text
    except Exception as e:
        print(f"Error during Selenium scraping for URL {url}: {e}")
        if 'driver' in locals():
            driver.quit()
        return ""

def ingest_data(url: str, business_name: str):
    """
    Scrapes a URL, processes the text, and ingests it into a Pinecone index.
    The `business_name` is used as a namespace within the index.
    """
    print(f"--- Starting ingestion for URL: {url} ---")
    
    # 1. Scrape the website content
    print("Step 1: Scraping website content...")
    scraped_text = scrape_website(url)
    if not scraped_text:
        print("Scraping failed. Aborting ingestion.")
        return
    print(f"   ...Scraped {len(scraped_text)} characters.")

    # 2. Split the text into manageable chunks
    print("Step 2: Splitting text into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    documents = text_splitter.create_documents([scraped_text])
    print(f"   ...Split into {len(documents)} documents.")

    # 3. Get embeddings and initialize Pinecone
    print("Step 3: Initializing embeddings and vector store...")
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        dimensions=512  # Specify the dimension to match Pinecone index
    )
    
    # Sanitize the business_name to be used as a namespace
    namespace = "".join(e for e in business_name if e.isalnum() or e in ['_', '-']).lower()
    
    print(f"Step 4: Upserting documents to Pinecone index '{INDEX_NAME}' with namespace '{namespace}'...")
    vector_store = PineconeVectorStore.from_documents(
        documents=documents,
        embedding=embeddings,
        index_name=INDEX_NAME,
        namespace=namespace
    )
    
    print("\n--- Ingestion Complete ---")
    print(f"Successfully ingested {len(documents)} documents into the '{INDEX_NAME}' index under the '{namespace}' namespace.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Scrape a website and ingest its content into a Pinecone index.")
    parser.add_argument("url", type=str, help="The URL of the website to scrape.")
    parser.add_argument("business_name", type=str, help="The business name, used as a namespace in Pinecone.")
    
    args = parser.parse_args()
    
    ingest_data(args.url, args.business_name)
