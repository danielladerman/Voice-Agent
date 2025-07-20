-- This file defines the database schema for logging and tracking communications.

-- 1. `calls` Table (Core Metadata)
-- This table stores the main information about each call.
CREATE TABLE calls (
    call_id UUID PRIMARY KEY,
    phone_number VARCHAR(20),
    direction VARCHAR(8), -- inbound/outbound
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    duration INTEGER, -- in seconds
    status VARCHAR(50) -- e.g., completed, missed
);

-- 2. `transcripts` Table (Full Conversation Log)
-- This table stores every part of the conversation, linking back to the call.
CREATE TABLE transcripts (
    transcript_id SERIAL PRIMARY KEY,
    call_id UUID REFERENCES calls(call_id),
    speaker VARCHAR(20), -- 'user' or 'agent' or 'conversation'
    content TEXT,
    timestamp TIMESTAMPTZ NULL,
    sentiment_score FLOAT NULL
);

-- 3. `appointments` Table (Booking Data)
-- This table can be adapted for any specific action or 'event' the agent accomplishes.
-- For now, it is set up for booking appointments as per the original plan.
CREATE TABLE appointments (
    appointment_id SERIAL PRIMARY KEY,
    call_id UUID REFERENCES calls(call_id),
    customer_name VARCHAR(100),
    customer_phone VARCHAR(20),
    customer_address TEXT NULL,
    issue_type VARCHAR(50), -- e.g., "AC not cooling"
    scheduled_time TIMESTAMPTZ,
    calendar_event_id VARCHAR(100) NULL, -- e.g., Google Calendar ID
    crm_contact_id VARCHAR(100) NULL -- e.g., HubSpot ID
);

-- 4. `recordings` Table (Audio Storage Reference)
-- This table links calls to their audio recordings stored in a service like S3.
CREATE TABLE recordings (
    recording_id SERIAL PRIMARY KEY,
    call_id UUID REFERENCES calls(call_id),
    s3_path VARCHAR(255),
    transcript_id INTEGER REFERENCES transcripts(transcript_id)
);

-- 5. `google_auth` Table (Stores OAuth credentials for Google Calendar)
-- This table stores the credentials for each business to access their Google Calendar.
CREATE TABLE google_auth (
    id SERIAL PRIMARY KEY,
    business_name VARCHAR(100) UNIQUE NOT NULL, -- Corresponds to the Pinecone namespace
    token TEXT, -- Stores the access token
    refresh_token TEXT, -- Stores the refresh token to get new access tokens
    token_uri TEXT,
    client_id TEXT,
    client_secret TEXT,
    scopes TEXT, -- Stores scopes as a space-separated string
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
