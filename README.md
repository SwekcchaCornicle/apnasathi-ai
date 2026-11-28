![ApnaSathi AI — Your world. One conversation away.](docs/brand/apnasathi-readme-hero.svg)

<p align="center">
  <a href="https://d03k1owznd.execute-api.ap-south-1.amazonaws.com/"><img src="https://img.shields.io/badge/Live%20App-Open%20ApnaSathi-354A3B?style=for-the-badge" alt="Live app"/></a>
  <img src="https://img.shields.io/badge/Frontend-React%20%2B%20Vite-405A46?style=for-the-badge" alt="React and Vite"/>
  <img src="https://img.shields.io/badge/Backend-FastAPI-76886F?style=for-the-badge" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/AI-Gemini%20%2B%20E5-D5A874?style=for-the-badge" alt="Gemini and E5"/>
  <img src="https://img.shields.io/badge/Cloud-AWS-354A3B?style=for-the-badge" alt="AWS"/>
</p>
<p align="center"><b>Speak naturally. Get things done. Stay in control.</b></p>

---

**ApnaSathi is a personal AI companion for everyday digital life.** Instead of jumping between screens and menus, you can simply type or speak what you need — in English or Hindi — and let the assistant guide you through the next step.

From shopping guidance and streaming discovery to Instagram photo drafts and everyday questions, ApnaSathi turns natural language into structured, useful workflows. **You stay in control:** the assistant explains, prepares and guides; you review and confirm actions.

### ✨ The experience, at a glance

<table>
  <tr>
    <td width="25%" align="center"><h2>💬</h2><b>Talk naturally</b><br/><sub>Type or speak in your language</sub></td>
    <td width="25%" align="center"><h2>🧠</h2><b>Understand intent</b><br/><sub>Gemini turns requests into structured intent</sub></td>
    <td width="25%" align="center"><h2>🧭</h2><b>Get guided actions</b><br/><sub>Purpose-built flows help with tasks</sub></td>
    <td width="25%" align="center"><h2>🔐</h2><b>Stay in control</b><br/><sub>You review before external actions</sub></td>
  </tr>
</table>

**Under the hood:** React + Vite power the experience; FastAPI coordinates requests; Gemini on Vertex AI understands intent; multilingual E5 embeddings support semantic answer reuse; PostgreSQL stores application data; and AWS CDK defines the cloud infrastructure.

> **A quick note about the cloud setup**
>
> ApnaSathi is a working web application. This README explains how its application code and AWS deployment design fit together. Some cloud resources are described from the CDK definitions, and their live status can vary by AWS environment. Where a feature needs an account-side secret, permission, or rollout check, that is called out in the relevant section.

---

## Contents 🧭

<sub>A guided tour from the product experience to the infrastructure behind it.</sub>

- [1. Product overview](#1-product-overview)
- [2. Application screenshots](#2-application-screenshots)
- [3. High-level architecture](#3-high-level-architecture)
- [4. One request, from browser to response](#4-one-request-from-browser-to-response)
- [5. Frontend architecture](#5-frontend-architecture)
- [6. Backend architecture](#6-backend-architecture)
- [7. AI, LLM, embeddings, and intent routing](#7-ai-llm-embeddings-and-intent-routing)
- [8. Application workflows](#8-application-workflows)
- [9. Database design](#9-database-design)
- [10. Audio and file storage](#10-audio-and-file-storage)
- [11. AWS architecture](#11-aws-architecture)
- [12. Docker and container design](#12-docker-and-container-design)
- [13. GitHub Actions and YAML pipelines](#13-github-actions-and-yaml-pipelines)
- [14. Local development](#14-local-development)
- [15. Configuration reference](#15-configuration-reference)
- [16. Tests and validation](#16-tests-and-validation)
- [17. Security and operational considerations](#17-security-and-operational-considerations)
- [18. Current implementation boundaries](#18-current-implementation-boundaries)
- [19. Repository layout](#19-repository-layout)

---

## 1. Product overview 🌱

### What problem does ApnaSathi solve? 🎯

A normal digital task can involve several steps: opening an application, finding the right screen, understanding a form, choosing an option, and confirming an action. That can be frustrating for someone who does not know the application well or who prefers speaking in their own language.

ApnaSathi brings a conversational interface in front of selected workflows. A user can type or speak a request such as:

- "I want to buy milk and potatoes on Blinkit."
- "Where can I watch this series in India?"
- "Help me prepare an Instagram post for this photo."
- "Explain this in Hindi."
- "What did I ask you about shopping last time?"

The assistant does not treat every sentence as the same kind of chat. It uses a structured intent response and routes the request to the relevant workflow.

### What is available in the current code? ✨

| Capability | What the implementation does |
| --- | --- |
| Account and sign-in | Uses Amazon Cognito for registration, email confirmation, SRP sign-in, and password reset |
| Language selection | The interface offers English and Hindi; backend language validation currently accepts `en` and `hi` |
| Text conversation | Sends text to the authenticated assistant endpoint |
| Voice conversation | Records browser audio, uploads it to the API, transcribes it with Faster-Whisper, and follows the same assistant flow |
| Shopping guidance | Uses a step-by-step state machine for Blinkit, Amazon, and Swiggy Instamart search and checkout guidance |
| Watch guidance | Uses Watchmode to find streaming availability and a separate yes/no troubleshooting flow |
| Instagram workflow | Supports a photo draft, Meta authorization, caption input/transcription, and user-directed publishing flow |
| Conversation history | Persists conversations and messages against the authenticated account |
| Speech response | Uses local Piper voice models for English and Hindi in supported response paths |
| Semantic answer reuse | Implements multilingual E5 embeddings and pgvector-backed answer matching for eligible general questions; see the integration boundary in [Section 18](#18-current-implementation-boundaries) |

### A simple example 💡

Imagine the user types:

```text
I want to buy milk, potatoes and bread on Blinkit.
```

The application roughly does this:

1. The browser sends the request and current conversation ID to FastAPI.
2. FastAPI checks the Cognito-authenticated user and confirms that the conversation belongs to that user.
3. The assistant gathers relevant conversation context and asks Gemini for a structured intent response.
4. The response identifies a shopping request and extracts the products.
5. The shopping state machine creates a guided shopping session.
6. The assistant returns a message, the next step, and retailer search links.
7. React displays the shopping guidance and the user decides what to do on the retailer's website.

**Important:** the shopping workflow guides the user and opens retailer links. It does not silently submit orders or payments. The user remains responsible for reviewing the cart, address, and payment on the retailer's own platform.

---

## 2. Application screenshots 📱

These screenshots were captured from the running ApnaSathi application after signing in. They show the real React interface served by the deployed API Gateway endpoint. The mobile image was captured at a 390 × 844 viewport.

### Authenticated chat workspace — desktop 🖥️

![ApnaSathi authenticated chat workspace on desktop](docs/screenshots/04-chat-workspace-desktop.jpg)

The workspace brings the assistant prompt, new-chat action, suggested starting points, message composer, microphone control, language selector, and account sign-out into one place. The suggestions shown are starting prompts; choosing one begins a conversation with that workflow.

### Authenticated chat workspace — mobile 📱

![ApnaSathi authenticated chat workspace on mobile](docs/screenshots/04-chat-workspace-mobile.jpg)

The same workspace is available in a narrow mobile layout. This is useful for a voice-first assistant because users can open the experience from a phone and start with a short text or spoken request.

### Other workflow screens 🧭

The repository also contains the language-selection and Cognito account screens, guided shopping logic, Watchmode lookup and troubleshooting, and the Instagram photo-draft workflow. Those screens are implemented in the source code, but are not represented by screenshots in this capture set. This README deliberately avoids using mockups or generated images as if they were screenshots of the running product.

---

## The ApnaSathi look & feel 🎨

The README follows the same visual language as the product: forest green for confident surfaces, sage for calm panels, warm sand for highlights, and soft paper backgrounds for readability.

![Complete ApnaSathi colour palette](docs/brand/apnasathi-palette.svg)

---

## 3. High-level architecture 🏗️

At a high level, ApnaSathi has four major areas:

1. **Frontend:** React and Vite provide the user interface, authentication screens, chat workspace, microphone capture, and action-specific components.
2. **Backend:** FastAPI receives requests, verifies the user, loads the conversation, invokes the AI layer when needed, routes the intent, and saves results.
3. **AI and integrations:** Gemini on Vertex AI classifies the request; local multilingual E5 embeddings are used by the semantic answer-reuse service; workflow modules connect to retailers, Watchmode, Meta, speech, and AWS storage.
4. **Cloud platform:** CDK defines the AWS network, PostgreSQL database, S3 audio bucket, ECR repository, ECS Fargate service, Application Load Balancer, IAM roles, and CloudWatch logs.

### System context diagram 🌐

![ApnaSathi request journey — visual sequence diagram](docs/architecture/request-journey.svg)

**How to read it:** follow the numbered cards from left to right, then follow the decision branch. A semantic-cache hit can reuse a saved answer; otherwise the request continues through Gemini and the selected workflow.


This diagram shows the logical integrations. It does not imply that every feature is invoked for every request. For example, a normal general question does not need Watchmode or the Instagram Graph API.

### Runtime deployment diagram ☁️

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#D5DDBD","primaryTextColor":"#252A23","primaryBorderColor":"#354A3B","lineColor":"#76886F","secondaryColor":"#EDF0E6","tertiaryColor":"#F2E4D2","background":"#FBFAF7"}}}%%
flowchart TB
  U([🌐 User / Browser]) --> FE[🌿 React + Vite]
  FE -->|Sign in| COG[🔐 Amazon Cognito]
  FE -->|HTTPS API request| APIGW[🚪 API Gateway]
  APIGW --> ALB[⚖️ Application Load Balancer]
  subgraph VPC["☁️ AWS VPC · ap-south-1"]
    subgraph PUBLIC["🌤️ Public subnets · two Availability Zones"]
      ALB
    end
    subgraph PRIVATE["🌱 Private subnets · two Availability Zones"]
      ECS[🐳 ECS Fargate · FastAPI]
      RDS[(🗄️ RDS PostgreSQL)]
      S3[(🪣 Private S3 audio bucket)]
      SM[🔑 Secrets Manager]
      CW[📈 CloudWatch Logs]
    end
    ECR[📦 Amazon ECR]
  end
  ALB --> ECS
  ECS --> RDS
  ECS --> S3
  ECS --> SM
  ECS --> CW
  ECR -. image .-> ECS
  style VPC fill:#EDF0E6,stroke:#354A3B,stroke-width:3px,color:#354A3B
  style PUBLIC fill:#F4F6EF,stroke:#D5A874,stroke-width:2px,color:#354A3B
  style PRIVATE fill:#FBFAF7,stroke:#76886F,stroke-width:2px,color:#354A3B
```


### Step 1 — User enters a request ➡️

The user types a message in `ChatWorkspace.jsx`. The frontend keeps the current conversation ID and builds a JSON request:

```json
{
  "conversation_id": "the-current-conversation-uuid",
  "message": "Find where I can watch this show"
}
```

### Step 2 — React calls the backend ➡️

The `apiRequest()` helper in `frontend/src/ChatWorkspace.jsx` sends the request to:

```http
POST /api/v1/assistant/chat
Authorization: Bearer <Cognito ID token>
Content-Type: application/json
```

The API base URL comes from `VITE_API_BASE_URL`. For local development it can point to `http://localhost:8000/api/v1`; for the hosted frontend the deployment workflow builds with `/api/v1`.

### Step 3 — FastAPI verifies the request context ➡️

The assistant endpoint receives the authenticated `User` through `get_current_user` and a SQLAlchemy database session through `get_db`.

It checks that:

- the conversation exists;
- the conversation belongs to the authenticated user;
- the conversation is not archived;
- the requested language is supported;
- the message is not empty and meets the input length limit.

This ownership check matters. Knowing another person's conversation UUID must not grant access to their messages.

### Step 4 — The message is persisted ➡️

The backend creates the user message and associates it with the user and conversation. This gives the request a durable place in conversation history.

### Step 5 — The assistant selects the processing path ➡️

The assistant checks whether the message is eligible for a reusable-answer lookup. Action requests, requests for current information, active shopping workflows, and some history-dependent requests are excluded from that optimization.

For eligible general questions, the semantic lookup helper can compare the query embedding with stored answer embeddings. A reusable result is only acceptable when it passes the configured similarity and quality constraints and belongs to the current user (unless the separately controlled shared-knowledge feature is enabled).

When there is no reusable answer, the backend prepares context from recent messages and applicable saved memories, then invokes the Gemini model through Vertex AI.

### Step 6 — Gemini returns structured intent ➡️

The LLM is configured to return JSON matching the Pydantic `IntentSchema`. The schema includes:

- `intent`;
- `application`;
- `show_name`;
- `shopping_items`;
- `confidence`;
- `response`;
- `response_language`;
- `requires_confirmation`;
- `entities`.

The backend does not need to guess what an unstructured paragraph means. It reads the validated fields and routes to the correct handler.

### Step 7 — A workflow performs the next step ➡️

Examples:

- `ORDER_GROCERIES` starts or continues the shopping state machine.
- `WATCH_SHOW` calls the Watchmode-backed title and availability logic.
- `POST_PHOTO` returns the next Instagram draft step.
- `GENERAL_QUESTION` or `GENERAL_CONVERSATION` returns the model's response.
- `OPEN_APP` currently returns a confirmation-oriented response; it does not demonstrate unrestricted operating-system control.

### Step 8 — Result is saved and returned ➡️

The backend persists the assistant message and a search-history record, updates the conversation timestamp, and returns a structured response containing the answer, intent, language, source, and any workflow payload.

### Request sequence diagram 🔄

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#D5DDBD","primaryTextColor":"#252A23","primaryBorderColor":"#354A3B","lineColor":"#76886F","secondaryColor":"#EDF0E6","tertiaryColor":"#F2E4D2","background":"#FBFAF7"}}}%%
sequenceDiagram
    actor User
    participant React as React ChatWorkspace
    participant API as FastAPI
    participant Auth as Cognito/JWT
    participant DB as PostgreSQL
    participant Cache as E5 + pgvector helper
    participant Gemini as Vertex AI Gemini
    participant Flow as Workflow handler
    User->>React: Type message
    React->>API: POST /assistant/chat + Bearer token
    API->>Auth: Verify token claims and signature
    Auth-->>API: Verified identity
    API->>DB: Load owned conversation
    API->>DB: Save user message
    API->>Cache: Eligible semantic lookup
    alt Eligible answer found
      Cache-->>API: Reusable answer + similarity
    else Cache miss / not eligible
      API->>DB: Load recent messages and saved memories
      API->>Gemini: Prompt + context + response schema
      Gemini-->>API: Structured intent JSON
      API->>Flow: Route selected intent
      Flow-->>API: Workflow response and action data
    end
    API->>DB: Save assistant message and search history
    API-->>React: Structured assistant response
    React-->>User: Render answer and workflow controls
```

---

## 5. Frontend architecture 🖥️

### Technology choices 🧰

| Technology | Purpose |
| --- | --- |
| React | UI components and local application state |
| Vite | Development server and production build |
| JavaScript / JSX | Component and browser logic |
| CSS | Layout, responsive styling, and visual presentation |
| AWS SDK Cognito Identity Provider client | Registration, verification, password reset, and Cognito requests |
| `amazon-cognito-identity-js` | SRP sign-in helper used by the Cognito authentication module |
| Browser MediaRecorder API | Captures microphone audio |
| Browser IndexedDB | Stores local browser recordings in the standalone recorder component |
| Browser SpeechSynthesis API | Speaks assistant responses in the chat workspace |

The dependencies and scripts are defined in `frontend/package.json`.

### Frontend component map 🧩

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#D5DDBD","primaryTextColor":"#252A23","primaryBorderColor":"#354A3B","lineColor":"#76886F","secondaryColor":"#EDF0E6","tertiaryColor":"#F2E4D2","background":"#FBFAF7"}}}%%
flowchart TB
    MAIN[main.jsx]
    APP[App.jsx]
    LANG[LanguageStep]
    LOGIN[LoginStep]
    CHAT[ChatWorkspace.jsx]
    REC[AudioRecorder.jsx]
    DRAFT[InstagramDraft.jsx]
    AUDIO[audioStorage.js]
    COG[cognito.js]
    CSS[styles.css]
    MAIN --> APP
    APP --> LANG
    APP --> LOGIN
    APP --> CHAT
    APP --> COG
    CHAT --> DRAFT
    REC --> AUDIO
    APP --> CSS
    CHAT --> CSS
    REC --> CSS
    DRAFT --> CSS
```

### `App.jsx` — application entry and session flow

The top-level component controls the first-use experience and authenticated workspace.

It is responsible for:

- presenting the welcome screen;
- allowing the user to choose English or Hindi;
- handling sign-up, email confirmation, sign-in, and password reset;
- asking Cognito to authenticate the user;
- sending the returned ID token to `POST /auth/cognito`;
- saving the selected language using `PATCH /users/me/profile`;
- keeping the token and language in `sessionStorage` for the browser tab session;
- switching to `ChatWorkspace` after successful sign-in;
- clearing the tab session on sign-out.

The frontend stores the token in session storage, not in a long-lived application database or source file. A browser session is still a security boundary that needs careful handling on shared devices.

### `cognito.js` — SRP sign-in helper

The Cognito helper contains the sign-in operation used by the login flow. The frontend passes the configured User Pool ID, public app client ID, email, and password to the SRP client.

The backend does not blindly trust the frontend's claim that sign-in succeeded. It verifies the ID token signature using the Cognito JSON Web Key Set (JWKS), validates the token issuer and audience, checks expiry and token use, and requires a verified email before creating or updating the local account.

### `ChatWorkspace.jsx` — main chat experience

This is the central authenticated React component.

**State it manages includes:**

- the list of conversations;
- the currently selected conversation ID;
- messages in the active conversation;
- groups used to organize conversation history by detected intent;
- message draft text;
- request/loading state;
- microphone recording and permission state;
- history search;
- a video troubleshooting guide;
- Instagram draft visibility;
- user-facing error and status notices.

**Important helper functions:**

- `apiRequest()` adds the Bearer token, sends the HTTP request, parses the response, and converts API errors into user-readable messages.
- `refreshConversations()` loads the user's conversation list and then fetches messages for each conversation.
- `sendText()` posts a message to `/assistant/chat`, temporarily displays the outgoing message, replaces it with persisted response data, and refreshes history.
- `toggleMic()` requests microphone permission, creates a `MediaRecorder`, gathers audio chunks, and submits the resulting blob to `/assistant/audio`.
- `guideVideo()` sends a platform, troubleshooting step, and optional spoken answer to `/watch-show/troubleshoot`.
- `speakReply()` uses browser speech synthesis to read a response in the current supported language.
- `openVideoResult()` accepts only a validated HTTPS playback URL before navigating a new tab.

When an API call returns HTTP 401, the shared request helper invokes sign-out. This prevents the UI from continuing to behave as though an expired session were valid.

### `InstagramDraft.jsx` — photo and caption workflow

This component owns the interactive Instagram draft UI:

1. the user selects a photo;
2. the component previews it locally using an object URL;
3. the user enters a caption or records a spoken caption;
4. the component sends the image and caption to the protected backend route;
5. the server creates a draft and returns an authorization action;
6. the browser opens the Meta authorization URL;
7. the component polls the draft status;
8. the user reviews the caption and confirms the publish step.

The component revokes its local object URL when the selected photo changes or the component unmounts. Microphone tracks are also stopped when recording completes or the component is removed.

### `AudioRecorder.jsx` and `audioStorage.js`

The repository also contains a separate recorder-oriented UI. It reads and writes browser recordings through IndexedDB helpers in `audioStorage.js`, checks the backend health endpoint, and presents recording, playback, shopping, Instagram, and video-guide interactions.

This local browser recording store is different from the private S3 bucket used by the backend upload route. A browser recording is not automatically the same thing as a durable account-owned S3 recording.

### Frontend-to-backend communication

| Frontend action | API path | Request type |
| --- | --- | --- |
| Cognito token exchange | `/auth/cognito` | JSON |
| Read or update profile | `/users/me`, `/users/me/profile` | JSON |
| List/create conversations | `/conversations` | JSON |
| Read conversation messages | `/conversations/{id}/messages` | JSON |
| Send chat message | `/assistant/chat` | JSON |
| Send voice message | `/assistant/audio?conversation_id={id}` | Multipart form data |
| Shopping reply | `/shopping/reply` | Multipart form data |
| Video troubleshooting | `/watch-show/troubleshoot` | Multipart form data |
| Instagram image draft | `/instagram/photo` | Multipart form data |
| Instagram caption transcription | `/instagram/caption` | Multipart form data |
| Instagram authorization status | `/instagram/status` | HTTP request |

The API routers are mounted by `backend/app.py`. Refer to the route functions for the exact payload and authentication requirements.

---

## 6. Backend architecture ⚙️

### Technology choices 🧰

| Technology | Purpose |
| --- | --- |
| Python 3.13 | Backend runtime |
| FastAPI | REST API and request handling |
| Uvicorn | ASGI server |
| Pydantic | Request/response validation and structured LLM output |
| SQLAlchemy 2.x | Relational data access and ORM |
| Psycopg 3 | PostgreSQL driver |
| Alembic | Database schema migrations |
| pgvector | PostgreSQL vector column and similarity operations |
| Google Gen AI SDK | Gemini model calls through Vertex AI |
| Faster-Whisper | Speech-to-text |
| FastEmbed | Local embedding inference |
| Piper | Local text-to-speech |
| boto3 | AWS service access, including S3 |
| PyJWT | Cognito token verification |
| requests | External HTTP APIs |

### Backend package structure 🗂️

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#D5DDBD","primaryTextColor":"#252A23","primaryBorderColor":"#354A3B","lineColor":"#76886F","secondaryColor":"#EDF0E6","tertiaryColor":"#F2E4D2","background":"#FBFAF7"}}}%%
flowchart TB
    APP[backend/app.py]
    ROUTERS[API routers]
    AUTH[auth/]
    DB[database/]
    LLM[llm_model/]
    EMB[embeddings/]
    AGENTS[agents/]
    SERVICES[services/]
    STORAGE[storage/]
    TRACE[request_tracing.py]
    APP --> ROUTERS
    APP --> TRACE
    ROUTERS --> AUTH
    ROUTERS --> DB
    ROUTERS --> LLM
    ROUTERS --> AGENTS
    ROUTERS --> SERVICES
    ROUTERS --> STORAGE
    SERVICES --> EMB
    SERVICES --> DB
    AGENTS --> LLM
    AGENTS --> STORAGE
```

### `backend/app.py` — FastAPI application assembly

This file is the application composition point.

It:

- loads the backend environment file when present;
- creates the FastAPI application and health router;
- configures CORS and request tracing middleware;
- initializes the cached Faster-Whisper model loader;
- imports and mounts the assistant, authentication, knowledge, persistence, and Instagram routers;
- exposes the legacy/helper workflow routes for shopping, audio upload, and video troubleshooting;
- handles audio validation and transcription paths.

The Whisper model loader is cached so the model is not re-created for every request.

### `backend/api/assistant.py` — conversation orchestration

This module is the main chat decision layer.

The text route is `POST /assistant/chat`. It:

1. receives the authenticated user and database session;
2. checks ownership of the active conversation;
3. validates the language and message;
4. creates a user message record;
5. determines whether semantic answer reuse is eligible;
6. handles a matching saved Blinkit-history request where applicable;
7. continues an active shopping flow when applicable;
8. attempts semantic answer reuse for eligible general questions;
9. otherwise prepares conversation and memory context for Gemini;
10. interprets the returned intent and dispatches the relevant helper;
11. writes the assistant response and search-history record;
12. returns a typed `AssistantChatResponse`.

The audio route is `POST /assistant/audio`. It validates the file, transcribes it in a temporary directory, rejects empty or excessively long transcripts, and calls the same text assistant function. This keeps voice and text requests on the same intent-routing and persistence path.

### `backend/api/auth.py` and `backend/auth/`

The authentication implementation has two responsibilities.

**Frontend identity provider:** Amazon Cognito owns registration, email confirmation, sign-in, and password reset.

**Backend token validation:** `backend/auth/cognito.py` verifies the ID token using the user pool's public JWKS key set. It checks the signature algorithm, issuer, app-client audience, expiration, token-use claim, and required identity claims. `backend/auth/dependencies.py` exposes the authenticated user to protected routes.

The `POST /auth/cognito` endpoint maps the Cognito subject to a local `users` row and creates a profile when necessary. The provider-subject pair is unique, which gives the backend a stable identity key.

### `backend/api/persistence.py` — user-owned data APIs

This router exposes conversation, message, search-history, profile-memory, and language-related persistence operations. It uses the authenticated user's ID when reading or changing private data.

The ownership helper checks that a conversation belongs to the current account before returning it.

### `backend/api/knowledge.py` — semantic lookup API

This route accepts a question, intent, and optional language. It only attempts reuse for the explicitly permitted reusable intents. A miss is returned as `llm_required`, which lets the normal model path continue.

Semantic lookup is treated as an optimization: a database or embedding problem should not incorrectly return an unrelated answer as though it were a valid match.

### `backend/llm_model/` — model integration and schema

- `llm_model.py` builds the prompt and calls Gemini through the Google Gen AI SDK.
- `intent_classifier.py` defines the Pydantic output schema.
- `prompt.py` contains the model instruction/prompt construction.
- `classify_intent_action.py` maps a structured intent to the corresponding application handler.
- `vertex_auth.py` creates the Vertex client and selects the configured Google authentication flow.

The classification request uses a JSON response MIME type and a response schema. This makes the model output easier for the application to validate and route.

### `backend/agents/` — workflow-specific logic

These modules keep workflow details separate from the general API handler.

- `greeting.py`: greeting response helpers.
- `shoaping.py`: the shopping state machine and retailer search URL builder. The source filename uses the spelling `shoaping.py`; imports should retain that spelling.
- `social_media.py`: Instagram/Meta OAuth, account resolution, image container creation, and publish operations.
- `speech.py`: Piper voice synthesis for Hindi and English.
- `watch_show/watch_show.py`: searches titles and sources through Watchmode and prepares safe streaming/search choices.
- `watch_show/troubleshoot.py`: deterministic yes/no playback troubleshooting prompts, including Hindi variants.

### `backend/services/` — shared application services

- `answer_reuse.py` normalizes questions, generates query and passage embeddings, applies similarity/quality/age constraints, and stores approved reusable answers.
- `conversation_memory.py` contains trusted persistence helpers for assistant replies and normalized search history.

### `backend/storage/s3_audio_storage.py` — S3 recording storage

This module validates audio types and file signatures, enforces a 25 MiB file limit, generates server-owned UUID object keys, and writes objects to the configured S3 bucket. It uses server-side encryption and does not expose the object key in the upload response.

### API request path at a glance 🛤️

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#D5DDBD","primaryTextColor":"#252A23","primaryBorderColor":"#354A3B","lineColor":"#76886F","secondaryColor":"#EDF0E6","tertiaryColor":"#F2E4D2","background":"#FBFAF7"}}}%%
flowchart TD
    R[HTTP request] --> MW[FastAPI middleware and tracing]
    MW --> AUTH{Protected route?}
    AUTH -->|Yes| JWT[Verify Cognito ID token]
    AUTH -->|No / public health| ROUTE[Resolve route]
    JWT --> ROUTE
    ROUTE --> VALID[Validate path, payload and language]
    VALID --> DBSESSION[Open SQLAlchemy session]
    DBSESSION --> OWNER[Validate current-user ownership]
    OWNER --> LOGIC[Run assistant or workflow logic]
    LOGIC --> PERSIST[Persist relevant state]
    PERSIST --> COMMIT[Commit on successful request]
    COMMIT --> RESP[JSON response]
    DBSESSION -->|Exception| ROLLBACK[Rollback and close session]
```

---

## 7. AI, LLM, embeddings, and intent routing 🧠

This is the important distinction in the AI design:

- **Gemini is the language model used to understand a request and create a structured response.**
- **E5 is an embedding model used to turn text into numeric vectors so semantically similar saved questions can be compared.**
- **The workflow handlers are ordinary application code.** They validate inputs, manage steps, and call external services.

These components have different jobs and are not interchangeable.

### 7.1 Gemini on Google Vertex AI 🔹

The current model call is configured in `backend/llm_model/llm_model.py`:

- model identifier: `gemini-3.8-flash`;
- structured response: JSON;
- schema: `IntentSchema`;
- temperature: `0.1`.

The low temperature is intended to make structured intent decisions more consistent, though it does not guarantee identical outputs.

For shopping item extraction, a separate call uses `gemini-3.1-flash-lite` with a smaller `ShoppingItems` schema. This helper extracts product names from a spoken shopping transcript and tries to preserve quantities and the user's language.

Model identifiers are code-level configuration. Confirm model availability and access in the target Google Cloud project before deployment.

### 7.2 Intent schema 🔹

The intent schema currently supports:

| Intent | Meaning | Handler behaviour |
| --- | --- | --- |
| `GREETING` | Greeting or welcome | Greeting helper |
| `OPEN_APP` | User asks to open an app | Returns an app-specific confirmation response |
| `POST_PHOTO` | User wants help with an Instagram photo | Starts the photo/caption workflow |
| `WATCH_SHOW` | User wants to find or watch a movie/show | Watchmode and playback guide |
| `ORDER_GROCERIES` | User wants to shop for groceries | Shopping state machine |
| `GENERAL_QUESTION` | Informational question | Reusable-answer lookup or Gemini response |
| `GENERAL_CONVERSATION` | Conversational message | Gemini response |
| `UNKNOWN` | Model cannot map the request | Safe fallback response |

The schema also carries the detected application, show name, shopping items, confidence, response language, entities, and whether the next step requires confirmation.

### 7.3 Why use embeddings? 🔹

A language model call is useful for interpreting a new request, but some users may ask the same informational question repeatedly using different wording.

For example:

```text
Question 1: How do I reset my phone?
Question 2: Tell me the steps to restart my mobile settings.
```

The wording differs, but the meaning may be close. Exact string matching is not enough for that case.

An embedding model converts a sentence into a fixed-size vector. Similar meanings are represented by vectors that can be close under a similarity metric.

### 7.4 Multilingual E5 embeddings 🔹

The embedding implementation is in `backend/embeddings/e5.py`.

Current characteristics:

- model family: multilingual E5 base;
- configured identifier: `Xenova/multilingual-e5-base` by default;
- inference library: FastEmbed;
- runtime: local CPU/ONNX inference;
- vector dimensions: 768;
- vectors are normalized before use;
- query text is prefixed with `query:`;
- stored question/answer passage text is prefixed with `passage:`.

The query/passage prefixes are part of the E5 retrieval convention. Query and passage vectors are generated for their respective roles.

**Why local embeddings?**

The application can create query vectors inside the backend instead of making a separate hosted embedding API request. The model can be cached in the container image and used for inference on the ECS task. This reduces a separate external inference dependency for this part of the pipeline, although it still consumes local CPU and memory.

### 7.5 Semantic answer reuse 🔹

The service in `backend/services/answer_reuse.py` applies several checks before returning a saved answer:

1. The intent must be in the reusable-intent allowlist. Currently that is `GENERAL_QUESTION`.
2. The question is normalized.
3. An E5 query embedding is generated.
4. PostgreSQL/pgvector calculates cosine distance against eligible entries.
5. Only active entries from the expected embedding model are considered.
6. Entries must be recent enough (the code uses a 30-day maximum age).
7. Entries must have a non-empty answer and a quality score of at least `0.80`.
8. Private entries must belong to the current user. Shared entries are considered only when shared knowledge is explicitly enabled and must have no user ID.
9. The best candidate must pass the configured similarity threshold. The default is `0.88`.
10. A successful match increments the reuse count.

Action requests and current-information questions are not supposed to be answered from this cache. For example, a shopping request should not be replayed because an older request happened to have similar wording.

### 7.6 Retrieval and LLM flow 🔹

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#D5DDBD","primaryTextColor":"#252A23","primaryBorderColor":"#354A3B","lineColor":"#76886F","secondaryColor":"#EDF0E6","tertiaryColor":"#F2E4D2","background":"#FBFAF7"}}}%%
flowchart TD
    Q[User question] --> CLEAN[Normalize question]
    CLEAN --> ELIGIBLE{Eligible for reuse?}
    ELIGIBLE -->|No| CTX[Build current conversation context]
    ELIGIBLE -->|Yes| EMBQ[Create E5 query vector]
    EMBQ --> SEARCH[pgvector cosine-distance search]
    SEARCH --> FILTER[User scope, intent, language, age, quality]
    FILTER --> THRESHOLD{Similarity above threshold?}
    THRESHOLD -->|Yes| REUSE[Return saved answer]
    THRESHOLD -->|No| CTX
    CTX --> PROMPT[Construct Gemini prompt]
    PROMPT --> MODEL[Gemini structured generation]
    MODEL --> ROUTE[Route intent]
    ROUTE --> SAVE[Persist response and search history]
    REUSE --> SAVE
    SAVE --> RESPONSE[Return response to frontend]
```

**Implementation boundary:** the repository contains the embedding model, pgvector schema, semantic lookup service, knowledge endpoint, and assistant lookup call. However, the root/backend documentation notes that the first database migration originally established the schema without completing every embedding inference and cache-write integration. The current code has since added service and call-site logic, but the full path must be verified against the deployed database, migration state, and end-to-end tests before describing it as a production-proven retrieval system. See [Section 18](#18-current-implementation-boundaries).

### 7.7 Conversation context and memory 🔹

Before a Gemini fallback call, the assistant can assemble:

- recent messages in the current conversation;
- active saved memories for the current user;
- recent shopping-related messages for that same user.

The assembled context is bounded before it is placed into the prompt. This gives the model relevant continuity without sending an unlimited conversation transcript.

The `memories` table is user-scoped and supports a category, key, value, confidence, active flag, optional expiry, and source message reference. Memory data should be treated as private user data.

---

## 8. Application workflows 🧩

### 8.1 Shopping workflow 🔹

The shopping logic lives in `backend/agents/shoaping.py`. The intentionally step-based design means the application does not attempt to complete a purchase on behalf of the user.

Supported retailers in the current source:

- Blinkit;
- Amazon India;
- Swiggy Instamart.

The session stores:

- current step;
- selected store;
- shopping item list;
- current item index.

Simplified state flow:

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#D5DDBD","primaryTextColor":"#252A23","primaryBorderColor":"#354A3B","lineColor":"#76886F","secondaryColor":"#EDF0E6","tertiaryColor":"#F2E4D2","background":"#FBFAF7"}}}%%
stateDiagram-v2
    [*] --> ChooseStore
    ChooseStore --> SignIn: Store selected
    SignIn --> EnterItems: User confirms sign-in
    EnterItems --> ReviewItem: Items extracted
    ReviewItem --> ReviewItem: More items
    ReviewItem --> CartReview: All item links reviewed
    CartReview --> CheckoutGuide: User requests checkout help
    CheckoutGuide --> PaymentReview: Address and delivery checked
    PaymentReview --> UserCompletesPayment: User confirms readiness
    UserCompletesPayment --> [*]
    CartReview --> Done: User declines / completes guidance
    Done --> [*]
```

The backend returns retailer search links, prompts, and yes/no choices. The user opens the retailer and independently signs in, selects products, reviews their cart, enters delivery information, and completes payment.

### 8.2 Watch-show workflow 🔹

The title lookup helper in `backend/agents/watch_show/watch_show.py` calls the Watchmode API.

At a high level:

1. Gemini identifies the requested show title and optional preferred application/platform.
2. The Watchmode integration searches for the title.
3. The implementation attempts an exact normalized title match.
4. If an exact match is not found, similar titles can be proposed.
5. The helper loads region-specific streaming sources (the current code defaults to India, `IN`).
6. It filters and prioritizes safe HTTPS streaming links.
7. The assistant returns a ready link or a provider search link.

The separate `troubleshoot.py` helper uses a deterministic state machine. It asks whether the tab opened, whether the user signed in, and whether the video is playing. A recognized yes/no answer advances the next step. It does not call the LLM for this simple confirmation state machine.

### 8.3 Instagram photo workflow 🔹

The Instagram workflow uses the Meta Graph API and a professional Instagram account linked to a Facebook Page.

Simplified sequence:

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#D5DDBD","primaryTextColor":"#252A23","primaryBorderColor":"#354A3B","lineColor":"#76886F","secondaryColor":"#EDF0E6","tertiaryColor":"#F2E4D2","background":"#FBFAF7"}}}%%
sequenceDiagram
    actor User
    participant UI as InstagramDraft
    participant API as FastAPI Instagram router
    participant Meta as Meta OAuth / Graph API
    participant DB as PostgreSQL
    participant S3 as Image hosting origin
    User->>UI: Select photo and caption
    UI->>API: POST /instagram/photo
    API->>DB: Create user-owned draft and state
    API-->>UI: Draft state and authorization URL
    UI->>Meta: User authorizes account
    Meta-->>API: OAuth callback with state and code
    API->>Meta: Exchange code and resolve linked professional account
    API->>DB: Save draft authorization state
    UI->>API: Poll /instagram/status
    API-->>UI: Caption/review step
    UI->>API: User confirms publish
    API->>S3: Provide temporary public HTTPS image URL
    API->>Meta: Create media container
    API->>Meta: Publish container
    API->>DB: Update draft status
    API-->>UI: Publishing result
```

The code keeps Instagram credentials out of repr-visible dataclass fields and uses the backend to call Meta. The Instagram app secret is configured server-side. A temporary public HTTPS image URL is required by the photo-container request; the image origin therefore needs to be configured and secured separately from the private audio bucket.

The workflow is not equivalent to an unrestricted Instagram automation. It depends on Meta permissions, a professional account setup, a valid callback configuration, and user authorization. Test with an approved professional test account.

### 8.4 Voice input and voice response 🔹

**Voice input:**

1. React requests browser microphone permission.
2. `MediaRecorder` captures supported audio.
3. The frontend sends a multipart request.
4. FastAPI validates MIME type, file size, and file signature.
5. Faster-Whisper transcribes the file.
6. The transcript is sent through the assistant's text path.

**Voice output:**

- `backend/agents/speech.py` uses Piper ONNX voice models.
- English uses `en_US-hfc_female-medium`.
- Hindi uses `hi_IN-priyamvada-medium`.
- The helper returns base64-encoded WAV audio when synthesis is available.
- The chat workspace also uses the browser's SpeechSynthesis API for spoken assistant responses.

The standalone recorder and chat workspace have different presentation code; do not assume every response path uses the same voice playback mechanism.

---

## 9. Database design 🗃️

### Database technology

The database layer is built around:

- Amazon RDS for PostgreSQL in the AWS infrastructure;
- SQLAlchemy 2.x as the ORM;
- Psycopg 3 as the PostgreSQL driver;
- Alembic for schema migration;
- pgvector for 768-dimensional embedding storage and cosine-distance search;
- PostgreSQL JSONB fields for flexible metadata and preferences.

The database connection is created in `backend/database/session.py`. It accepts either a complete `DATABASE_URL` or the RDS connection fields and JSON credentials injected into the ECS task.

### Entity relationship diagram 🔗

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#D5DDBD","primaryTextColor":"#252A23","primaryBorderColor":"#354A3B","lineColor":"#76886F","secondaryColor":"#EDF0E6","tertiaryColor":"#F2E4D2","background":"#FBFAF7"}}}%%
erDiagram
    USERS ||--|| USER_PROFILES : has
    USERS ||--o{ CONVERSATIONS : owns
    USERS ||--o{ MESSAGES : authors
    CONVERSATIONS ||--o{ MESSAGES : contains
    USERS ||--o{ SEARCH_HISTORY : creates
    CONVERSATIONS ||--o{ SEARCH_HISTORY : relates_to
    USERS ||--o{ MEMORIES : owns
    MESSAGES ||--o{ MEMORIES : sourced_from
    USERS ||--o{ KNOWLEDGE_EMBEDDINGS : owns_private
    MESSAGES ||--o{ KNOWLEDGE_EMBEDDINGS : sourced_from
    USERS ||--o{ AGENT_EXECUTIONS : runs
    CONVERSATIONS ||--o{ AGENT_EXECUTIONS : groups
    MESSAGES ||--o{ AGENT_EXECUTIONS : traces
    USERS ||--o{ INSTAGRAM_DRAFTS : owns
    USERS {
      uuid id PK
      varchar auth_provider
      varchar auth_subject
      varchar email
      boolean email_verified
      boolean is_active
      timestamptz last_seen_at
    }
    USER_PROFILES {
      uuid user_id PK,FK
      varchar display_name
      varchar preferred_language
      varchar timezone
      jsonb preferences
    }
    CONVERSATIONS {
      uuid id PK
      uuid user_id FK
      varchar title
      varchar channel
      varchar language
      boolean is_archived
    }
    MESSAGES {
      uuid id PK
      uuid conversation_id FK
      uuid user_id FK
      varchar role
      text content
      varchar language
      varchar intent
      jsonb metadata
    }
    SEARCH_HISTORY {
      uuid id PK
      uuid user_id FK
      uuid conversation_id FK
      text query
      text normalized_query
      varchar intent
      varchar language
      varchar result_source
    }
    MEMORIES {
      uuid id PK
      uuid user_id FK
      varchar category
      varchar memory_key
      text memory_value
      float confidence
      boolean is_active
      timestamptz expires_at
    }
    KNOWLEDGE_EMBEDDINGS {
      uuid id PK
      uuid user_id FK
      uuid source_message_id FK
      text question
      text normalized_question
      text answer
      varchar intent
      varchar language
      varchar embedding_model
      vector_768 embedding
      varchar visibility
      float quality_score
      integer reuse_count
      boolean is_active
    }
    AGENT_EXECUTIONS {
      uuid id PK
      uuid user_id FK
      uuid conversation_id FK
      uuid message_id FK
      varchar agent_name
      varchar action_name
      varchar status
      jsonb input_metadata
      jsonb output_metadata
      varchar error_code
    }
    INSTAGRAM_DRAFTS {
      varchar id PK
      uuid owner_id FK
      varchar state_hash
      varchar image_key
      bytea image
      varchar caption
      varchar phase
      timestamptz expires_at
      text notice
      text media_id
    }
```

The diagram includes the Instagram drafts table created in the second migration. It shows the logical ownership relationships; the exact column definitions and constraints are in `backend/database/models.py` and the Alembic migration files.

### Table-by-table explanation 📚

#### `users`

One row represents one local ApnaSathi account.

- `id` is the local UUID primary key.
- `auth_provider` records the identity provider.
- `auth_subject` stores the stable provider subject.
- `email` and `email_verified` hold verified account email state.
- `is_active` allows the account to be disabled.
- `last_seen_at` tracks the last successful identity exchange.
- A unique constraint on `(auth_provider, auth_subject)` prevents duplicate local accounts for the same identity.

#### `user_profiles`

One-to-one profile settings for the user.

- display name;
- preferred language;
- timezone (default `Asia/Kolkata`);
- JSONB preferences.

The frontend updates the preferred language after sign-in.

#### `conversations`

A conversation belongs to one user.

- title;
- channel (for example, chat);
- language;
- archived flag;
- creation and update timestamps.

The index on user and update time supports recent conversation retrieval.

#### `messages`

Every message is associated with both a user and a conversation.

- role: user, assistant, system, or tool;
- text content;
- language;
- detected intent;
- JSONB metadata.

The metadata can carry workflow-specific information such as shopping or playback context. Database constraints restrict the allowed message roles.

#### `search_history`

Records user queries and the processing metadata associated with them:

- original query;
- normalized query;
- conversation reference;
- detected intent;
- language;
- result source such as Gemini, a saved history response, or semantic cache.

This helps understand the path taken to answer a request without mixing one user's search history with another's.

#### `memories`

Stores explicit user-scoped facts or preferences that can be included as context in future assistant calls.

Each memory has a category, key, value, confidence, active flag, optional expiry, and optional source message. Expired or inactive memories should not be used as active context.

#### `knowledge_embeddings`

Stores question/answer material that can be considered for semantic reuse.

Important fields:

- question and normalized question;
- answer;
- intent and language;
- embedding model identifier;
- 768-dimensional pgvector embedding;
- visibility (`private` or `shared`);
- quality score;
- reuse count;
- active flag.

A database check constraint enforces the tenant rule: a shared item has no `user_id`, while a private item must have one. This is an important privacy boundary.

#### `agent_executions`

An audit-oriented table for workflow/agent execution metadata. It can associate an execution with the user, conversation, and message, and record an agent name, action name, status, input/output metadata, and error code.

The existence of this table does not by itself prove that every workflow currently writes an audit row. Confirm call sites before relying on it for operational audit reporting.

#### `instagram_drafts`

The second migration creates a user-owned Instagram draft table. It contains draft state, a hashed state reference, image metadata/content, caption, phase, expiry, notice, and Meta media ID. It is associated with `users` and deletes when the owner is deleted.

### Migration history 🧬

| Migration | Purpose |
| --- | --- |
| `0001_initial` | Enables the pgvector extension and creates the SQLAlchemy metadata tables |
| `0002_instagram_drafts` | Adds the user-owned Instagram draft table and expiration index |

Run migrations explicitly; do not assume creating an RDS instance automatically creates tables or extensions.

### Database connection lifecycle

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#D5DDBD","primaryTextColor":"#252A23","primaryBorderColor":"#354A3B","lineColor":"#76886F","secondaryColor":"#EDF0E6","tertiaryColor":"#F2E4D2","background":"#FBFAF7"}}}%%
flowchart TD
    REQ[Request with DB dependency] --> FACTORY[Get cached SQLAlchemy session factory]
    FACTORY --> ENGINE[Cached SQLAlchemy engine]
    ENGINE --> CONNECT[PostgreSQL connection]
    CONNECT --> SESSION[Create session]
    SESSION --> QUERY[Execute ORM reads and writes]
    QUERY --> SUCCESS{Request succeeded?}
    SUCCESS -->|Yes| COMMIT[Commit transaction]
    SUCCESS -->|No| ROLLBACK[Rollback transaction]
    COMMIT --> CLOSE[Close session]
    ROLLBACK --> CLOSE
```

The engine uses `pool_pre_ping`, a small configurable pool, a maximum overflow, and connection recycling. The ECS connection path requires TLS by default. Local development can disable SSL for a local Docker PostgreSQL instance.

---

## 10. Audio and file storage 🎙️

### Browser storage versus backend storage

There are two distinct audio-storage concepts in the repository:

| Layer | Storage | Purpose |
| --- | --- | --- |
| Browser recorder | IndexedDB | Keeps the user's local recordings in that browser for local playback |
| Backend upload | Private Amazon S3 bucket | Stores uploaded recordings using server-generated object keys |

These are not automatically synchronized.

### Audio upload validation

The backend audio storage module:

- supports WebM, Ogg, MP4/M4A, WAV, MP3, and FLAC declarations;
- checks the actual file header against the declared format;
- rejects empty files;
- rejects files larger than 25 MiB;
- creates server-generated UUID object names;
- stores objects under a date-based anonymous prefix;
- uses S3 server-side encryption;
- does not return object keys or direct object URLs to the browser.

For transcription, the backend downloads the object into a temporary directory, passes it to Faster-Whisper, and removes the temporary local copy when the request exits that directory.

### Audio upload flow

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#D5DDBD","primaryTextColor":"#252A23","primaryBorderColor":"#354A3B","lineColor":"#76886F","secondaryColor":"#EDF0E6","tertiaryColor":"#F2E4D2","background":"#FBFAF7"}}}%%
flowchart TD
    MIC[Browser microphone] --> BLOB[MediaRecorder audio blob]
    BLOB --> API[POST /assistant/audio]
    API --> CHECK[Validate size, MIME type and file signature]
    CHECK -->|Invalid| ERROR[Return safe validation error]
    CHECK -->|Valid| S3[Upload to private S3]
    S3 --> TEMP[Download to temporary working directory]
    TEMP --> WHISPER[Faster-Whisper transcription]
    WHISPER --> CLEAN[Temporary file cleaned up]
    CLEAN --> CHAT[Call shared assistant chat orchestration]
    CHAT --> DB[(Persist message and response)]
    DB --> RESULT[Return transcript and assistant response]
```

### Retention note

The backend notes state that anonymous audio keys do not contain a user-provided identity and that the bucket has no configured lifecycle expiration or versioning. There is no established audio retention period in the code. Before exposing any upload endpoint publicly, enforce verified authentication, abuse protection, and an explicit retention/deletion policy.

---

## 11. AWS architecture ☁️

### AWS services used in the design

The official AWS service icons below make the cloud building blocks easier to scan. Their original AWS colours are preserved, while the surrounding documentation uses ApnaSathi's forest, sage and warm-sand palette.

<table>
<tr>
<td align="center"><img width="54" src="https://raw.githubusercontent.com/icacho-dev/aws-architecture-icons/main/Architecture-Service-Icons_02072025/Arch_Security-Identity-Compliance/48/Arch_Amazon-Cognito_48.svg"/><br/><b>Amazon Cognito</b><br/><sub>Authentication</sub></td>
<td align="center"><img width="54" src="https://raw.githubusercontent.com/icacho-dev/aws-architecture-icons/main/Architecture-Service-Icons_02072025/Arch_Networking-Content-Delivery/48/Arch_Amazon-API-Gateway_48.svg"/><br/><b>API Gateway</b><br/><sub>HTTPS entry</sub></td>
<td align="center"><img width="54" src="https://raw.githubusercontent.com/icacho-dev/aws-architecture-icons/main/Architecture-Service-Icons_02072025/Arch_Networking-Content-Delivery/48/Arch_Elastic-Load-Balancing_48.svg"/><br/><b>Load Balancer</b><br/><sub>Traffic routing</sub></td>
<td align="center"><img width="54" src="https://raw.githubusercontent.com/icacho-dev/aws-architecture-icons/main/Architecture-Service-Icons_02072025/Arch_Networking-Content-Delivery/48/Arch_Amazon-Virtual-Private-Cloud_48.svg"/><br/><b>Amazon VPC</b><br/><sub>Network boundary</sub></td>
</tr>
<tr>
<td align="center"><img width="54" src="https://raw.githubusercontent.com/icacho-dev/aws-architecture-icons/main/Architecture-Service-Icons_02072025/Arch_Containers/48/Arch_Amazon-Elastic-Container-Service_48.svg"/><br/><b>ECS Fargate</b><br/><sub>API runtime</sub></td>
<td align="center"><img width="54" src="https://raw.githubusercontent.com/icacho-dev/aws-architecture-icons/main/Architecture-Service-Icons_02072025/Arch_Database/48/Arch_Amazon-RDS_48.svg"/><br/><b>Amazon RDS</b><br/><sub>PostgreSQL</sub></td>
<td align="center"><img width="54" src="https://raw.githubusercontent.com/icacho-dev/aws-architecture-icons/main/Architecture-Service-Icons_02072025/Arch_Storage/48/Arch_Amazon-Simple-Storage-Service_48.svg"/><br/><b>Amazon S3</b><br/><sub>Audio storage</sub></td>
<td align="center"><img width="54" src="https://raw.githubusercontent.com/icacho-dev/aws-architecture-icons/main/Architecture-Service-Icons_02072025/Arch_Containers/48/Arch_Amazon-Elastic-Container-Registry_48.svg"/><br/><b>Amazon ECR</b><br/><sub>Container images</sub></td>
</tr>
<tr>
<td align="center"><img width="54" src="https://raw.githubusercontent.com/icacho-dev/aws-architecture-icons/main/Architecture-Service-Icons_02072025/Arch_Management-Governance/48/Arch_Amazon-CloudWatch_48.svg"/><br/><b>CloudWatch</b><br/><sub>Logs &amp; metrics</sub></td>
<td align="center"><img width="54" src="https://raw.githubusercontent.com/icacho-dev/aws-architecture-icons/main/Architecture-Service-Icons_02072025/Arch_Security-Identity-Compliance/48/Arch_AWS-Secrets-Manager_48.svg"/><br/><b>Secrets Manager</b><br/><sub>Runtime secrets</sub></td>
<td align="center"><img width="54" src="https://raw.githubusercontent.com/icacho-dev/aws-architecture-icons/main/Architecture-Service-Icons_02072025/Arch_Security-Identity-Compliance/48/Arch_AWS-Identity-and-Access-Management_48.svg"/><br/><b>AWS IAM</b><br/><sub>Least privilege</sub></td>
<td align="center"><img width="54" src="https://raw.githubusercontent.com/icacho-dev/aws-architecture-icons/main/Architecture-Service-Icons_02072025/Arch_Management-Governance/48/Arch_AWS-CloudFormation_48.svg"/><br/><b>CloudFormation</b><br/><sub>CDK deployment</sub></td>
</tr>
</table>



The infrastructure source is under `aws_cloud/` and uses AWS CDK in Python. The current target region is **Asia Pacific (Mumbai), `ap-south-1`**.

### 11.1 Infrastructure stack breakdown 🔹

The CDK app defines four stacks and creates them with cross-stack references:

| Stack | File | Main responsibility |
| --- | --- | --- |
| `ApnaSathiNetworkStack` | `stacks/network_stack.py` | VPC, subnets, route tables, endpoints, and security groups |
| `ApnaSathiDatabaseStack` | `stacks/database_stack.py` | RDS PostgreSQL database and subnet group |
| `ApnaSathiInfrastructureStack` | `stacks/infrastructure_stack.py` | S3 buckets and a REST API Gateway resource |
| `ApnaSathiApplicationStack` | `stacks/application_stack.py` | ECR, ECS Fargate, ALB, task roles, logs, and service |

The stack creation and context validation are in `aws_cloud/app.py`.

### 11.2 Network — VPC, subnets and security 🔹

The network stack defines:

| Resource | Configuration in source |
| --- | --- |
| VPC | `10.20.0.0/16` |
| Public subnet A | `10.20.1.0/24`, `ap-south-1a` |
| Public subnet B | `10.20.2.0/24`, `ap-south-1b` |
| Private subnet A | `10.20.11.0/24`, `ap-south-1a` |
| Private subnet B | `10.20.12.0/24`, `ap-south-1b` |
| Internet Gateway | Attached to the VPC |
| Public route table | Default route to Internet Gateway |
| Private route table | Private workload routing and VPC endpoint routes |
| ALB security group | Allows inbound HTTP port 80 |
| Backend security group | Allows TCP 8000 only from the ALB security group |
| RDS security group | Allows TCP 5432 only from the backend security group |

The ALB sits in public subnets. ECS tasks and RDS are placed in private subnets. The backend security group does not permit arbitrary inbound traffic from the internet.

### Network diagram 🗺️

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#D5DDBD","primaryTextColor":"#252A23","primaryBorderColor":"#354A3B","lineColor":"#76886F","secondaryColor":"#EDF0E6","tertiaryColor":"#F2E4D2","background":"#FBFAF7"}}}%%
flowchart TB
    INTERNET((Internet))
    IGW[Internet Gateway]
    subgraph VPC["VPC 10.20.0.0/16"]
      subgraph AZA["Availability Zone ap-south-1a"]
        PUBA[Public subnet 10.20.1.0/24]
        PRIA[Private subnet 10.20.11.0/24]
      end
      subgraph AZB["Availability Zone ap-south-1b"]
        PUBB[Public subnet 10.20.2.0/24]
        PRIB[Private subnet 10.20.12.0/24]
      end
      ALB[Internet-facing ALB :80]
      ECS[ECS Fargate task :8000]
      RDS[(RDS PostgreSQL :5432)]
      ENDPOINTS[VPC endpoints]
    end
    INTERNET --> IGW
    IGW --> PUBA
    IGW --> PUBB
    PUBA --> ALB
    PUBB --> ALB
    ALB -->|Backend SG allows ALB SG| ECS
    ECS -->|RDS SG allows backend SG| RDS
    ECS --> ENDPOINTS
```

### 11.3 Outbound connectivity 🔹

The CDK supports three egress choices via the `networkEgress` context:

- `none`: the default. No NAT gateway or proxy is created by this setting. S3 and configured AWS service endpoints can still be reached; public third-party HTTPS calls will not work unless another egress path already exists.
- `nat`: creates a development NAT Gateway and EIP in public subnet A and a default route for the private route table. This is a single-AZ development arrangement, not a highly available multi-AZ NAT design.
- `proxy`: expects the address of an already-existing HTTPS forward proxy. The proxy itself is not created by this CDK stack. The task receives `HTTPS_PROXY` and a `NO_PROXY` list for AWS endpoints and task credential metadata.

This choice matters because Vertex AI, Watchmode, and Meta are external services. A private ECS task needs a permitted route to those services. VPC endpoints alone do not provide general internet access.

### 11.4 RDS PostgreSQL 🔹

The database stack defines:

- engine: PostgreSQL;
- engine version in code: `17.12`;
- instance class: `db.t4g.micro`;
- database name: `apnasathi`;
- master username: `apnasathi_admin`;
- AWS-managed master password;
- initial storage: 20 GiB;
- maximum autoscaled storage: 100 GiB;
- storage type: gp3;
- storage encryption: enabled;
- private subnets: both private subnet IDs;
- public accessibility: disabled;
- port: 5432;
- Multi-AZ: disabled;
- backup retention: one day;
- removal policy: snapshot.

The RDS instance is intended to be reachable only from the backend security group. The engine version and pgvector extension availability must be verified in the target AWS region before rollout.

**Important:** CDK provisioning creates the database instance; Alembic creates the application schema. Those are separate operations.

### 11.5 Amazon S3 🔹

The shared infrastructure stack defines two buckets:

- a general ApnaSathi bucket;
- a dedicated audio recordings bucket.

The audio bucket is configured with:

- all public access blocked;
- bucket-owner-enforced object ownership;
- S3-managed server-side encryption;
- HTTPS-only access;
- retain-on-stack-removal behaviour.

The backend task role receives object-level permissions for the `audio/*` prefix. Do not make the audio bucket public to support audio playback; authenticated retrieval should be implemented through an explicit authorization path.

### 11.6 Amazon ECR 🔹

The application stack defines an ECR repository named:

```text
apnasathi-backend
```

It uses:

- immutable tags;
- image scanning on push;
- AES-256 repository encryption;
- retention of the repository when the stack is removed;
- a lifecycle rule for untagged images older than 14 days.

The application workflow tags each built image with the Git commit SHA. This gives each application deployment an immutable image identifier.

### 11.7 Amazon ECS Fargate 🔹

The application stack defines:

- ECS cluster: `apnasathi-dev-cluster`;
- Fargate task family: `apnasathi-backend`;
- Linux ARM64 runtime platform;
- container port: 8000;
- CPU: 512 units;
- memory: 2048 MiB in the current CDK task definition;
- configurable desired task count (default zero);
- a container health check against `/api/v1/health`;
- CloudWatch Logs driver;
- deployment circuit breaker and rollback behaviour in the ECS service definition.

The repository's older backend run notes mention different resource values in one section. The current CDK source is the authority for the infrastructure definition, so re-check the task definition and runtime metrics before sizing production capacity.

### 11.8 Application Load Balancer 🔹

The ALB is internet-facing and lives in public subnets. In the current CDK source it listens on HTTP port 80 and forwards to an IP target group on port 8000.

The target group health-check path is:

```http
GET /api/v1/health
```

The health check verifies that the backend process responds. It does not prove that Vertex AI, S3 uploads, Watchmode, Instagram, or database-backed user workflows are all healthy.

The GitHub application workflow also checks an HTTPS API Gateway gateway URL after publishing. The ALB listener and the gateway are separate infrastructure concepts; follow the deployed route and DNS configuration to understand the actual public request path.

### 11.9 IAM roles and secret delivery 🔹

The application stack creates two ECS roles with different responsibilities.

**Task execution role**

Used by ECS during task startup to:

- pull the image from ECR;
- write logs;
- retrieve configured Secrets Manager values.

It is not the application runtime identity.

**Task role**

Used by code inside the running container to call AWS APIs. The current policy grants the backend access to the audio object prefix in S3. It is also the AWS identity used by the Google Workload Identity Federation integration.

**Secrets Manager values may include:**

- RDS master credentials;
- Google Workload Identity Federation configuration;
- Watchmode API key;
- Instagram application secret.

Secret values are injected into the ECS task definition using secret references. Keep the actual values out of GitHub source, Docker build arguments, and frontend variables.

### 11.10 Google Workload Identity Federation 🔹

The backend calls Vertex AI, but the runtime is in AWS. The deployment notes document a cross-cloud identity design:

1. ECS obtains temporary credentials from its task role.
2. Google Workload Identity Federation trusts the specific AWS role.
3. The external-account credential configuration is stored in AWS Secrets Manager.
4. ECS injects the federation configuration into the container.
5. Google authentication exchanges the AWS identity for a short-lived Google identity.
6. The backend uses that identity to call Vertex AI.

This avoids putting a permanent Google service-account key inside the image or repository.

The CDK and deployment notes require the Google project, WIF secret ARN, and appropriate IAM bindings to be configured. A project ID alone does not authenticate the ECS task.

### 11.11 AWS component interaction diagram 🔹

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#D5DDBD","primaryTextColor":"#252A23","primaryBorderColor":"#354A3B","lineColor":"#76886F","secondaryColor":"#EDF0E6","tertiaryColor":"#F2E4D2","background":"#FBFAF7"}}}%%
flowchart LR
    GHA[GitHub Actions]
    OIDC[GitHub OIDC identity token]
    IAM[AWS IAM deployment role]
    CDK[AWS CDK / CloudFormation]
    ECR[(Amazon ECR)]
    ECS[ECS Fargate service]
    ALB[Application Load Balancer]
    RDS[(RDS PostgreSQL)]
    S3[(S3 audio bucket)]
    SM[AWS Secrets Manager]
    CW[CloudWatch Logs]
    WIF[Google Workload Identity Federation]
    VERTEX[Vertex AI]
    GHA --> OIDC --> IAM --> CDK
    CDK --> ECR
    CDK --> ECS
    CDK --> ALB
    CDK --> RDS
    CDK --> S3
    ECS --> RDS
    ECS --> S3
    ECS --> SM
    ECS --> CW
    ECS -->|Task role identity| WIF --> VERTEX
    ALB --> ECS
```

---

## 12. Docker and container design 🐳

### Dockerfile stages and decisions

The repository has a single runtime image defined in `Dockerfile`.

The build:

1. copies the `uv` executable from the official Astral uv image;
2. starts from Python 3.13 slim Bookworm;
3. sets the application working directory and Python/uv environment settings;
4. copies `pyproject.toml` and `uv.lock`;
5. synchronizes locked runtime dependencies without development dependencies;
6. installs the backend-specific requirements;
7. downloads and caches the Faster-Whisper base model inside the image;
8. copies the backend source;
9. warms the multilingual embedding model cache;
10. changes to the non-root user `10001:10001`;
11. exposes port 8000;
12. starts Uvicorn.

The model caches are included so the container does not need to download Whisper or the configured E5 model during normal startup. Confirm that the build environment can access the model source when creating a new image.

### Why ARM64?

The CDK task definition uses the Linux ARM64 runtime platform. The application workflow builds with:

```bash
docker buildx build --platform linux/arm64
```

It also inspects the image architecture and requires `linux/arm64` before pushing it.

An AMD64-only local image is not a valid substitute for the ARM64 ECS image.

### Local PostgreSQL with Docker Compose

`docker-compose.yml` defines a local pgvector-enabled PostgreSQL container for development/QA:

- image: `pgvector/pgvector:pg16`;
- database: `apnasathi_qa`;
- user: `apnasathi`;
- host port: `55432`, bound to localhost only;
- health check: `pg_isready`.

The password in this compose file is for local QA only. Never reuse it in AWS or a shared environment.

---

## 13. GitHub Actions and YAML pipelines 🚀

There are three workflow files:

| File | Workflow | Purpose |
| --- | --- | --- |
| `.github/workflows/bootstrap.yaml` | Ensure ApnaSathi CDK Bootstrap | Checks whether the CDKToolkit stack exists and bootstraps only when needed |
| `.github/workflows/deploy-infrastructure.yaml` | Deploy ApnaSathi Infrastructure | Synthesizes and deploys the four CDK stacks |
| `.github/workflows/deploy.yaml` | Deploy ApnaSathi Application | Builds the frontend and ARM64 backend image, pushes ECR, deploys ECS, publishes frontend assets, and checks the gateway |

The deployment workflows use `workflow_dispatch`, so they are manually started from GitHub Actions. They use a shared concurrency group to prevent overlapping ECS deployments.

### 13.1 GitHub OIDC — why it is used 🔹

The workflows request:

```yaml
permissions:
  contents: read
  id-token: write
```

The `id-token: write` permission lets GitHub Actions request a GitHub-issued OIDC token. The AWS credentials action exchanges that token with AWS STS to assume the configured IAM role.

This avoids saving a long-lived AWS access key and secret key in GitHub repository secrets.

The repository includes:

- `github-oidc-trust-policy.json`;
- `github-deploy-permissions.json`.

The trust policy should restrict who can assume the role to the expected repository and branch/environment subject. The permissions policy should grant only the actions needed for the relevant deployment job.

### 13.2 Bootstrap workflow 🔹

The reusable `bootstrap.yaml` workflow:

1. requires the run to be from `main`;
2. checks that the infrastructure-check role and deployment role are consistent;
3. assumes the infrastructure role using GitHub OIDC;
4. checks the AWS account ID;
5. checks whether `CDKToolkit` already exists;
6. if it is missing, requires a separate authorized bootstrap role;
7. bootstraps the target AWS account and region with the pinned CDK CLI.

It deliberately does not use the ordinary deployment role to create the initial bootstrap resources.

### 13.3 Infrastructure deployment workflow 🔹

The infrastructure workflow runs the bootstrap workflow first. It then:

1. checks out the repository;
2. assumes the infrastructure IAM role using OIDC;
3. installs Node.js and Python;
4. installs dependencies from `aws_cloud/requirements.txt`;
5. validates the AWS account;
6. requires explicit baseline image tag and desired task count values;
7. reads GitHub variables for optional Google, Cognito, egress, Watchmode, and Instagram configuration;
8. builds the CDK context arguments;
9. runs CDK synthesis;
10. deploys all four stacks.

The default network egress mode in the workflow is `none`. NAT or proxy should be selected only after the related cost, routing, and security choices have been reviewed.

### 13.4 Application deployment workflow 🔹

The application workflow also starts with the bootstrap check. Its deployment job then:

1. assumes the backend deployment IAM role through OIDC;
2. confirms the target AWS account;
3. downloads the current ECS task definition;
4. checks that the task family is `apnasathi-backend`, the runtime is ARM64, and expected secret/environment entries exist;
5. builds the React frontend using `npm ci` and `npm run build`;
6. configures QEMU and Docker Buildx;
7. logs in to ECR;
8. builds the backend image for Linux ARM64;
9. starts the image in an isolated network for a health-check smoke test;
10. pushes the image tagged with the Git commit SHA;
11. creates a new ECS task definition revision with the new immutable image tag;
12. updates the ECS service;
13. waits for ECS service stability and checks that the expected task revision is active;
14. synchronizes frontend assets to the configured S3 website bucket;
15. checks the development HTTPS API gateway and compares the returned index page with the built frontend.

This pipeline is a manual release workflow. A successful container health check is a startup test, not a complete integration test of all third-party services.

### CI/CD diagram 🚦

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#D5DDBD","primaryTextColor":"#252A23","primaryBorderColor":"#354A3B","lineColor":"#76886F","secondaryColor":"#EDF0E6","tertiaryColor":"#F2E4D2","background":"#FBFAF7"}}}%%
flowchart TD
    START[Maintainer starts workflow_dispatch]
    BOOT[Reusable bootstrap workflow]
    CHECK[Assume infrastructure role with OIDC]
    EXISTS{CDKToolkit exists?}
    BOOTSTRAP[Assume separate bootstrap role and run CDK bootstrap]
    INFRA[Infrastructure deployment workflow]
    APP[Application deployment workflow]
    SYNTH[CDK synth and deploy all stacks]
    BUILD[Build React frontend]
    IMAGE[Build ARM64 Docker image]
    SMOKE[Run container health smoke test]
    PUSH[Push commit-SHA image to ECR]
    ECS[Register task revision and update ECS]
    STABLE[Wait for stable service and verify revision]
    SITE[Sync frontend assets to S3]
    GATEWAY[Check HTTPS gateway]
    START --> BOOT --> CHECK --> EXISTS
    EXISTS -->|No| BOOTSTRAP
    EXISTS -->|Yes| INFRA
    BOOTSTRAP --> INFRA
    INFRA --> SYNTH
    BOOT --> APP
    APP --> BUILD --> IMAGE --> SMOKE --> PUSH --> ECS --> STABLE --> SITE --> GATEWAY
```

The infrastructure and application workflows are launched separately. The diagram shows their shared bootstrap dependency; it should not be read as one workflow automatically running both deployments in sequence.

### 13.5 Important YAML terms 🔹

| YAML element | Meaning in these workflows |
| --- | --- |
| `name` | Human-readable workflow name |
| `on: workflow_dispatch` | Manual run trigger |
| `permissions` | Token permissions requested by the workflow |
| `env` | Environment variables shared by jobs or steps |
| `jobs` | Independent or dependent workflow jobs |
| `needs` | Job dependency |
| `uses` | Reusable workflow or third-party action |
| `with` | Inputs passed to an action |
| `if` | Conditional execution |
| `run` | Shell commands executed by the runner |
| `vars.*` | GitHub Actions repository or environment variables |
| `secrets.*` | Encrypted GitHub secrets (not the same as AWS Secrets Manager) |
| `GITHUB_OUTPUT` | Mechanism for a step to publish outputs to later steps |

### 13.6 GitHub variables to configure 🔹

The checked-in workflow reads these variable names. Configure only the values needed for the environment and check the workflow before changing their meaning.

| Variable | Purpose |
| --- | --- |
| `AWS_ROLE_ARN` | Application deployment role |
| `INFRASTRUCTURE_ROLE_ARN` | Infrastructure role and bootstrap check role |
| `BOOTSTRAP_ROLE_ARN` | Separate initial CDK bootstrap role when required |
| `BACKEND_IMAGE_TAG` | Baseline image tag used by infrastructure deployment |
| `BACKEND_DESIRED_COUNT` | Baseline ECS desired task count |
| `COGNITO_USER_POOL_ID` | Cognito user pool identifier |
| `COGNITO_CLIENT_ID` | Cognito public application client identifier |
| `GOOGLE_CLOUD_PROJECT` | Google Cloud project for Vertex AI |
| `GOOGLE_CLOUD_LOCATION` | Vertex AI location (defaults to global) |
| `GOOGLE_WIF_SECRET_ARN` | AWS Secrets Manager ARN containing WIF config |
| `NETWORK_EGRESS` | `none`, `nat`, or `proxy` |
| `BACKEND_HTTPS_PROXY` | Existing HTTPS forward proxy address for proxy mode |
| `WATCHMODE_SECRET_ARN` | Secrets Manager ARN for Watchmode API key |
| `INSTAGRAM_SECRET_ARN` | Secrets Manager ARN for Instagram app secret |
| `INSTAGRAM_SECRET_JSON_KEY` | Optional JSON key selection inside the secret |
| `INSTAGRAM_API_VERSION` | Meta Graph API version |
| `INSTAGRAM_IMAGE_ORIGIN` | Public HTTPS image origin used by Instagram media publishing |
| `FRONTEND_SITE_BUCKET` | S3 bucket receiving frontend build output |

Some workflows also provide development defaults for the Cognito IDs and frontend site-bucket name. Replace those defaults with deliberate environment values before using the pipeline for another account or environment.

---

## 14. Local development 💻

### Prerequisites 📋

Install:

- Git;
- Python 3.13;
- uv;
- Node.js 22 or a compatible current Node.js release;
- npm;
- Docker Desktop (for local PostgreSQL or container testing);
- Google Cloud CLI and a Google project with Vertex AI access, if testing Gemini;
- AWS CLI configured with an authorized profile, if testing S3;
- an Amazon Cognito User Pool and public app client for authenticated flows.

### Clone the repository

```bash
git clone https://github.com/SwekcchaCornicle/apnasathi-ai.git
cd apnasathi-ai
```

### Install Python dependencies

```bash
uv sync
uv pip install -r backend/requirements.txt
```

The project lock file is `uv.lock`. Use the lock file when preparing a reproducible local environment.

### Start local PostgreSQL

From the repository root:

```bash
docker compose up -d postgres
docker compose ps
```

The local PostgreSQL service is exposed on `127.0.0.1:55432`.

### Configure backend environment

Copy the example file and update the local values:

```bash
# macOS / Linux
cp backend/.env.example backend/.env
```

For Windows CMD:

```cmd
copy backend\.env.example backend\.env
```

Set a local database URL that matches the Compose port and database credentials. For example:

```dotenv
DATABASE_URL=postgresql+psycopg://apnasathi:local-qa-only@localhost:55432/apnasathi_qa
DB_SSL=false
COGNITO_REGION=ap-south-1
COGNITO_USER_POOL_ID=YOUR_USER_POOL_ID
COGNITO_CLIENT_ID=YOUR_PUBLIC_APP_CLIENT_ID
```

The exact database/user values must match the local PostgreSQL container configuration.

### Run database migrations

```bash
uv run --no-sync alembic -c backend/alembic.ini upgrade head
```

The initial migration enables pgvector and creates the SQLAlchemy metadata tables. The following migration creates the Instagram draft table.

### Configure Google authentication for local development

The deployment documentation recommends Google Application Default Credentials for local development. After you have configured an authorized Google Cloud account:

```bash
gcloud auth application-default login
```

Set the relevant values:

```dotenv
GOOGLE_CLOUD_PROJECT=YOUR_GOOGLE_PROJECT_ID
GOOGLE_CLOUD_LOCATION=global
```

The project ID tells the SDK which Google Cloud project to use; it does not itself grant authentication or Vertex AI permissions.

### Configure AWS audio storage (optional)

The audio endpoint requires a bucket and an AWS identity that can access it.

```dotenv
AUDIO_S3_BUCKET=YOUR_PRIVATE_AUDIO_BUCKET
AWS_REGION=ap-south-1
AWS_PROFILE=YOUR_AWS_PROFILE
```

Use the standard AWS credential provider chain locally. Do not store AWS access keys in the repository's `.env` file. In ECS, use the configured task role instead of a developer profile.

### Start the backend

From the repository root:

```bash
uv run python -m uvicorn app:app --app-dir backend --reload --port 8000
```

The backend health endpoint is:

```http
GET http://localhost:8000/api/v1/health
```

### Configure and start the frontend

Create the local frontend environment file:

```bash
# macOS / Linux
cp frontend/.env.example frontend/.env.local
```

For Windows CMD:

```cmd
copy frontend\.env.example frontend\.env.local
```

Configure:

```dotenv
VITE_COGNITO_REGION=ap-south-1
VITE_COGNITO_USER_POOL_ID=YOUR_USER_POOL_ID
VITE_COGNITO_CLIENT_ID=YOUR_PUBLIC_APP_CLIENT_ID
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Then start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

Open the local Vite URL printed by the development server.

### Run the backend using Docker

Build the image from the repository root:

```bash
docker build --platform linux/arm64 -t apnasathi-backend:local .
```

Run it with the required runtime configuration supplied through your local environment. For example:

```bash
docker run --rm --platform linux/arm64 -p 127.0.0.1:8000:8000 \
  -e GOOGLE_CLOUD_PROJECT=YOUR_GOOGLE_PROJECT_ID \
  apnasathi-backend:local
```

The Dockerfile starts Uvicorn on port 8000. The full authenticated workflow also requires database, Cognito, Vertex, and optional integration configuration.

---

## 15. Configuration reference 🔧

Configuration is separated by runtime boundary.

### Frontend build-time variables

| Variable | Description |
| --- | --- |
| `VITE_API_BASE_URL` | API base URL used by browser requests |
| `VITE_COGNITO_REGION` | AWS region containing the Cognito User Pool |
| `VITE_COGNITO_USER_POOL_ID` | Cognito User Pool identifier |
| `VITE_COGNITO_CLIENT_ID` | Public Cognito app client identifier |

Anything prefixed with `VITE_` is bundled into frontend assets. Never place secret keys, passwords, private tokens, or server-side API credentials in a Vite variable.

### Backend environment variables

| Variable | Description |
| --- | --- |
| `DATABASE_URL` | Optional complete SQLAlchemy database URL |
| `DB_HOST` | RDS or local PostgreSQL host |
| `DB_PORT` | Database port; defaults to 5432 |
| `DB_NAME` | Database name |
| `DB_USER`, `DB_PASSWORD` | Optional direct local credentials |
| `DATABASE_CREDENTIALS` | JSON database secret injected by ECS |
| `DB_SSL` | Database TLS requirement; defaults to true |
| `DB_POOL_SIZE` | SQLAlchemy pool size; defaults to 3 |
| `DB_MAX_OVERFLOW` | Pool overflow; defaults to 2 |
| `COGNITO_REGION` | Cognito region |
| `COGNITO_USER_POOL_ID` | User Pool used to validate tokens |
| `COGNITO_CLIENT_ID` | Audience/app-client ID expected in tokens |
| `GOOGLE_CLOUD_PROJECT` | Google Cloud project |
| `GOOGLE_CLOUD_LOCATION` | Vertex AI location |
| `GOOGLE_WIF_CONFIG_JSON` | External-account WIF JSON injected in ECS |
| `AUDIO_S3_BUCKET` | Private S3 audio bucket |
| `AWS_REGION` | AWS region for SDK requests |
| `WATCHMODE_API_KEY` | Watchmode API credential |
| `INSTAGRAM_APP_SECRET` | Meta application secret |
| `INSTAGRAM_API_VERSION` | Meta Graph API version |
| `INSTAGRAM_IMAGE_ORIGIN` | Public HTTPS origin for the Instagram image workflow |
| `HTTPS_PROXY` | Optional external HTTPS proxy |
| `NO_PROXY` | Destinations that bypass the proxy |
| `EMBEDDING_MODEL` | Optional embedding model override |
| `FASTEMBED_CACHE_PATH` | Local embedding model cache path |
| `ANSWER_CACHE_SIMILARITY_THRESHOLD` | Similarity threshold; defaults to 0.88 |
| `ENABLE_SHARED_KNOWLEDGE` | Whether eligible shared knowledge can be considered |

Do not commit real environment files. Keep secrets in a secret manager and grant each runtime only the access it needs.

---

## 16. Tests and validation 🧪

The repository has separate test areas for backend behaviour, infrastructure helpers, and browser interaction.

### Backend tests

Run:

```bash
uv run --no-sync python -m unittest discover -s backend/tests -v
```

The current backend test files cover areas including:

- assistant intent routing;
- audio workflow;
- database configuration;
- language policy;
- local question/answer behaviour;
- S3 audio storage;
- semantic retrieval;
- Vertex authentication.

### Infrastructure tests

Install the CDK dependencies and run:

```bash
uv pip install -r aws_cloud/requirements.txt
uv run --no-sync python -m unittest discover -s aws_cloud/tests -v
```

### Frontend build

```bash
cd frontend
npm ci
npm run build
```

### Container smoke test

Build an ARM64 image:

```bash
docker build --platform linux/arm64 -t apnasathi-backend:local .
```

Confirm its architecture:

```bash
docker image inspect apnasathi-backend:local --format '{{.Os}}/{{.Architecture}}'
```

Expected output:

```text
linux/arm64
```

The deployment workflow also runs the container with networking disabled and checks the backend health endpoint before it pushes the image.

### CDK synthesis

From the `aws_cloud` directory, synthesize the infrastructure using the repository's CDK app and configured environment:

```bash
npx --yes aws-cdk@2.1149.0 synth --no-lookups
```

Use the same context values intended for deployment. A successful synthesis confirms that CDK can generate a CloudFormation template; it does not mean AWS resources have been created.

### Integration validation checklist ✅

Before calling a release ready, test more than the health endpoint:

- [ ] Cognito sign-up, confirmation, sign-in, and password reset.
- [ ] Backend JWT signature, issuer, audience, token-use, expiry, and email checks.
- [ ] User A cannot read or update User B's conversation, message, search history, memory, or draft.
- [ ] Text chat and conversation history.
- [ ] Hindi and English response-language behaviour.
- [ ] Microphone permission, valid audio upload, invalid file rejection, and transcription.
- [ ] S3 upload using the task role.
- [ ] Database migrations on the exact target PostgreSQL engine.
- [ ] pgvector extension and embedding dimensions.
- [ ] Semantic retrieval threshold, tenant isolation, and cache-miss fallback.
- [ ] Shopping flow state transitions and cancellation.
- [ ] Watchmode lookup, region filtering, and safe playback URLs.
- [ ] Instagram OAuth state validation, callback, draft expiry, and user confirmation.
- [ ] Vertex AI authentication using the ECS task role and WIF.
- [ ] ECS task health, logs, service stability, and rollback behaviour.
- [ ] External egress route to each enabled integration.

---

## 17. Security and operational considerations 🛡️

### Authentication and authorization

- Verify Cognito tokens on the backend; do not trust a user ID supplied by the browser.
- Keep user ownership filters in every private-data query.
- Ensure every message and conversation is associated with the authenticated user.
- Keep Meta and Watchmode credentials server-side.
- Use short-lived identity tokens and rotate/revoke credentials according to provider guidance.

### AWS permissions

- Use GitHub OIDC rather than permanent AWS keys in GitHub.
- Keep the bootstrap role separate from deployment roles.
- Keep the ECS task execution role separate from the task role.
- Restrict the task role to the S3 object prefix it needs.
- Keep RDS in private subnets.
- Restrict PostgreSQL ingress to the backend security group.
- Keep S3 Block Public Access enabled for audio files.
- Use Secrets Manager for server-side secrets.

### Audio privacy

The current audio object key includes an `anonymous` prefix because the storage helper does not assign the uploaded object to a user identity. The authenticated assistant audio path and the anonymous object-key design are therefore separate concerns.

Before using audio storage for account-level playback or long-term retention, add server-side ownership metadata, authorize every read, define retention and deletion, and consider the privacy implications of storing voice recordings.

### External service availability

Vertex, Meta, Watchmode, and retailer websites can fail independently of the backend. Handle timeouts and provider errors as recoverable failures and avoid logging API keys, access tokens, full secret payloads, or sensitive user prompts.

### Production hardening still required

The current CDK source is development-oriented in several places (for example, single NAT egress when selected, non-Multi-AZ RDS, HTTP ALB listener, and zero ECS tasks by default). Review TLS termination, multi-AZ availability, backups, deletion protection, scaling, rate limiting, monitoring, WAF controls, and data-retention policy before a public production launch.

---

## 18. Current implementation boundaries 📌

This section is intentionally explicit. It separates what is visible in source code from assumptions that would need deployment or integration evidence.

### Implemented in application source

- React language and account screens.
- Cognito sign-up, verification, SRP sign-in, password reset, and backend token verification.
- Authenticated text chat and voice chat endpoint.
- FastAPI intent classification through Gemini on Vertex AI.
- Shopping state machine and retailer search link generation.
- Watchmode title/source lookup and deterministic playback troubleshooting.
- Instagram draft/OAuth/publish integration code.
- Faster-Whisper transcription.
- Piper speech generation.
- SQLAlchemy models and Alembic migrations.
- S3 audio storage helper with file validation.
- Multilingual E5 embedding helper and pgvector answer-reuse service.
- CDK infrastructure definitions and GitHub Actions deployment workflows.

### Defined in infrastructure code, but must be verified in the target AWS account

- VPC, subnets, security groups, route tables, and endpoints.
- RDS PostgreSQL instance and secret.
- S3 buckets.
- ECR repository.
- ECS cluster, Fargate task definition, service, and ALB.
- IAM roles, log group, and configured secret references.
- Optional NAT or proxy configuration.

A CDK construct describes desired infrastructure. Use CloudFormation stack outputs, ECS service state, RDS connectivity checks, and S3/CloudWatch evidence to establish whether the deployed environment matches it.

### Important caveats from the repository

1. **Database readiness:** RDS provisioning, environment injection, SQLAlchemy models, and migrations are separate steps. Confirm that the exact deployed RDS instance supports the required PostgreSQL version and pgvector extension, then apply Alembic migrations.
2. **Semantic cache readiness:** the repository has the E5 model, pgvector field, lookup service, and assistant call path. Run the database-backed integration tests against a migrated PostgreSQL instance to prove embedding generation, insert, cosine search, threshold handling, and tenant isolation together.
3. **Audio ownership:** the S3 helper writes anonymous UUID keys. It does not currently establish a durable user-to-object ownership relationship for account playback.
4. **Audio retention:** no object expiry policy is configured in the documented bucket setup. Decide how long recordings should be retained and implement deletion/lifecycle controls.
5. **Internet egress:** the default CDK egress mode is `none`. Third-party HTTPS integrations need an approved NAT or proxy route.
6. **ALB TLS:** the current CDK listener is HTTP on port 80. The application workflow separately checks an HTTPS API Gateway URL. Verify the actual TLS termination and gateway-to-backend path before assuming the ALB itself terminates HTTPS.
7. **Instagram hosting:** the Instagram workflow needs a publicly reachable HTTPS image origin for the Meta media-container API. The private audio bucket is not a substitute for that public image origin.
8. **Health check scope:** `/api/v1/health` verifies process availability, not all dependencies or business workflows.
9. **Task sizing:** the CDK currently defines ARM64 Fargate with 512 CPU units and 2048 MiB memory. Measure model loading, transcription, embedding inference, and peak memory under representative requests.
10. **Public access and abuse control:** require verified authentication and rate limiting for any publicly exposed upload/action endpoint.

### What the application does not claim

- It does not autonomously complete retailer payments.
- It does not bypass account authorization on Instagram or other services.
- It does not have unrestricted control of the user's phone or desktop.
- It does not infer that an AWS resource is live just because it exists in CDK.
- It does not guarantee every language is supported; the current backend policy accepts English and Hindi.

---

## 19. Repository layout 🗂️

A simplified repository map:

```text
apnasathi-ai/
│
├── .github/
│   └── workflows/
│       ├── bootstrap.yaml
│       ├── deploy-infrastructure.yaml
│       └── deploy.yaml
│
├── aws_cloud/
│   ├── app.py
│   ├── cdk.json
│   ├── requirements.txt
│   ├── stacks/
│   │   ├── network_stack.py
│   │   ├── database_stack.py
│   │   ├── infrastructure_stack.py
│   │   └── application_stack.py
│   └── tests/
│
├── backend/
│   ├── agents/
│   │   ├── greeting.py
│   │   ├── shoaping.py
│   │   ├── social_media.py
│   │   ├── speech.py
│   │   └── watch_show/
│   │       ├── watch_show.py
│   │       └── troubleshoot.py
│   ├── api/
│   │   ├── assistant.py
│   │   ├── auth.py
│   │   ├── knowledge.py
│   │   └── persistence.py
│   ├── auth/
│   │   ├── cognito.py
│   │   └── dependencies.py
│   ├── database/
│   │   ├── base.py
│   │   ├── models.py
│   │   └── session.py
│   ├── embeddings/
│   │   └── e5.py
│   ├── llm_model/
│   │   ├── classify_intent_action.py
│   │   ├── intent_classifier.py
│   │   ├── llm_model.py
│   │   ├── prompt.py
│   │   └── vertex_auth.py
│   ├── migrations/
│   │   └── versions/
│   │       ├── 0001_initial_persistence.py
│   │       └── 0002_instagram_drafts.py
│   ├── services/
│   │   ├── answer_reuse.py
│   │   └── conversation_memory.py
│   ├── storage/
│   │   └── s3_audio_storage.py
│   ├── tests/
│   ├── voices/
│   ├── app.py
│   ├── alembic.ini
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── AudioRecorder.jsx
│   │   ├── ChatWorkspace.jsx
│   │   ├── InstagramDraft.jsx
│   │   ├── audioStorage.js
│   │   ├── cognito.js
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── tests/
│   ├── package.json
│   └── vite.config.js
│
├── docs/
│   ├── aws-deployment.md
│   ├── LOCAL_QA_CHECKLIST.md
│   ├── architecture.md
│   ├── api-contract.md
│   └── setup-guide.md
│
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
├── github-deploy-permissions.json
└── github-oidc-trust-policy.json
```

---

## Final note 💚

ApnaSathi is built around a simple idea: **technology should adapt to the way people communicate, not the other way around.**

The frontend makes the experience conversational. The backend turns requests into structured workflows. The AI layer helps understand what the user means. The database is designed to keep conversations and knowledge scoped to an account. AWS provides the infrastructure to run and deploy the system.

The most important engineering principle in this project is the separation of responsibilities: the LLM interprets, application code validates and acts, authentication identifies the user, the database stores the state, and cloud infrastructure runs the services.

For implementation details, start with `backend/api/assistant.py`, `backend/llm_model/`, `backend/database/models.py`, `aws_cloud/app.py`, and the three GitHub Actions workflows.
