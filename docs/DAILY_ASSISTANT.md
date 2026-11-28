# Daily assistant workflows

This branch introduces a Hindi/English structured planner and confirmation-gated personal workflows.

Implemented API modules: `POST /api/v1/daily/plan`, `POST /api/v1/daily/actions/{id}/confirm`, reminder CRUD basics, task CRUD basics, shopping lists, expense capture/summary, meal plans, and message drafts. All records are scoped to the authenticated user. Messages are drafts only; this does not send WhatsApp/SMS/email or place calls.

Run `cd backend` then `alembic upgrade head` before testing. Configure the same Vertex AI credentials used by the existing assistant.

Before production: connect typed and transcribed input to this planner in the existing chat orchestration, implement durable reminder delivery (worker + notification channel), add full edit/delete and item-level shopping operations, idempotency, rate limits, provider OAuth, frontend review UI, and run PostgreSQL/Vertex integration tests.