import asyncpg
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

# Load environment variables from .env file
load_dotenv()

# --- Database Connection ---

# It's recommended to use environment variables for database credentials
DB_NAME = os.getenv("DB_NAME", "your_db_name")
DB_USER = os.getenv("DB_USER", "your_db_user")
DB_PASS = os.getenv("DB_PASS", "your_db_password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = f"postgres://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- Helper Functions ---
def to_datetime(ms: int) -> datetime:
    """Converts a UNIX timestamp in milliseconds to a timezone-aware datetime object."""
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)

async def get_db_connection():
    """Establishes a connection to the database."""
    try:
        # --- TEMPORARY DEBUGGING ---
        print(f"--- DB: Attempting to connect to host: '{DB_HOST}' on port: '{DB_PORT}'")
        # --------------------------
        conn = await asyncpg.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"!!! DATABASE CONNECTION ERROR: {e}")
        return None

# --- Database Interaction Functions ---

async def create_call_record(event: dict):
    """Creates a new record for a call in the 'calls' table."""
    conn = await get_db_connection()
    if not conn:
        return
    
    try:
        call_data = event.get('call', {})
        await conn.execute("""
            INSERT INTO calls (call_id, phone_number, direction, start_time, status)
            VALUES ($1, $2, $3, $4, 'started')
        """,
            call_data.get('id'),
            call_data.get('customer', {}).get('number'),
            call_data.get('direction'),
            to_datetime(event.get('timestamp'))
        )
        print(f"--- DB: Created call record for {call_data.get('id')}")
    except Exception as e:
        print(f"!!! DB ERROR (create_call_record): {e}")
    finally:
        await conn.close()


async def save_transcript(call_id: str, full_transcript: str):
    """Saves the full conversation transcript to the 'transcripts' table."""
    conn = await get_db_connection()
    if not conn:
        return

    try:
        # We store the entire conversation in a single record.
        # The 'speaker' is set to 'conversation' to reflect this.
        await conn.execute("""
            INSERT INTO transcripts (call_id, speaker, content)
            VALUES ($1, 'conversation', $2)
        """,
            call_id,
            full_transcript
        )
        print(f"--- DB: Saved full transcript for {call_id}")
    except Exception as e:
        print(f"!!! DB ERROR (save_transcript): {e}")
    finally:
        await conn.close()


async def create_appointment(call_id: str, parameters: dict):
    """Creates an appointment record from a function call."""
    conn = await get_db_connection()
    if not conn:
        return
        
    try:
        await conn.execute("""
            INSERT INTO appointments (call_id, customer_name, customer_phone, issue_type, scheduled_time)
            VALUES ($1, $2, $3, $4, $5)
        """,
            call_id,
            parameters.get('customer_name'),
            parameters.get('customer_phone'),
            parameters.get('issue_type'),
            parameters.get('scheduled_time')
        )
        print(f"--- DB: Created appointment for {call_id}")
    except Exception as e:
        print(f"!!! DB ERROR (create_appointment): {e}")
    finally:
        await conn.close()


async def finalize_call_record(event: dict):
    """Updates a call record with the end time and final status."""
    conn = await get_db_connection()
    if not conn:
        return
    
    try:
        call_data = event.get('call', {})
        await conn.execute("""
            UPDATE calls
            SET end_time = $1, status = $2, duration = $3
            WHERE call_id = $4
        """,
            to_datetime(event.get('timestamp')),
            event.get('endedReason'),
            event.get('durationSeconds'),
            call_data.get('id')
        )
        print(f"--- DB: Finalized call record for {call_data.get('id')}")
    except Exception as e:
        print(f"!!! DB ERROR (finalize_call_record): {e}")
    finally:
        await conn.close()

async def store_recording(call_id: str, audio_url: str):
    """Stores a reference to the call recording."""
    # This would typically involve downloading the audio and uploading to S3,
    # then saving the S3 path to the 'recordings' table.
    # For now, we will just log it.
    print(f"Received request to store recording for call {call_id} from URL: {audio_url}")
    pass
