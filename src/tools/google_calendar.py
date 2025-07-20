from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from src.database import database as db_utils
import datetime

async def get_calendar_service(business_name: str):
    """
    Builds and returns a Google Calendar service object authenticated
    for the given business.
    """
    creds_dict = await db_utils.get_google_auth(business_name)
    if not creds_dict:
        return None

    # Recreate the Credentials object from the stored dictionary
    credentials = Credentials(
        token=creds_dict['token'],
        refresh_token=creds_dict['refresh_token'],
        token_uri=creds_dict['token_uri'],
        client_id=creds_dict['client_id'],
        client_secret=creds_dict['client_secret'],
        scopes=creds_dict['scopes'].split(' ')
    )
    
    # If the credentials are expired, refresh them
    if credentials.expired and credentials.refresh_token:
        import google.auth.transport.requests
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        # Save the refreshed credentials back to the database
        await db_utils.save_google_auth(business_name, credentials)

    try:
        service = build('calendar', 'v3', credentials=credentials)
        return service
    except Exception as e:
        print(f"!!! CALENDAR SERVICE ERROR: {e}")
        return None

async def get_available_slots(business_name: str, start_time: str, end_time: str):
    """
    Finds available time slots in a Google Calendar.
    (This is a simplified example; a real implementation would be more complex)
    """
    service = await get_calendar_service(business_name)
    if not service:
        return {"error": "Could not connect to Google Calendar."}
    
    # Get the list of events
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=start_time,
        timeMax=end_time,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    
    # This is a placeholder for a more sophisticated availability search.
    # For now, it just returns the busy times.
    busy_times = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        busy_times.append({"start": start, "end": end})
        
    return {"busy_times": busy_times}


async def create_calendar_event(business_name: str, summary: str, start_time: str, end_time: str, description: str = ''):
    """
    Creates a new event in the primary Google Calendar for the business.
    """
    service = await get_calendar_service(business_name)
    if not service:
        return {"error": "Could not connect to Google Calendar."}

    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': 'America/Los_Angeles', # You may want to make this configurable
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'America/Los_Angeles', # You may want to make this configurable
        },
    }

    try:
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        return {"status": "success", "event_id": created_event.get('id')}
    except Exception as e:
        print(f"!!! CALENDAR EVENT CREATION ERROR: {e}")
        return {"error": str(e)} 