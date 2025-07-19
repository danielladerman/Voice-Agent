# AI Voice Agent

This project is a conversational AI voice agent capable of real-time, spoken conversations. It leverages a Retrieval-Augmented Generation (RAG) pipeline to answer questions based on a custom knowledge base.

## Core Technologies

*   **Backend API:** FastAPI
*   **Voice & Conversation:** Vapi AI
*   **Language Model:** OpenAI (GPT-4o)
*   **RAG Pipeline:** LangChain
*   **Vector Store:** FAISS (for local development)
*   **Orchestration:** Python

## How It Works

1.  **Real-Time Communication:** The user interacts with the agent through a voice call initiated by Vapi. Vapi handles the real-time transcription of the user's speech and the synthesis of the agent's spoken responses.
2.  **Webhook Integration:** Vapi sends the user's transcribed speech to our FastAPI backend via a webhook.
3.  **RAG Processing:** The backend receives the transcript and passes it as a query to a LangChain RAG pipeline.
4.  **Knowledge Retrieval:** The RAG pipeline's retriever searches a FAISS vector store to find relevant information from the project's knowledge base.
5.  **Response Generation:** The retrieved context and the original query are passed to an OpenAI language model, which generates a coherent, context-aware answer.
6.  **Spoken Response:** The generated answer is sent back to Vapi, which synthesizes it into speech and plays it back to the user in real-time.

## Setup and Installation

### 1. Prerequisites

*   Python 3.9+
*   [Ngrok](https://ngrok.com/download) for exposing the local server.

### 2. Clone the Repository

```bash
git clone <your-repository-url>
cd <your-repository-name>
```

### 3. Set Up Virtual Environment

It is highly recommended to use a virtual environment.

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Create a `.env` file in the project root and add your API keys:

```
OPENAI_API_KEY="sk-..."
VAPI_API_KEY="..."
```

You can get your Vapi key from the [Vapi Dashboard](https://vapi.ai/dashboard).

## Running the Agent

You will need three separate terminal windows.

### Terminal 1: Start the Backend Server

This server runs the RAG pipeline and exposes the webhook for Vapi.

```bash
python3 src/core_api/main.py
```

### Terminal 2: Expose the Server with Ngrok

Vapi needs a public URL to communicate with your local server.

```bash
ngrok http 8000
```
Copy the `https://...ngrok-free.app` URL provided by ngrok.

### Terminal 3: Start the Vapi Call

This script initiates the call with the Vapi service.

```bash
python3 run_vapi.py
```

When prompted, paste the ngrok URL you copied from the previous step. A browser window should open, connecting you to the voice agent.

## Project Structure
```
.
├── faiss_vector_store/ # Local vector store
├── src/
│   ├── core_api/
│   │   └── main.py     # FastAPI server and RAG logic
│   ├── data_ingestion/
│   │   └── scraper.py  # (Future use) Script for ingesting data
│   └── tts/
│       └── eleven_labs_tts.py # (Future use) for other TTS providers
├── .gitignore
├── Gemini.md
├── README.md
├── requirements.txt
├── run_vapi.py         # Script to initiate the Vapi call
└── venv/
``` 