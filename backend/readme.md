# ApnaSathi backend

Run these commands from the repository root in PowerShell. Use the existing `uv`
environment and an already-provisioned private audio bucket.

```powershell
uv sync
$env:AUDIO_S3_BUCKET = "your-existing-audio-bucket"
$env:AWS_REGION = "ap-south-1"
$env:AWS_PROFILE = "your-existing-aws-profile"
uv run python -m uvicorn app:app --app-dir backend --reload --port 8006
```

Use your usual Vertex AI configuration for intent processing. The application
uses boto3's default credential chain. ECS receives the bucket and region from
CDK and uses its task role. On a local machine, the region is optional if the
AWS profile or SDK already supplies it. Avoid storing AWS keys in `.env`.

The Vite frontend proxies `/api/v1` to the backend address in its configuration.
The endpoint `POST /api/v1/upload-audio` accepts the same `audio` multipart field
and the existing optional shopping fields. It validates the declared media type
and container signature, stores the original in private S3, downloads it into a
temporary directory for Whisper, and removes that local copy before intent
processing. The per-file limit is 25 MiB. The existing JSON response is unchanged.
The browser still holds its own recordings in IndexedDB for local playback.

Voice captions and watch-guide yes/no answers are transcribed in temporary
files and are not persisted. Instagram image storage is separate.

## Retention and access

Recordings are stored under `audio/anonymous/YYYY/MM/<UUID>.<extension>`.
The backend has no verified user identity. Object keys include no user-supplied
values and the upload response exposes no keys or URLs. Before making the
write endpoint publicly available, require verified authentication and rate
limiting. If account playback is added later, store object ownership server-side
and authorize reads before issuing short-lived download URLs.

The bucket is private, encrypted with SSE-S3, HTTPS-only, and retained if the
stack is deleted. No recording expiration or versioning is configured. There
is no established retention period, and versioning would retain additional
billable copies that are not useful for these immutable, UUID-named recordings.
Existing local recordings are not migrated automatically.

## Local checks

```powershell
uv run --no-sync python -m unittest discover -s backend/tests -v
uv pip install -r aws_cloud/requirements.txt
uv run --no-sync python -m unittest discover -s aws_cloud/tests -v
docker build --platform linux/arm64 -t apnasathi-backend:local .
docker run --rm --platform linux/arm64 -p 127.0.0.1:8000:8000 -e GOOGLE_CLOUD_PROJECT=local-smoke-test apnasathi-backend:local
```

In a second terminal, run `curl.exe --fail http://127.0.0.1:8000/api/v1/health`.
The smoke test does not access AWS. The container build downloads the public
Whisper base model once and includes the cached model in the image.

## Deployment preflight

The target group checks `/api/v1/health`. CDK keeps the service at zero tasks
by default. After validating and publishing an immutable Linux ARM64 ECR tag,
synthesize the first rollout with `-c backendDesiredCount=1` and
`-c backendImageTag=<published-tag>`. The HTTP ALB requires no ACM context.
Confirm the selected AWS identity, existing stacks, ECR tag, ACM status, and
Fargate quotas before authorizing a deployment.

Check the local image after the build:

```powershell
docker image inspect apnasathi-backend:local --format '{{.Os}}/{{.Architecture}}'
```

Expect `linux/arm64`. A successful health check verifies container startup
but not calls to S3, Vertex, or Meta.

### Outbound access without a NAT Gateway

Keep ECS and RDS private. The gateway endpoint continues to handle S3, and
the existing interface endpoints handle AWS service traffic. For the external
HTTPS APIs, use a forward proxy with an Internet route in the public subnets.
Restrict proxy ingress to the ECS security group and allow only the required
HTTPS CONNECT destinations for Google, Meta, and enabled integrations such
as Watchmode. Use TLS passthrough, configure `HTTPS_PROXY` for clients that
support it, and keep AWS endpoint traffic and ECS task credentials metadata
out of the proxy using `NO_PROXY`. Verify each client from a task before
rollout. A single proxy is a development option. For production, use redundant
proxies across both AZs. No proxy or route change is included here.

For Google, configure Application Default Credentials with Workload Identity
Federation scoped to this ECS task role and a minimally privileged Google
identity. The ECS integration must use task role credentials, not an EC2 IMDS
configuration. Validate the AWS credential supplier and the Google STS and
Vertex paths together. `GOOGLE_CLOUD_PROJECT` names a project but does not
authenticate the task.

The backend currently has no database client or query path. RDS provisioning
and ECS secret injection do not establish application database readiness.
Before exposing the audio upload API publicly, add authentication and rate
limiting. Confirm the pinned RDS engine version is offered in the target region.

See [AWS deployment and Vertex authentication](../docs/aws-deployment.md) for rollout and federation setup.


## PostgreSQL persistence foundation

The backend database layer uses the existing private RDS PostgreSQL instance,
SQLAlchemy 2.x, psycopg 3, Alembic, and the PostgreSQL pgvector extension.
The schema is tenant-aware: private memories and answer embeddings belong to
one user; shared embeddings are explicitly marked shared and cannot carry a
user ID. Do not put user-specific data in shared knowledge.

### Local setup

Install the backend database dependencies (in addition to the project runtime):

```powershell
uv pip install -r backend/requirements.txt
```

Create a local PostgreSQL database with pgvector installed, copy
`backend/.env.example` values into your shell or local environment, then run:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://apnasathi:password@localhost:5432/apnasathi"
$env:DB_SSL = "false"
uv run --no-sync alembic -c backend/alembic.ini upgrade head
```

For ECS, the task already receives `DB_HOST`, `DB_PORT`, `DB_NAME`, and the
RDS JSON secret in `DATABASE_CREDENTIALS`. The SQLAlchemy layer reads those
values and requires TLS by default. Never put the RDS password in source control.
The first migration runs `CREATE EXTENSION IF NOT EXISTS vector`; verify that
the selected RDS PostgreSQL engine supports pgvector and that the migration
identity has permission to enable the extension before applying it.

### Tables created

- `users` and `user_profiles`: provider identity and editable preferences.
- `conversations` and `messages`: durable chat history.
- `search_history`: each user's past queries and retrieval source.
- `memories`: explicit user facts/preferences with confidence and optional expiry.
- `knowledge_embeddings`: private or shared Q&A, multilingual 768-dimension vectors,
  model identifier, quality score, active flag, and reuse count.
- `agent_executions`: audit trail for agent/action outcomes; action executions
  must not be replayed from semantic answer cache.

The first migration creates tables and enables pgvector, but does not yet wire
request handlers, authentication, embedding inference, or answer-cache lookup.
Those are the next backend stages. The current anonymous audio endpoint remains
unchanged; do not associate uploaded audio with a user until verified auth is added.

Run the backend tests after installing dependencies:

```powershell
uv run --no-sync python -m unittest discover -s backend/tests -v
```


## Stage 2: Google authentication

The API now supports Google OpenID Connect sign-in. Configure a Google OAuth
Web application client in Google Cloud Console and set the backend environment
variable `GOOGLE_OAUTH_CLIENT_ID` to that exact client ID. Keep the client secret
out of the backend: the browser obtains a Google ID token using the Google
Identity Services client, then sends that ID token to the backend.

### Endpoints

- `POST /api/v1/auth/google`: body `{"id_token":"<Google ID token>"}`;
  verifies the token signature, expiry, issuer, audience and verified email,
  then creates or updates the user record and profile. It returns the ApnaSathi
  user ID and profile fields, never the Google token.
- `GET /api/v1/users/me`: requires `Authorization: Bearer <Google ID token>`.
- `PATCH /api/v1/users/me/profile`: same bearer requirement; updates display
  name, preferred language, timezone and preferences for the authenticated user.

Install the backend dependencies using `uv pip install -r backend/requirements.txt`
(the Docker build installs this file as part of its image build). Set
`GOOGLE_OAUTH_CLIENT_ID` in your local environment or ECS task environment.
Do not commit real OAuth client IDs if your deployment policy treats them as
configuration secrets, and never commit client secrets or ID tokens.

Example local PowerShell configuration:

```powershell
$env:GOOGLE_OAUTH_CLIENT_ID = "your-google-web-client-id.apps.googleusercontent.com"
uv run --no-sync python -m uvicorn app:app --app-dir backend --reload --port 8006
```

Google ID tokens are short-lived. The frontend should obtain/refresh them using
the Google Identity Services SDK and send the current ID token on each protected
request. The backend validates the token with Google's published signing keys;
it does not accept a user ID from the request body or trust email alone.

**Important:** The existing audio, shopping, Instagram and watch-show endpoints
remain backward compatible and are not yet protected by login. Stage 3 will
connect authenticated user IDs to conversations, messages and search history.
Do not expose account-specific data through those routes until that integration
and endpoint authorization are complete. This stage does not create a separate
application refresh token or session cookie.


## Stage 4: multilingual semantic answer reuse

The semantic retrieval layer uses FastEmbed with the local ONNX model
`intfloat/multilingual-e5-base` (768 dimensions) and the existing PostgreSQL
pgvector column. Query vectors use the E5 `query:` prefix; stored question/answer
passages use `passage:`. The model weights are prefetched during the Docker image
build under `FASTEMBED_CACHE_PATH`, so an ECS task does not need to download the
model at request time. First local use downloads the model into the configured
cache directory.

### API

- `POST /api/v1/knowledge/lookup` requires a verified Google ID token in the
  Authorization Bearer header.
- Request: `{"question":"How do I ...?","intent":"GENERAL_QUESTION","language":"en"}`.
- A hit returns `found: true`, the stored answer, matched question, similarity,
  knowledge ID and `source: "semantic_cache"`.
- A miss or non-reusable intent returns `found: false` and
  `source: "llm_required"`. The caller must then use the existing Gemini path.

### Reuse policy

- Only `GENERAL_QUESTION` is eligible initially. Shopping, posting, ordering,
  calling, app navigation and other action intents are never replayed.
- Private retrieval is always scoped to the authenticated user's ID. Shared
  knowledge is disabled unless `ENABLE_SHARED_KNOWLEDGE=true`; shared records
  must be explicitly curated and must not contain personal data.
- Retrieval filters active entries, matching intent, matching language when
  supplied, and quality score of at least 0.80.
- The initial cosine similarity threshold is configurable with
  `ANSWER_CACHE_SIMILARITY_THRESHOLD` (default 0.88). This is a conservative
  starting point, not a validated universal threshold; evaluate it against a
  representative multilingual test set before lowering it.
- `store_approved_answer()` is a backend service function, not a public API.
  Only trusted application code after a quality/review decision should call it.
  Do not cache transient facts, unverified LLM outputs, personal user data as
  shared content, or any action result that could trigger a side effect.

### Runtime notes

FastEmbed and E5 are free/open-source software and execute locally; compute,
container image storage, and ECS memory/CPU are still infrastructure costs. The
current Fargate task has limited memory, so benchmark embedding inference before
production traffic. The API currently exposes semantic lookup as a separate
protected endpoint; it is not yet inserted into the existing audio/chat response
pipeline. Stage 3 persistence and the final LLM orchestration stage must connect
user messages, approved answer storage, cache lookup, and Gemini fallback.

Configure the values in `backend/.env.example`. No production migration,
model download, test run, or deployment was performed as part of this code change.


## Stage 3: authenticated user history and memory

The authenticated persistence API connects data to the verified Google user ID.
The API never accepts a caller-supplied user ID for ownership. Every query for
conversations, messages, search history and memories filters by the authenticated
user. Existing tables are provisioned by the Stage 1 Alembic migration.

### Supported languages

ApnaSathi currently supports exactly two language choices:

- `en` — English
- `hi` — Hindi

The language selector is `POST /api/v1/users/me/language` with
`{"language":"hi"}` or `{"language":"en"}`. For any other language the API
returns `supported: false` and the message:

> We're about to launch support for this language. For now, please choose Hindi or English.

Unsupported language choices are not saved. Conversation creation, message
creation, search history, and profile updates also reject unsupported languages.
If a language is omitted, the user's saved preference is used (English if no
preference has been selected). Regional forms such as `hi-IN` normalize to
`hi` and `en-IN` to `en`.

### Endpoints (all require a Google ID token bearer header)

- `POST /api/v1/users/me/language` — select English or Hindi; returns launch notice for other languages.
- `POST /api/v1/conversations` — create a conversation, defaulting to profile language.
- `GET /api/v1/conversations` — list only the signed-in user's conversations.
- `GET /api/v1/conversations/{id}/messages` — list messages after ownership verification.
- `POST /api/v1/conversations/{id}/messages` — append a user message.
- `POST /api/v1/search-history` and `GET /api/v1/search-history` — record and list searches.
- `POST /api/v1/memories` and `GET /api/v1/memories` — create and list user-approved facts/preferences.
- `DELETE /api/v1/memories/{id}` — deactivate a memory owned by the signed-in user.
- Trusted backend orchestration can call `persist_assistant_message()` to save assistant replies; there is no public endpoint that lets clients impersonate assistant messages.

### Example: create a conversation

```http
POST /api/v1/conversations
Authorization: Bearer <Google ID token>
Content-Type: application/json

{"title":"My first chat","channel":"chat","language":"hi"}
```

### Example: unsupported language

```http
POST /api/v1/users/me/language
Authorization: Bearer <Google ID token>
Content-Type: application/json

{"language":"bn"}
```

Response:

```json
{
  "supported": false,
  "language": null,
  "message": "We're about to launch support for this language. For now, please choose Hindi or English.",
  "supported_languages": ["en", "hi"]
}
```

Messages and memories are private to the account. Memory creation is explicit;
this stage does not automatically infer/store personal facts from raw messages.
The memory delete endpoint deactivates the record rather than hard-deleting it,
so it is excluded from future reads. Add a retention/purge policy before production.

This stage exposes persistence APIs and trusted helper functions. Existing
voice/agent endpoints are not yet fully connected to conversation persistence
or semantic lookup. That orchestration wiring remains a final integration task.
