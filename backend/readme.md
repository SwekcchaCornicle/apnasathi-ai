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


## Development authentication: Amazon Cognito

This development setup uses the Cognito User Pool in `ap-south-1`.

Frontend `.env.local`:

```dotenv
VITE_COGNITO_REGION=ap-south-1
VITE_COGNITO_USER_POOL_ID=ap-south-1_qxfax5y4B
VITE_COGNITO_CLIENT_ID=3o9dcghf8vagog0c24jpih5l8r
VITE_API_BASE_URL=/api/v1
```

Backend `.env`:

```dotenv
COGNITO_REGION=ap-south-1
COGNITO_USER_POOL_ID=ap-south-1_qxfax5y4B
COGNITO_CLIENT_ID=3o9dcghf8vagog0c24jpih5l8r
```

The frontend uses the AWS Cognito Identity Provider SDK directly for email/password
sign-up, email confirmation, sign-in, forgot-password and password reset. It sends
the resulting Cognito ID token to `POST /api/v1/auth/cognito`. FastAPI verifies the
JWT signature against the User Pool JWKS, issuer, app-client audience, token_use,
expiry and verified email before creating/updating the local account.

The app client must be a **public client with no client secret**. Enable the
`USER_PASSWORD_AUTH` authentication flow (AWS console app client authentication
flows / ALLOW_USER_PASSWORD_AUTH) because the development frontend calls
`InitiateAuth` with `USER_PASSWORD_AUTH`. Keep self-registration and email
verification enabled in the User Pool. SMS/MFA is not required for this dev setup.

Do not put AWS access keys or a client secret in the frontend. The Cognito app
client ID and User Pool ID are identifiers, not secrets. Configure real values in
local `.env.local` / `.env` files and never commit credentials.

Install updated dependencies after pulling:

```bash
# frontend
cd frontend
npm install
npm run dev

# backend (from repository root; use your existing uv workflow)
uv sync
```

Legacy Google verifier files may remain for reference, but the active auth router
and protected-route dependency now use Cognito. Existing Google-only accounts are
not automatically linked to Cognito accounts; this is a development migration
and account linking should be designed before production.
