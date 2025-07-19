import chromadb
import argparse

# --- Configuration ---
PERSIST_DIRECTORY = "chroma_db"

def inspect_collection(collection_name: str):
    """
    Connects to the persistent ChromaDB and inspects a collection.
    """
    print(f"Connecting to ChromaDB at '{PERSIST_DIRECTORY}'...")
    try:
        client = chromadb.PersistentClient(path=PERSIST_DIRECTORY)
        
        print("\nAvailable collections:")
        collections = client.list_collections()
        for c in collections:
            print(f"  - {c.name} (Items: {c.count()})")

        print(f"\n--- Inspecting collection: '{collection_name}' ---")
        collection = client.get_collection(name=collection_name)
        
        count = collection.count()
        if count == 0:
            print("The collection is empty.")
            return

        print(f"The collection contains {count} documents.")
        
        # Get a peek at the first 5 documents
        data = collection.peek(limit=5)
        
        print("\nFirst 5 document snippets:")
        for doc in data['documents']:
            clean_doc = doc[:80].replace('\n', ' ')
            print(f"  - \"{clean_doc}...\"")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        print("Please ensure the collection name is correct and the database exists.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect a ChromaDB collection.")
    parser.add_argument("--name", type=str, required=True, help="The name of the collection to inspect.")
    
    args = parser.parse_args()
    
    inspect_collection(collection_name=args.name) 