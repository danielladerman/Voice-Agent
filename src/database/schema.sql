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
    status VARCHAR(10) -- e.g., completed, missed
);

-- 2. `transcripts` Table (Full Conversation Log)
-- This table stores every part of the conversation, linking back to the call.
CREATE TABLE transcripts (
    transcript_id SERIAL PRIMARY KEY,
    call_id UUID REFERENCES calls(call_id),
    speaker VARCHAR(10), -- 'user' or 'agent'
    content TEXT,
    timestamp TIMESTAMPTZ,
    sentiment_score FLOAT
);

-- 3. `appointments` Table (Booking Data)
-- This table can be adapted for any specific action or 'event' the agent accomplishes.
-- For now, it is set up for booking appointments as per the original plan.
CREATE TABLE appointments (
    appointment_id SERIAL PRIMARY KEY,
    call_id UUID REFERENCES calls(call_id),
    customer_name VARCHAR(100),
    customer_phone VARCHAR(20),
    customer_address TEXT,
    issue_type VARCHAR(50), -- e.g., "AC not cooling"
    scheduled_time TIMESTAMPTZ,
    calendar_event_id VARCHAR(100), -- e.g., Google Calendar ID
    crm_contact_id VARCHAR(100) -- e.g., HubSpot ID
);

-- 4. `recordings` Table (Audio Storage Reference)
-- This table links calls to their audio recordings stored in a service like S3.
CREATE TABLE recordings (
    recording_id SERIAL PRIMARY KEY,
    call_id UUID REFERENCES calls(call_id),
    s3_path VARCHAR(255),
    transcript_id INTEGER REFERENCES transcripts(transcript_id)
);
