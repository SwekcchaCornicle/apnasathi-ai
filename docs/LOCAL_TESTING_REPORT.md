# ApnaSathi AI local testing report

**Release decision — Hold deployment.**  
**Date** 27 November 2026  
**Checkout** `C:\Users\singh\OneDrive\Desktop\apnasathi-ai`  
**Branch** `qa/pre-deployment-validation` · based on `1518bf3` from `origin/main`

## Executive summary

Baseline tests missed an application-level regression. The signed-in React workspace called conversation and assistant endpoints that were absent from the running FastAPI application. The QA branch restores those endpoints, retains Cognito as the identity provider, and validates chat persistence, private semantic retrieval, and saved Blinkit history with a disposable database. The production bundle renders in Chrome, and the English and Hindi browser tests exercise mocked registration and SRP, chat, recovery, sidebar history, and voice upload.

Live Cognito verification, native PostgreSQL and Docker validation, live provider checks, mixed-language speech fidelity, and deployment-wide rate limiting remain release blockers. The chat UI includes the shopping guide, Instagram review controls, and video troubleshooting. CDK synthesized four stacks locally. No AWS resources were modified, no purchase or post was made, and no branch was merged or pushed.

## Repository and runtime audit

- GitHub reported PRs #1–#9 as closed and merged, with no open PRs. Main contains the frontend workspace and Cognito changes, while the assistant, history and retrieval modules were present on the assistant orchestration branch and absent from the current main tree. The QA branch restores the selected modules and tests without a branch merge. [Pull requests](https://github.com/SwekcchaCornicle/apnasathi-ai/pulls?q=is%3Apr)
- Audited the frontend environment template and Vite proxy, Python and npm lockfiles, FastAPI registrations, account and history models, initial Alembic migration, Docker startup, and CDK network, database, ECS, secret-injection, health-check and S3 resources.
- Registered API families include health; Cognito exchange and profile; language; conversations and messages; assistant text and audio; semantic lookup; search history and memories; legacy audio, shopping, caption and watch troubleshooting; and Instagram upload, callback, draft status, image and publish. Instagram attachments, status, publishing, and cancellation require a verified account and are scoped to the draft owner. The public Instagram callback and image routes depend on single-use draft state or short-lived image keys.
- The user pool client describe call returned `UnrecognizedClientException`. Actual allowed flows and secret presence are unverified. SRP uses the public client named in the request and the user's stated SRP setting. The browser suite verified an initiate/challenge exchange against fixtures. [AWS Cognito flow documentation](https://docs.aws.amazon.com/cognito/latest/developerguide/authentication-implement.html)

## Test results

Each row counts the listed release checks once. The automated test count below is separate because individual tests span several areas. A BLOCKED check lacked a required dependency or was outside the evidence obtained in this run. A FAIL indicates observed behavior or a missing required feature.

| Area | Total | Passed | Failed | Blocked | Evidence or remaining gate |
|---|---:|---:|---:|---:|---|
| Cognito | 4 | 2 | 0 | 2 | Mocked signup, confirmation and SRP plus signed JWT validation passed. Actual client flows and live account, email and reset are blocked. |
| Frontend | 4 | 3 | 0 | 1 | Production build, desktop/mobile Chrome, and English/Hindi selection passed. Tablet and browser compatibility matrix incomplete. |
| Chat | 4 | 3 | 0 | 1 | Send, refresh, and request failure/retry passed. Full keyboard and long-thread matrix incomplete. |
| Sidebar and intent history | 3 | 2 | 0 | 1 | Drawer, search, and reopen covered. All intent categories and outside-click matrix incomplete. |
| Microphone and voice | 4 | 2 | 1 | 1 | Simulated permission denial and upload passed. Synthetic English and Hindi speech produced intelligible text. Mixed speech was rendered in English. Real microphone and full browser matrix remain open. |
| Backend APIs | 4 | 3 | 0 | 1 | Health, auth and persistence, and protected assistant calls passed. Full per-route negative matrix incomplete. |
| PostgreSQL | 4 | 2 | 0 | 2 | Initial migration and second upgrade passed under disposable PGlite with pgvector. Native PostgreSQL and existing production-equivalent schema validation remain open. |
| Semantic cache | 4 | 3 | 0 | 1 | First miss, persisted vector, exact and paraphrased hits without additional LLM calls, and fallback for similar-but-different and unrelated queries passed. Full freshness and shared-cache matrix incomplete. |
| Embeddings | 4 | 3 | 0 | 1 | Model loads, produces 768 dimensions, and runs across English, Hindi, mixed and long queries. Concurrent deployment profiling remains open. |
| Shopping | 3 | 3 | 0 | 0 | Store detection and guided correction/cancellation passed. Saved basket recovery worked and was isolated by account. |
| Instagram | 2 | 1 | 0 | 1 | Browser and API fixtures covered draft attachment, review, ownership and explicit confirmation. Live Meta authorization and provider behavior remain unverified. |
| Video assistant | 2 | 1 | 0 | 1 | Browser controls and backend text troubleshooting passed. Live provider/platform compatibility and the complete voice troubleshooting matrix remain unverified. |
| Security | 5 | 3 | 1 | 1 | JWT claims, tenant scoping, CORS and error redaction covered. No effective deployment-wide rate limit was identified. Full route/security matrix remains open. |
| Docker | 2 | 1 | 0 | 1 | Compose config validates. Linux Docker engine pipe unavailable for image build and native DB startup. |
| AWS configuration | 3 | 2 | 0 | 1 | CDK synth and infrastructure unit tests passed. ECS sizing, live permissions, and RDS engine availability remain unverified. |
| End-to-end | 7 | 4 | 0 | 3 | Mocked browser onboarding/retry plus database-backed Blinkit and cache workflows passed. Real microphone E2E, complete intent history and live two-user Cognito E2E remain open. |
| **Total** | **59** | **38** | **2** | **19** | Release checks tracked in this report. |

The final combined suite covered backend, infrastructure, disposable-database integration, and Chrome tests together. The final totals are recorded separately from the release checks above.

## Bug fix register

| Defect | Root cause | Fix and files | Regression and retest |
|---|---|---|---|
| Chat and sign-in returned missing-route responses | Main omitted assistant and persistence modules and did not register the Cognito router | Restored selected `backend/api`, `backend/services` and `backend/embeddings` modules, connected routers in `backend/app.py`, and wired selected language and saved context into the LLM request | Protected-route regression tests and real database-backed integration passed |
| SPA sign-in used an incompatible flow and localhost pointed at a LAN host | Password auth was hardcoded, the env example pointed at the older client, and Vite proxied to a machine-specific address | Uses SRP in `frontend/src/cognito.js`, configures the public client, fixes localhost proxy and CORS, and removes the tracked local env file from the index while keeping an ignored local copy | Chrome exercised both SRP challenge steps, and CORS preflight passed |
| Successful bundling produced a blank browser screen | Cognito JS dependency referenced the Node-style global name | Vite maps the dependency global to `globalThis` | Browser captured the original runtime error and passed after the fix |
| Semantic lookup silently fell back to the LLM | The requested E5 base identifier was absent from FastEmbed's built-in registry, and optional lookup failures rolled back the whole transaction | Registers the quantized 768-dimensional E5 base export, validates vector values, isolates cache operations with savepoints, scopes by language, model and tenant, checks age and suppresses action or current-information reuse | Real embeddings and pgvector persisted and served a repeat without a second LLM call |
| Previous Blinkit request could be guessed | History was only unstructured LLM context, and the original user message did not retain the intent | `backend/api/assistant.py` stores classified order items and retrieves the latest eligible saved Blinkit request from the authenticated user's own history | Two database-backed accounts verified known items, no LLM call for saved history, and no cross-account disclosure |
| Audio, history and error handling had unsafe edge cases | Route auth was absent for legacy ingestion helpers, attachment processing lacked an assistant HTTP body cap, message views could apply stale state, and request validation could echo inputs | Added route auth and input redaction, exposed the saved transcript, guarded browser mic cleanup and conversation selection, and added deterministic recent-message ordering in `backend/app.py`, `backend/api`, and `frontend/src/ChatWorkspace.jsx` | API, signed-JWT, upload, browser mic and database integration checks cover the exercised cases |
| Shopping, Instagram and video controls were absent from authenticated chat | Existing agent workflows were only reachable from the obsolete recording UI or lacked structured reply metadata | Persists shopping sessions and playback metadata; adds a Cognito-owned Instagram draft workflow with explicit confirmation and cancellation; adds accessible playback and guide controls | Browser tests exercise the flows with mocked services; API and database tests cover real route logic, shopping corrections and Instagram draft ownership |
| ECS could omit the Cognito client environment | Task synthesis had no interface for the public pool or app client identifiers | Added paired CDK context inputs and mapped validated public values into the task environment | CloudFormation template test verifies Cognito region, pool and client settings. Private-subnet JWKS access is still a live release check. |
| Locked Docker dependency install and local Compose setup were invalid | `uv.lock` omitted the pyproject JWT dependency and the Compose file was empty | Regenerated `uv.lock`, added disposable pgvector service, and bundled the E5 cache in the Dockerfile | `uv lock --check` and `docker compose config --quiet` passed. Image build remains blocked. |

## Performance

| Measure | Observed |
|---|---|
| Health endpoint | 10 localhost requests, 62.5 ms mean and 5.1 ms minimum, including a 531.4 ms first-run outlier |
| Embedding cold load with existing model files | 5.25 s for first English request |
| Warm embedding | 88.5 ms Hindi, 93.9 ms mixed, and 2.82 s for a long input, single samples |
| Embedding process memory and CPU | 612–652 MiB RSS. 6.83 CPU seconds across the four-request benchmark. A combined smoke test sampled 632 MiB after E5 load and 585 MiB after the first Whisper request; these are working-set snapshots rather than peak memory. |
| Assistant cache miss | 2.17 s in the latest measured integration run, including model load, PostgreSQL-compatible storage and a mocked LLM |
| Assistant cache hit | 72.1 ms in the latest measured integration run, including query embedding, pgvector and database writes. SQL-only latency was not measured. |
| Frontend assets | 489.20 kB main JS (149.94 kB gzip), 13.70 kB auxiliary JS (4.71 kB gzip), 28.83 kB CSS (7.50 kB gzip) |
| Speech inference | Synthetic English 3.58 s, Hindi 3.59 s and mixed 6.70 s on CPU |

ECS currently specifies 0.5 vCPU and 1 GiB RAM. Embeddings alone reached 652 MiB RSS on this Windows host before loading Whisper, serving requests or running concurrent work. Fit at 1 GiB is unverified. For a single worker, start container load validation at 2 vCPU and 4 GiB and measure peak RSS with overlapping voice and chat requests.

## Acceptance checklist

- **PASS** Backend starts without loading the speech model, health responds, and production frontend builds and renders.
- **PASS** English and Hindi selection, unsupported-language notice, mocked signup/confirmation/SRP, chat refresh and sidebar history, local request recovery, and simulated mic denial/upload.
- **PASS** JWT expiry, audience, issuer, token usage, verified email and validation error redaction in automated tests.
- **PASS** Disposable PGlite migration, account ownership checks, saved Blinkit history, embedding persistence, exact-repeat reuse with unchanged LLM count, and unrelated fallback.
- **PASS** CDK synthesis, infrastructure assertions, lockfile and Compose validation.
- **PASS** Shopping correction and cancellation, mocked Instagram attachment and review with explicit confirmation, and video troubleshooting controls.
- **FAIL** Mixed-language transcription fidelity on the synthetic sample and deployment-wide rate limiting.
- **BLOCKED** Live Cognito registration and password reset, Docker image build, native and existing-schema PostgreSQL migration, real microphone E2E, live external integrations, ECS resource and RDS engine validation, and unexecuted coverage described in the table.
- **BLOCKED** Release approval. CDK emitted a database engine-version validation warning for configured PostgreSQL 17.12, as well as availability-zone and cross-stack warnings. Target-region confirmation is pending. Before a real rollout, supply the public Cognito context values and verify ECS network access to the user pool JWKS and other required providers.

## Reproduce locally

Run from the repository root in PowerShell. The Compose database is disposable and binds only to loopback. Supply the Cognito values through the local backend environment template. The browser fixtures use Chrome and intercept Cognito and backend requests.

```powershell
uv sync --locked
uv pip install -r backend/requirements.txt -r aws_cloud/requirements.txt pytest httpx
npm.cmd --prefix frontend ci
if (!(Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
if (!(Test-Path frontend/.env.local)) { Copy-Item frontend/.env.example frontend/.env.local }

docker compose up -d --wait postgres
$env:DATABASE_URL = 'postgresql+psycopg://apnasathi:local-qa-only@127.0.0.1:55432/apnasathi_qa'
.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head
.venv/Scripts/python.exe -m alembic -c backend/alembic.ini current

# Use this terminal for the backend so it inherits DATABASE_URL.
# Start the frontend in a second terminal.
.venv/Scripts/python.exe -m uvicorn --app-dir backend app:app --host 127.0.0.1 --port 8000
npm.cmd --prefix frontend run dev

$env:PYTHONDONTWRITEBYTECODE = '1'
.venv/Scripts/python.exe -m pytest backend/tests aws_cloud/tests -q
.venv/Scripts/python.exe -m pytest backend/integration -q -s
npm.cmd --prefix frontend run build
.venv/Scripts/python.exe -m pytest frontend/tests -q
uv lock --check
docker compose config --quiet
docker build -t apnasathi-local-qa .

$env:CDK_DEFAULT_ACCOUNT = '111111111111'
cdk.cmd synth --no-lookups -a '.venv/Scripts/python.exe aws_cloud/app.py' `
  -c cognitoUserPoolId=ap-south-1_qxfax5y4B `
  -c cognitoClientId=6ltn4ni5clgd6b939epjcv78bh -o cdk.out
```

The database integration test accepts only the known loopback QA endpoints. PGlite was used as a local fallback during this run because Docker could not start. Native PostgreSQL remains part of the release gate.
