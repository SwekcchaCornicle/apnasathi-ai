"""Google Calendar OAuth and event creation using per-user encrypted refresh tokens."""
import json, os
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session
from database.daily_models import GoogleCalendarCredential

class GoogleCalendarError(RuntimeError):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message); self.status_code = status_code

def _config():
    keys=("GOOGLE_CALENDAR_CLIENT_ID","GOOGLE_CALENDAR_CLIENT_SECRET","GOOGLE_CALENDAR_REDIRECT_URI","GOOGLE_TOKEN_ENCRYPTION_KEY")
    cfg={key:os.getenv(key) for key in keys}
    if not all(cfg.values()):
        raise GoogleCalendarError("Google Calendar OAuth is not configured. Add its client credentials and token encryption key to AWS Secrets Manager.")
    return cfg

def google_oauth_url(state: str) -> str:
    c=_config()
    return "https://accounts.google.com/o/oauth2/v2/auth?"+urlencode({
        "client_id":c["GOOGLE_CALENDAR_CLIENT_ID"],"redirect_uri":c["GOOGLE_CALENDAR_REDIRECT_URI"],
        "response_type":"code","scope":"https://www.googleapis.com/auth/calendar.events",
        "access_type":"offline","prompt":"consent","include_granted_scopes":"true","state":state})

def _post_form(url, values):
    req=Request(url,data=urlencode(values).encode(),headers={"Content-Type":"application/x-www-form-urlencoded"},method="POST")
    try:
        with urlopen(req,timeout=20) as response: return json.loads(response.read().decode())
    except HTTPError:
        raise GoogleCalendarError("Google rejected the Calendar authorization request.",502) from None
    except (URLError,TimeoutError,json.JSONDecodeError):
        raise GoogleCalendarError("Google Calendar is temporarily unavailable.",503) from None

def exchange_google_code(code):
    c=_config()
    return _post_form("https://oauth2.googleapis.com/token",{"code":code,"client_id":c["GOOGLE_CALENDAR_CLIENT_ID"],"client_secret":c["GOOGLE_CALENDAR_CLIENT_SECRET"],"redirect_uri":c["GOOGLE_CALENDAR_REDIRECT_URI"],"grant_type":"authorization_code"})

def encrypt_refresh_token(token):
    try: return Fernet(_config()["GOOGLE_TOKEN_ENCRYPTION_KEY"].encode()).encrypt(token.encode()).decode()
    except (ValueError,InvalidToken): raise GoogleCalendarError("Google token encryption key is invalid. Use a Fernet key.") from None

def _access_token(db:Session,user_id):
    c=_config(); credential=db.get(GoogleCalendarCredential,user_id)
    if credential is None: raise GoogleCalendarError("Connect Google Calendar before creating events.",409)
    try: refresh=Fernet(c["GOOGLE_TOKEN_ENCRYPTION_KEY"].encode()).decrypt(credential.refresh_token_encrypted.encode()).decode()
    except (ValueError,InvalidToken): raise GoogleCalendarError("Stored Google Calendar credentials could not be decrypted.",503) from None
    token=_post_form("https://oauth2.googleapis.com/token",{"client_id":c["GOOGLE_CALENDAR_CLIENT_ID"],"client_secret":c["GOOGLE_CALENDAR_CLIENT_SECRET"],"refresh_token":refresh,"grant_type":"refresh_token"})
    if not token.get("access_token"): raise GoogleCalendarError("Google did not issue an access token.",502)
    return token["access_token"]

def create_calendar_event(db:Session,user_id,event:dict):
    token=_access_token(db,user_id); start=event["start_at"]; end=event["end_at"]
    payload={"summary":event["title"],"description":event.get("description") or "",
      "start":{"dateTime":start.isoformat() if hasattr(start,"isoformat") else str(start),"timeZone":event["timezone"]},
      "end":{"dateTime":end.isoformat() if hasattr(end,"isoformat") else str(end),"timeZone":event["timezone"]}}
    req=Request("https://www.googleapis.com/calendar/v3/calendars/primary/events",data=json.dumps(payload).encode(),
      headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},method="POST")
    try:
        with urlopen(req,timeout=20) as response: return json.loads(response.read().decode())
    except HTTPError: raise GoogleCalendarError("Google Calendar could not create this event.",502) from None
    except (URLError,TimeoutError,json.JSONDecodeError): raise GoogleCalendarError("Google Calendar is temporarily unavailable.",503) from None
