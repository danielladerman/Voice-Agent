import uvicorn
import os
from dotenv import load_dotenv

if __name__ == "__main__":
    # For local development only, allow insecure transport for OAuthlib.
    # This is required because the server is running on http:// and not https://.
    # We now know this is needed for the local machine setup.
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    
    # Load environment variables from .env file BEFORE starting the server.
    print("--- Loading environment variables from .env file ---")
    load_dotenv()
    
    # Now, run the Uvicorn server
    uvicorn.run(
        "src.core_api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    ) 