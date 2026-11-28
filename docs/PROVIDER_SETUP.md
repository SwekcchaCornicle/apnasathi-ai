# Provider setup for ApnaSathi

## WhatsApp Business reminders

The reminder worker sends **approved WhatsApp message templates only**. It does not send arbitrary text outside Meta's allowed messaging rules.

Required ECS environment/secrets:
- `WHATSAPP_ACCESS_TOKEN` — long-lived system-user token from Meta Business.
- `WHATSAPP_PHONE_NUMBER_ID` — Cloud API phone number ID.
- `WHATSAPP_REMINDER_TEMPLATE` — approved template name with one body placeholder ({{1}}) for the reminder title.
- `WHATSAPP_GRAPH_API_VERSION` — supported Graph API version, e.g. v22.0.
- `WHATSAPP_TEMPLATE_LANGUAGE` — template language code.

Each user must save an E.164 phone number through `PUT /api/v1/daily/whatsapp/phone`. The worker can be run as a scheduled ECS task: `python -m workers.reminder_worker --once`. Configure EventBridge Scheduler to run it every minute; do not run multiple always-on copies unless desired. Failed sends retry with bounded backoff, up to five attempts.

Meta prerequisites: WhatsApp Business Account, registered Cloud API phone number, approved reminder template, system-user access token, and recipient opt-in. Do not commit tokens to Git.

## Google Calendar

Google Calendar requires a Google Cloud OAuth consent screen, Calendar API enabled, OAuth web client, redirect URI, and per-user OAuth consent. Do not use a shared service-account credential for personal calendars. We should add per-user token storage encrypted with AWS KMS/Secrets Manager after the OAuth client details and redirect domain are supplied. No calendar event is written by this branch yet.

## Android

The frontend is now an installable PWA shell. On Android Chrome, use the browser menu → Install app / Add to Home screen. This is not a native APK; native call/SMS/contacts integrations would require a separate Android application and permission review.
