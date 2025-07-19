# Project Activity Log

This document tracks prompts and actions taken during the development of the AI Voice Agent.

---
### 2024-07-25: Initial Setup

**USER PROMPT:** "Lets brainstorm an ai voice agent that can be trained on businsses websites to learn everything about it so it could handle FAQs and scheduling inquiries, basically act as an appointment setter, that can handle objections, learn from past conversations and become more powerful overtime"

**USER PROMPT:** "a few questions: what is FAISS I have heared that pinecone is a good vector databse where can we log all the interactions made with the voice agent? Ideally the voice agent would be a number on a website that when people call they contact the ai, then the ai relays the info to the businseess team. Also, we should make a dashboard to track the interactions of the voice agent so it could improve on past conveersation and we know how to fine tune it"

**USER PROMPT:** "What do you think of this? Make sure to write a requirements file, make sure to add this: Gemini.md..."

**USER PROMPT:** "are they suitable for our voice agent project?"

**USER PROMPT:** "lets do it!!"

**AGENT ACTIONS:**
1.  Created `Gemini.md` with user-provided guidelines.
2.  Created `requirements.txt` with initial Python packages.
3.  Created directory structure: `tasks/`, `docs/`, `src/`.
4.  Created `tasks/todo.md` with the initial project plan.
5.  Created `docs/activity.md` for logging.
6.  Created `.gitignore`.
7.  Marked Task 1 as complete in `tasks/todo.md`.

---
### 2024-07-25: Environment Setup

**AGENT ACTIONS:**
1.  Created Python virtual environment `venv`.
2.  Installed all packages from `requirements.txt` into `venv`.
3.  Marked Task 2 as complete in `tasks/todo.md`.

---
### 2024-07-25: Web Scraper Implementation

**USER PROMPT:** "can you create the new file scraper.py while i create the .env file"
**USER PROMPT:** "what do i need to add to the .env file"
**USER PROMPT:** "k i added the openai api key to the .env whats now"

**AGENT ACTIONS:**
1.  Created `src/data_ingestion/scraper.py` with initial web scraping logic.
2.  Informed user to add `OPENAI_API_KEY` to a new `.env` file.
3.  Ran the scraper test, which failed due to a 404 error on the test URL.
4.  Updated the test URL in `scraper.py` to a more stable link.
5.  Re-ran the scraper test, which passed successfully.
6.  Marked Task 3 as complete in `tasks/todo.md`.

---
### 2024-07-25: Vector Store Implementation

**USER PROMPT:** "yes lets do it!"

**AGENT ACTIONS:**
1.  Created `src/vector_store/faiss_store.py` to handle text splitting, embedding, and storage.
2.  Ran the test script, which failed with a `ModuleNotFoundError` for `langchain_community`.
3.  Updated `requirements.txt` to include the `langchain-community` package.
4.  Installed the new dependencies.
5.  Re-ran the test script, which passed successfully, creating the `faiss_vector_store` directory.
6.  Marked Task 4 as complete in `tasks/todo.md`.

---
### 2024-07-25: Core API Implementation & Debugging

**USER PROMPT:** "sure lets do it"

**AGENT ACTIONS:**
1.  Created `src/core_api/main.py` with a FastAPI server and `/ask` endpoint.
2.  Initial test of the API failed, returning "I don't know."
3.  **Debugging Attempt 1:** Removed `allow_dangerous_deserialization` flag. This caused the server to fail on startup.
4.  **Debugging Attempt 2:** Re-added the flag and explicitly set the embeddings model to `text-embedding-3-small` in both `faiss_store.py` and `main.py`. Regenerated the vector store. The test still failed.
5.  **Debugging Attempt 3:** Improved the retriever's search configuration in `main.py`. The test still failed.
6.  **Debugging Attempt 4:** Added a `/debug/retriever` endpoint to inspect the raw context. This revealed the retriever was working, but the context was messy.
7.  **Debugging Attempt 5:** Significantly improved the `scraper.py` to extract cleaner, more meaningful text. Regenerated the vector store with higher-quality data. The test still failed.
8.  **Debugging Attempt 6 (Success):** Relaxed the prompt in `main.py` to be less strict, allowing the LLM to synthesize an answer if the context was imperfect.
9.  Final test passed, returning an intelligent, nuanced answer.
10. Removed the temporary `/debug` endpoint.
11. Marked Task 5 as complete in `tasks/todo.md`.

---
### 2024-07-25: Initial Testing

**USER PROMPT:** "ask it who is he"
**USER PROMPT:** "sweet, what are the next steps?"

**AGENT ACTIONS:**
1.  Started the API server for user testing.
2.  Sent the user's question "who is he" to the API.
3.  The API correctly responded that it did not have the context to answer the question.
4.  Stopped the server and marked Task 6 as complete.

---
### 2024-07-25: Phase 2 - Voice Integration Setup

**USER PROMPT:** "cool lets continue to step 2"

**AGENT ACTIONS:**
1.  Added the plan for Phase 2 to `tasks/todo.md`.
2.  Added `websockets`, `python-decouple`, and `elevenlabs` to `requirements.txt`.
3.  Installed the new dependencies into the virtual environment.
4.  Marked Task 7 as complete in `tasks/todo.md`.

---
### 2024-07-25: Text-to-Speech (TTS) Integration

**USER PROMPT:** "what should we enable for the api key?"
**USER PROMPT:** "what about these settings?"
**USER PROMPT:** "for voices and models it asking for read only or read and write options"
**USER PROMPT:** "ok i saved changes and added the key to the env file"
**USER PROMPT:** "i am confused it says i have 10,000 credits for free and that we havent used any yet"
**USER PROMPT:** "ok i changed it to unlimited, where can i see the interaction we are having?"

**AGENT ACTIONS:**
1.  Guided user on which API permissions to enable for ElevenLabs.
2.  Created the `src/tts/eleven_labs_tts.py` module.
3.  Initial tests failed due to incorrect method names and parameters in the `elevenlabs` library.
4.  Created a temporary script to list valid voice IDs to fix a "voice not found" error.
5.  Final test failed due to the API key's specific credit quota being too low.
6.  Guided user to remove the key-specific credit limit in their ElevenLabs dashboard.
7.  Final test passed, successfully generating and saving `test_audio.mp3`.
8.  Marked Task 8 as complete in `tasks/todo.md`. 