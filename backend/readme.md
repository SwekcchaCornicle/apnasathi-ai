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

## Deployment prerequisites

The existing private ECS subnets share the route table attached to the S3
gateway endpoint. The endpoint covers S3 traffic only. The current private
subnets have no external egress for Vertex AI or other external integrations.
The ALB target group also checks `/health`, while the API exposes
`/api/v1/health`. Resolve those existing deployment issues and put authentication
and rate limiting in front of the upload API before making it public.
