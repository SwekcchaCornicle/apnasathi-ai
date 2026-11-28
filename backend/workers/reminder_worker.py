"""Poll due reminders and send approved WhatsApp Business templates.

Run as a dedicated scheduled ECS task: python -m workers.reminder_worker --once
The worker never sends free-form outbound messages; Meta-approved templates are required.
"""
import argparse
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy import or_, select
from database.daily_models import Reminder
from database.models import UserProfile
from database.session import get_session_factory

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("apnasathi.reminders")

def send_template(phone: str, title: str) -> None:
    token = os.environ["WHATSAPP_ACCESS_TOKEN"]
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    template = os.environ["WHATSAPP_REMINDER_TEMPLATE"]
    version = os.getenv("WHATSAPP_GRAPH_API_VERSION", "v22.0")
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "en")},
            "components": [{"type": "body", "parameters": [{"type": "text", "text": title[:200]}]}],
        },
    }
    request = Request(
        f"https://graph.facebook.com/{version}/{phone_id}/messages",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            if response.status not in (200, 201):
                raise RuntimeError(f"WhatsApp returned HTTP {response.status}")
    except HTTPError as error:
        logger.warning("WhatsApp API rejected reminder (HTTP %s).", error.code)
        raise RuntimeError(f"WhatsApp API HTTP {error.code}") from None
    except (URLError, TimeoutError):
        raise RuntimeError("WhatsApp delivery connection failed.") from None

def process_batch(limit: int = 25) -> int:
    factory = get_session_factory()
    claimed = []
    now = datetime.now(timezone.utc)
    with factory() as db:
        rows = db.scalars(
            select(Reminder).where(
                Reminder.status == "scheduled",
                Reminder.scheduled_at <= now,
                or_(Reminder.next_attempt_at.is_(None), Reminder.next_attempt_at <= now),
                Reminder.attempts < 5,
            ).order_by(Reminder.scheduled_at).limit(limit).with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            row.status = "processing"
            claimed.append((row.id, row.user_id, row.title))
        db.commit()
    delivered = 0
    for reminder_id, user_id, title in claimed:
        with factory() as db:
            row = db.get(Reminder, reminder_id)
            profile = db.get(UserProfile, user_id)
            phone = profile.whatsapp_phone if profile else None
            try:
                if not phone:
                    raise RuntimeError("WhatsApp phone number is not configured for this account.")
                send_template(phone, title)
                row.status = "delivered"
                row.delivered_at = datetime.now(timezone.utc)
                row.last_error = None
                delivered += 1
            except Exception as error:
                row.attempts += 1
                row.last_error = str(error)[:240]
                if row.attempts >= 5 or not phone:
                    row.status = "failed"
                else:
                    row.status = "scheduled"
                    row.next_attempt_at = datetime.now(timezone.utc) + timedelta(minutes=min(2 ** row.attempts, 60))
            db.commit()
    return delivered

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=20)
    args = parser.parse_args()
    while True:
        count = process_batch()
        logger.info("Delivered %s reminder(s).", count)
        if args.once:
            return
        time.sleep(max(5, args.interval))

if __name__ == "__main__":
    main()
