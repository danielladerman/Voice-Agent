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

# --- Global Connection Pool ---
db_pool = None

async def init_db_pool():
    """Initializes the database connection pool."""
    global db_pool
    if db_pool is None:
        try:
            print(f"--- DB: Initializing connection pool for host: '{DB_HOST}'")
            db_pool = await asyncpg.create_pool(
                dsn=DATABASE_URL,
                min_size=1,
                max_size=10,
                statement_cache_size=0  # Required for Supabase Transaction Pooler
            )
            print("--- DB: Connection pool initialized successfully.")
        except Exception as e:
            print(f"!!! DATABASE POOL CREATION ERROR: {e}")
            db_pool = None

async def close_db_pool():
    """Closes the database connection pool."""
    global db_pool
    if db_pool:
        await db_pool.close()
        print("--- DB: Connection pool closed.")

# --- Helper Functions ---
def to_datetime(ms: int) -> datetime:
    """Converts a UNIX timestamp in milliseconds to a timezone-aware datetime object."""
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)

async def get_db_connection():
    """Acquires a connection from the global pool."""
    global db_pool
    if db_pool is None:
        # This is a fallback, but in practice the pool should be initialized on app startup
        await init_db_pool()
    
    if db_pool:
        return await db_pool.acquire()
    return None

# --- Database Interaction Functions ---

async def create_call_record(event: dict):
    """Creates a new record for a call in the 'calls' table."""
    conn = await get_db_connection()
    if not conn:
        print("!!! DB ERROR: Could not get a connection from the pool.")
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
        if conn:
            await db_pool.release(conn)


async def save_transcript_turn(call_id: str, speaker: str, content: str):
    """Saves a single turn of the conversation to the 'transcripts' table."""
    conn = await get_db_connection()
    if not conn:
        print("!!! DB ERROR: Could not get a connection from the pool.")
        return

    try:
        await conn.execute("""
            INSERT INTO transcripts (call_id, speaker, content, timestamp)
            VALUES ($1, $2, $3, $4)
        """,
            call_id,
            speaker,
            content,
            datetime.now(timezone.utc)
        )
        print(f"--- DB: Saved transcript turn for {call_id}")
    except Exception as e:
        print(f"!!! DB ERROR (save_transcript_turn): {e}")
    finally:
        if conn:
            await db_pool.release(conn)


async def create_appointment(call_id: str, parameters: dict):
    """Creates an appointment record from a function call."""
    conn = await get_db_connection()
    if not conn:
        print("!!! DB ERROR: Could not get a connection from the pool.")
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
        if conn:
            await db_pool.release(conn)


async def finalize_call_record(event: dict):
    """Updates a call record with the end time and final status."""
    conn = await get_db_connection()
    if not conn:
        print("!!! DB ERROR: Could not get a connection from the pool.")
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
        if conn:
            await db_pool.release(conn)

async def store_recording(call_id: str, audio_url: str):
    """Stores a reference to the call recording."""
    # This would typically involve downloading the audio and uploading to S3,
    # then saving the S3 path to the 'recordings' table.
    # For now, we will just log it.
    print(f"Received request to store recording for call {call_id} from URL: {audio_url}")
    pass

# --- Google Calendar Auth Functions ---

async def save_google_auth(business_name: str, credentials):
    """Saves or updates the Google OAuth 2.0 credentials for a business."""
    conn = await get_db_connection()
    if not conn:
        print("!!! DB ERROR: Could not get a connection from the pool.")
        return

    try:
        # Check if a record for this business already exists
        existing = await conn.fetchval("SELECT id FROM google_auth WHERE business_name = $1", business_name)
        
        if existing:
            # Update existing credentials
            await conn.execute("""
                UPDATE google_auth
                SET token = $1, refresh_token = $2, token_uri = $3, client_id = $4, client_secret = $5, scopes = $6, updated_at = $7
                WHERE business_name = $8
            """,
                credentials.token,
                credentials.refresh_token,
                credentials.token_uri,
                credentials.client_id,
                credentials.client_secret,
                ' '.join(credentials.scopes),
                datetime.now(timezone.utc),
                business_name
            )
            print(f"--- DB: Updated Google Auth credentials for {business_name}")
        else:
            # Insert new credentials
            await conn.execute("""
                INSERT INTO google_auth (business_name, token, refresh_token, token_uri, client_id, client_secret, scopes, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
                business_name,
                credentials.token,
                credentials.refresh_token,
                credentials.token_uri,
                credentials.client_id,
                credentials.client_secret,
                ' '.join(credentials.scopes),
                datetime.now(timezone.utc),
                datetime.now(timezone.utc)
            )
            print(f"--- DB: Saved new Google Auth credentials for {business_name}")

    except Exception as e:
        print(f"!!! DB ERROR (save_google_auth): {e}")
    finally:
        if conn:
            await db_pool.release(conn)

async def get_google_auth(business_name: str):
    """Retrieves the Google OAuth 2.0 credentials for a business."""
    conn = await get_db_connection()
    if not conn:
        print("!!! DB ERROR: Could not get a connection from the pool.")
        return None
    
    try:
        row = await conn.fetchrow("SELECT * FROM google_auth WHERE business_name = $1", business_name)
        if row:
            print(f"--- DB: Retrieved Google Auth credentials for {business_name}")
            return dict(row)
        else:
            print(f"--- DB: No Google Auth credentials found for {business_name}")
            return None
    except Exception as e:
        print(f"!!! DB ERROR (get_google_auth): {e}")
        return None
    finally:
        if conn:
            await db_pool.release(conn)
