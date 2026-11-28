"""Send due reminders through approved WhatsApp Business templates."""
import json, logging, os, time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from sqlalchemy import or_, select
from database.daily_models import Reminder
from database.models import UserProfile
from database.session import get_session_factory

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger=logging.getLogger("apnasathi.reminders")

def send_template(phone: str, title: str) -> None:
    payload={"messaging_product":"whatsapp","to":phone,"type":"template","template":{
        "name":os.environ["WHATSAPP_REMINDER_TEMPLATE"],
        "language":{"code":os.getenv("WHATSAPP_TEMPLATE_LANGUAGE","en")},
        "components":[{"type":"body","parameters":[{"type":"text","text":title[:200]}]}]}}
    request=Request(
        f"https://graph.facebook.com/{os.getenv('WHATSAPP_GRAPH_API_VERSION','v22.0')}/{os.environ['WHATSAPP_PHONE_NUMBER_ID']}/messages",
        data=json.dumps(payload).encode(),
        headers={"Authorization":f"Bearer {os.environ['WHATSAPP_ACCESS_TOKEN']}","Content-Type":"application/json"},
        method="POST")
    try:
        with urlopen(request,timeout=15) as response:
            if response.status not in (200,201): raise RuntimeError(f"WhatsApp returned HTTP {response.status}")
    except HTTPError as error:
        logger.warning("WhatsApp rejected reminder (HTTP %s).",error.code)
        raise RuntimeError(f"WhatsApp API HTTP {error.code}") from None
    except (URLError,TimeoutError):
        raise RuntimeError("WhatsApp delivery connection failed.") from None

def process_batch(limit: int=25) -> int:
    factory=get_session_factory(); claimed=[]; now=datetime.now(timezone.utc)
    with factory() as db:
        rows=db.scalars(select(Reminder).where(
            or_(Reminder.status=="scheduled",(Reminder.status=="processing") & (Reminder.claimed_at < now-timedelta(minutes=10))),
            Reminder.scheduled_at<=now,
            or_(Reminder.next_attempt_at.is_(None),Reminder.next_attempt_at<=now),
            Reminder.attempts<5,
        ).order_by(Reminder.scheduled_at).limit(limit).with_for_update(skip_locked=True)).all()
        for row in rows:
            row.status="processing"; row.claimed_at=now
            claimed.append((row.id,row.user_id,row.title))
        db.commit()
    delivered=0
    for reminder_id,user_id,title in claimed:
        with factory() as db:
            row=db.get(Reminder,reminder_id)
            if row is None or row.status!="processing": continue
            profile=db.get(UserProfile,user_id)
            phone=profile.whatsapp_phone if profile and profile.whatsapp_opt_in else None
            try:
                if not phone: raise RuntimeError("WhatsApp reminder opt-in or phone number is missing.")
                send_template(phone,title)
                row.status="delivered"; row.delivered_at=datetime.now(timezone.utc)
                row.last_error=None; row.claimed_at=None; delivered+=1
            except Exception as error:
                row.attempts+=1; row.last_error=str(error)[:240]; row.claimed_at=None
                if row.attempts>=5 or not phone: row.status="failed"
                else:
                    row.status="scheduled"
                    row.next_attempt_at=datetime.now(timezone.utc)+timedelta(minutes=min(2**row.attempts,60))
            db.commit()
    return delivered

def main():
    interval=max(5,int(os.getenv("REMINDER_POLL_INTERVAL_SECONDS","20")))
    while True:
        try: logger.info("Delivered %s reminder(s).",process_batch())
        except Exception: logger.exception("Reminder worker batch failed.")
        time.sleep(interval)

if __name__=="__main__": main()
