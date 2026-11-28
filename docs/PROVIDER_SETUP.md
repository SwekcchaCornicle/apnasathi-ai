# Provider setup

## WhatsApp Business reminders
The reminder worker sends approved Meta WhatsApp templates only. Create an AWS Secrets Manager JSON secret and pass its ARN as CDK context `whatsappSecretArn`. Required keys: `access_token`, `phone_number_id`, `reminder_template`, `graph_api_version`, `template_language` (`en` or `hi`). The approved template must have one body placeholder for the reminder title. Each user must save an E.164 number through `PUT /api/v1/daily/whatsapp/phone`. The ECS worker runs as a separate service. It needs outbound HTTPS egress to Meta; use `networkEgress=nat` or the configured HTTPS proxy. Recipient opt-in and Meta template approval are mandatory.

## Google Calendar
OAuth and event creation use per-user encrypted refresh tokens. Enable Google Calendar API and create an OAuth **Web application** client. Register redirect URI `https://YOUR_APP_DOMAIN/api/v1/daily/google/calendar/callback`. Create an AWS Secrets Manager JSON secret and pass its ARN as CDK context `googleCalendarSecretArn`, with keys `client_id`, `client_secret`, `redirect_uri`, and `token_encryption_key`. Generate a Fernet key with:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Authenticated flow: `GET /api/v1/daily/google/calendar/connect` returns the authorization URL; redirect the user to Google. `GET /api/v1/daily/google/calendar/status` checks connection. `POST /api/v1/daily/calendar/events` creates an event. The OAuth scope is limited to Calendar Events.

## Android
The frontend is an installable PWA, not a native APK. On Android Chrome use the browser menu → Install app / Add to Home screen. Native call/SMS/contacts integration requires a separate Android app and permission review.
