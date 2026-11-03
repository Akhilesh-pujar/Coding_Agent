# APEX – Local AI API Gateway

**APEX API Gateway** is a production-grade, modular, local-first API gateway and routing layer built with FastAPI, HTTPX, and SQLAlchemy 2.x for locally hosted Ollama AI models.

It provides a unified OpenAI-compatible interface, intelligent task-based model routing between `apex-fast` (7B) and `apex-pro` (14B), streaming and non-streaming completions, performance and audit logging, and connectivity for MCP agents, IDEs, and local developer tooling.

---

## Architecture Overview

```
                      +-------------------------------------------------+
                      |              Client Applications                |
                      | (Web Portal, Antigravity, VS Code, MCP, cURL)   |
                      +-------------------------------------------------+
                                               |
                                               | (JWT Bearer / API Key + HTTP / SSE)
                                               v
                      +-------------------------------------------------+
                      |           APEX API Gateway (FastAPI)            |
                      |                                                 |
                      |   / (Developer Portal)   /health   /api/route   |
                      |   /v1/auth/*    /v1/rooms/*     /v1/models     |
                      |   /v1/chat/completions   /v1/completions        |
                      +-------------------------------------------------+
                                       |                 |
                    +------------------+                 +----------------+
                    | (Intelligent Model Router)                          | (Async DB Engine)
                    v                                                     v
       +-------------------------+                           +-------------------------+
       |  Model Router & Heuristic|                          |  Storage & Audit DB     |
       |  - Fast: 7B (Docs/Simple) |                         |  (SQLite / PostgreSQL)  |
       |  - Pro: 14B (Architecture)|                         |  Users, Keys, Rooms,    |
       +-------------------------+                           |  Messages, RequestLogs  |
                    |                                        +-------------------------+
                    v
       +-------------------------------------------------+
       |                 Ollama Client                   |
       |         Async HTTP Connection Pool              |
       +-------------------------------------------------+
                    |
                    v
       +-------------------------------------------------+
       |       Local Ollama Engine (127.0.0.1:11434)      |
       |   - apex-fast:latest (Qwen 2.5 Coder 7B)        |
       |   - apex-pro:latest  (Qwen 2.5 Coder 14B)       |
       +-------------------------------------------------+
```

### Module Organization

```
apex-gateway/
├── app/
│   ├── main.py              # Application factory, lifespan, error handling, CORS, static mount
│   ├── config.py            # Type-safe settings with Pydantic BaseSettings & DB validator
│   ├── dependencies.py      # Tri-layer auth (JWT + API key + Master key) & DB session providers
│   ├── api/
│   │   ├── health.py        # Gateway & Ollama health monitoring (/health)
│   │   ├── auth.py          # User registration, login, personal API keys (/v1/auth/*)
│   │   ├── rooms.py         # Persistent multi-room chat & history (/v1/rooms/*)
│   │   ├── models.py        # OpenAI-compatible model discovery (/v1/models)
│   │   ├── chat.py          # OpenAI-compatible completions (/v1/chat/completions)
│   │   └── routing.py       # Heuristic routing diagnostics (/api/route)
│   ├── core/
│   │   ├── security.py      # Password hashing (bcrypt) & JWT token signing (PyJWT)
│   │   ├── ollama_client.py # Async HTTPX client with connection pooling
│   │   ├── model_registry.py# Real-time model verification against Ollama (30s TTL cache)
│   │   ├── model_router.py  # Intent & complexity analyzer (Fast vs Pro)
│   │   ├── authentication.py# Auth re-exports & key validation
│   │   └── logging_config.py# Structured logging & credential sanitization
│   ├── schemas/
│   │   ├── auth.py          # Registration, login, token, and API key schemas
│   │   ├── rooms.py         # Room creation, summary, detail, and room chat schemas
│   │   ├── chat.py          # OpenAI Pydantic schemas (stream & non-stream)
│   │   └── models.py        # Model list & routing schemas
│   ├── services/
│   │   ├── room_service.py  # Room management & sliding-window context history
│   │   ├── chat_service.py  # Request lifecycle, SSE formatting, token tracking
│   │   └── routing_service.py # Routing evaluation orchestrator
│   └── database/
│       ├── connection.py    # Async SQLAlchemy 2.x session engine (SQLite/PostgreSQL)
│       └── models.py        # User, UserApiKey, ChatRoom, ChatMessage, RequestLog
├── static/
│   └── index.html           # Dark-themed Web Developer Portal (Auth, Keys, VS Code setup)
├── tests/
│   ├── test_auth.py         # User registration, JWT login, API key lifecycle
│   ├── test_rooms.py        # Chat room persistence, sliding context, isolation
│   ├── test_health.py       # Health checks and offline tests
│   ├── test_models.py       # Model discovery and auth tests
│   ├── test_chat.py         # Streaming, non-streaming, timeouts, errors
│   └── test_routing.py      # Heuristic routing and user override tests
├── logs/                    # Rotating log files (apex_gateway.log)
├── mcp_server.py            # Model Context Protocol stdio server for Antigravity & IDEs
├── .env.example             # Template environment variables
├── .env                     # Local configuration
├── run.py                   # CLI entrypoint
├── requirements.txt         # Production dependencies
└── README.md
```

---

## Requirements & Windows Setup

### Prerequisites
- Windows 10/11 64-bit
- Python 3.13+
- [Ollama](https://ollama.com/) running locally on `http://127.0.0.1:11434`
- Installed Ollama models:
  - `apex-fast:latest` (Qwen 2.5 Coder 7B)
  - `apex-pro:latest` (Qwen 2.5 Coder 14B Q4_K_M)

### 1. Virtual Environment Setup

In PowerShell from the project root:

```powershell
# Set execution policy if not already enabled
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Create virtual environment if needed
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
.\.venv\Scripts\pip.exe install -r apex-gateway\requirements.txt
```

### 3. Environment Configuration

Copy `.env.example` to `.env` inside `apex-gateway/` (or update existing):

```powershell
cp apex-gateway\.env.example apex-gateway\.env
```

Default configuration in `.env`:

```env
OLLAMA_BASE_URL=http://localhost:11434
APEX_HOST=127.0.0.1
APEX_PORT=8000
APEX_API_KEY=apex-secret-key-12345
APEX_DEFAULT_MODEL=apex-fast:latest
APEX_PRO_MODEL=apex-pro:latest
APEX_FAST_MODEL=apex-fast:latest
APEX_REQUEST_TIMEOUT=300
APEX_LOG_LEVEL=INFO
APEX_DATABASE_URL=sqlite+aiosqlite:///./apex.db
```

---

## Starting the Gateway

Run the gateway launcher script:

```powershell
.\.venv\Scripts\python.exe apex-gateway\run.py
```

Or run via Uvicorn directly:

```powershell
cd apex-gateway
..\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```

Once started:
- **Interactive OpenAPI Documentation (Swagger)**: `http://127.0.0.1:8000/docs`
- **ReDoc API Spec**: `http://127.0.0.1:8000/redoc`
- **Health Check**: `http://127.0.0.1:8000/health`

---

## API Endpoints & Usage Examples

All protected endpoints require either:
- `Authorization: Bearer <APEX_API_KEY>` header, or
- `x-api-key: <APEX_API_KEY>` header.

### 1. Health Monitoring (`GET /health`)

Inspect status of the gateway, Ollama connectivity, and verified installed models:

```bash
curl -X GET http://127.0.0.1:8000/health
```

**Example Response:**
```json
{
  "gateway_status": "healthy",
  "gateway_version": "1.0.0",
  "ollama_connectivity": {
    "connected": true,
    "base_url": "http://localhost:11434",
    "version": "0.40.13",
    "error": null
  },
  "model_status": {
    "apex_fast_model": "apex-fast:latest",
    "apex_fast_verified": true,
    "apex_pro_model": "apex-pro:latest",
    "apex_pro_verified": true,
    "installed_models_count": 4,
    "installed_models": [
      "apex-pro:latest",
      "apex-fast:latest",
      "qwen2.5-coder:14b-instruct-q4_K_M",
      "qwen2.5-coder:latest"
    ]
  }
}
```

---

### 2. Model Discovery (`GET /v1/models`)

Returns models verified live against Ollama in standard OpenAI format:

```bash
curl -X GET http://127.0.0.1:8000/v1/models \
  -H "Authorization: Bearer apex-secret-key-12345"
```

---

### 3. Chat Completions (`POST /v1/chat/completions`)

#### Standard Non-Streaming Request
```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer apex-secret-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "apex-fast:latest",
    "messages": [
      {"role": "system", "content": "You are a concise programming assistant."},
      {"role": "user", "content": "How do I check if a file exists in Python?"}
    ],
    "temperature": 0.2
  }'
```

#### Streaming Request (Server-Sent Events)
```bash
curl -N -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer apex-secret-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "apex-pro:latest",
    "messages": [
      {"role": "user", "content": "Write an async worker loop with graceful shutdown in Python."}
    ],
    "stream": true
  }'
```

---

### 4. Automatic Model Routing (`POST /api/route`)

Evaluates task complexity and suggests the optimal tier (`apex-fast` vs `apex-pro`):

```bash
curl -X POST http://127.0.0.1:8000/api/route \
  -H "Authorization: Bearer apex-secret-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Debug this deadlock and race condition across our multi-file asyncio backend."}
    ]
  }'
```

**Response:**
```json
{
  "selected_model": "apex-pro:latest",
  "routing_reason": "Heuristics detected complex engineering task (score=6)",
  "confidence": 0.98,
  "classification": "complex",
  "available_models": ["apex-pro:latest", "apex-fast:latest"]
}
```

> **Automatic Chat Routing:** In `/v1/chat/completions`, if `"model"` is omitted or set to `"auto"`, the gateway automatically evaluates the conversation and selects between `apex-fast` and `apex-pro` on the fly!

---

### 5. User Authentication & Personal API Keys (`/v1/auth/*`)

#### User Registration & Login (JWT)
```bash
# Register
curl -X POST http://127.0.0.1:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "prof_satish", "email": "satish@apex.edu", "password": "SecurePassword123!", "role": "faculty"}'

# Login (returns JWT access_token)
curl -X POST http://127.0.0.1:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username_or_email": "prof_satish", "password": "SecurePassword123!"}'
```

#### Generating Personal API Key for Cabin IDE / Antigravity
```bash
# Generate key (Bearer <JWT>)
curl -X POST http://127.0.0.1:8000/v1/auth/api-keys \
  -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Cabin Laptop VS Code", "expires_in_days": 60}'
```
Returns a persistent key starting with `apex_live_...` that can be directly passed into IDE extensions or Antigravity!

---

### 6. Persistent Multi-Room Chat Sessions (`/v1/rooms/*`)

Create isolated conversation threads with sliding-window history and auto-routing:

```bash
# 1. Create a Chat Room
curl -X POST http://127.0.0.1:8000/v1/rooms \
  -H "Authorization: Bearer <JWT_OR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Compiler Deadlock Analysis",
    "default_model": "auto",
    "system_prompt": "You are a senior systems engineer specializing in concurrency."
  }'

# 2. Chat in the Room (Context and history automatically persisted!)
curl -X POST http://127.0.0.1:8000/v1/rooms/{room_id}/chat \
  -H "Authorization: Bearer <JWT_OR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Why does this mutex deadlock under high load?",
    "stream": false
  }'

# 3. List User Rooms with Message Counts
curl -X GET http://127.0.0.1:8000/v1/rooms \
  -H "Authorization: Bearer <JWT_OR_API_KEY>"

# 4. Retrieve Full Conversation History
curl -X GET http://127.0.0.1:8000/v1/rooms/{room_id} \
  -H "Authorization: Bearer <JWT_OR_API_KEY>"
```

---

### 7. Web Developer Portal (`GET /`)

The gateway serves a built-in dark-themed single-page Developer Portal directly at `http://127.0.0.1:8000/`:

- **User Registration & Login**: Authenticate to obtain a session and JWT token.
- **Personal API Key Generation**: Generate keys (`apex_live_...`) with custom names and expiration days.
- **VS Code / Continue Config Generator**: One-click copy configuration block pre-filled with host and models.
- **Active Keys Management**: View key prefixes, creation dates, expiration dates, and revoke compromised keys.
- **API Documentation Link**: Instant navigation to `/docs` (Swagger UI) from the header.

---

### 8. Database Administration & PostgreSQL Migration

APEX supports both SQLite (zero-config local file) and PostgreSQL (production multi-user):

```bash
# Inspect tables and records in terminal
python inspect_db.py

# Run end-to-end quickstart test
python quickstart.py

# Migrate all tables (Users, API Keys, Rooms, Messages, Audit Logs) from SQLite to PostgreSQL
python migrate_sqlite_to_postgres.py
```

Switching to PostgreSQL in `.env`:
```env
APEX_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/apex_db
```

---

### 9. Model Context Protocol (MCP) Integration

The gateway bundles an MCP stdio server (`mcp_server.py`) adhering to protocol version `2024-11-05`:

- **Tools exposed**:
  - `apex_chat`: Send instructions to local Ollama models with auto-routing.
  - `apex_route`: Evaluate task complexity and return recommended model tier.
  - `apex_model_status`: Check gateway health and verified models.
- **Client Configuration** (`.agents/mcp_config.json`):
  ```json
  {
    "mcpServers": {
      "apex-gateway": {
        "command": "python",
        "args": ["apex-gateway/mcp_server.py"]
      }
    }
  }
  ```

---

## Connecting External Tools & IDEs

### 1. Python OpenAI SDK
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="apex-secret-key-12345",
)

response = client.chat.completions.create(
    model="apex-fast:latest",  # or "apex-pro:latest" or "auto"
    messages=[{"role": "user", "content": "Write a quicksort in Python."}],
    stream=False,
)
print(response.choices[0].message.content)
```

### 2. VS Code (Continue Extension)
Add to your `~/.continue/config.json`:
```json
{
  "models": [
    {
      "title": "APEX Auto-Route",
      "provider": "openai",
      "model": "auto",
      "apiBase": "http://127.0.0.1:8000/v1",
      "apiKey": "apex-secret-key-12345"
    },
    {
      "title": "APEX Fast (7B)",
      "provider": "openai",
      "model": "apex-fast:latest",
      "apiBase": "http://127.0.0.1:8000/v1",
      "apiKey": "apex-secret-key-12345"
    },
    {
      "title": "APEX Pro (14B)",
      "provider": "openai",
      "model": "apex-pro:latest",
      "apiBase": "http://127.0.0.1:8000/v1",
      "apiKey": "apex-secret-key-12345"
    }
  ]
}
```

### 3. Cline / Roo Code / Antigravity
Select **OpenAI Compatible** as the provider:
- **Base URL**: `http://127.0.0.1:8000/v1`
- **API Key**: `apex-secret-key-12345`
- **Model ID**: `apex-pro:latest` or `apex-fast:latest` or `auto`

### 4. APEX MCP Server Integration
Point your Model Context Protocol (MCP) clients to the gateway endpoint `http://127.0.0.1:8000/v1/chat/completions`. Future MCP servers connect seamlessly using standard OpenAI client abstractions.

---

## Running the Automated Test Suite

Run pytest across all unit and integration tests:

```powershell
cd apex-gateway
..\.venv\Scripts\pytest.exe -v
```

All 19 tests mock external network resources and verify:
- Gateway health & degraded state reporting
- Live model listing and schema validation
- Chat completions (JSON & SSE streaming chunks)
- Invalid model rejection (404)
- Ollama connection failure handling (503)
- Request timeout handling (504)
- API key authentication & constant-time security
- Automatic routing heuristics & overrides

---

## Troubleshooting

1. **`Ollama connection error (503)`**:
   Verify Ollama is running locally:
   ```powershell
   curl.exe http://127.0.0.1:11434/api/tags
   ```
   If not running, start Ollama from the Windows start menu or run `ollama serve`.

2. **`Model not found (404)`**:
   Ensure `apex-fast:latest` and `apex-pro:latest` are registered in Ollama:
   ```powershell
   ollama list
   ```

3. **`401 Unauthorized`**:
   Check that your client sends the header matching `APEX_API_KEY` in `apex-gateway/.env`:
   ```bash
   Authorization: Bearer <key>
   ```

4. **Port Conflict on 8000**:
   Change `APEX_PORT=8080` in `.env`.

---

## Future Implementation Roadmap

### Phase 1 — Security & Access Control Hardening

| Feature | Description | Priority |
|---------|-------------|----------|
| **Role-Based Access Control (RBAC)** | Enforce granular permissions per role (`admin`, `faculty`, `student`). Students get read-only access to specific models; faculty can create rooms and API keys; admins manage users and system config. Currently roles are stored but not enforced beyond the admin guard. | 🔴 High |
| **Rate Limiting & Throttling** | Per-user and per-API-key request rate limiting (e.g., 60 req/min for students, 200 req/min for faculty) using sliding window counters. Prevents abuse and ensures fair GPU resource allocation across LAN users. | 🔴 High |
| **Token Usage Quotas** | Daily/monthly token budgets per user or role. Track cumulative `prompt_tokens + completion_tokens` from `request_logs` and reject requests when quota is exceeded. Configurable soft/hard limits with warning thresholds. | 🟡 Medium |
| **OAuth2 / SSO Integration** | Support external identity providers (Google Workspace, institutional LDAP/Active Directory) alongside local JWT auth for seamless campus-wide single sign-on. | 🟡 Medium |
| **API Key Scoping** | Allow personal API keys to be scoped to specific models (`apex-fast` only), endpoints (chat only, no admin), or rooms. Stored as JSON permissions on `UserApiKey`. | 🟢 Low |

---

### Phase 2 — Intelligence & Model Management

| Feature | Description | Priority |
|---------|-------------|----------|
| **Adaptive Routing with Feedback Loop** | Replace static heuristic scoring with a lightweight ML classifier trained on historical `request_logs` data (model selected, response quality, latency). Auto-improve routing accuracy over time. | 🟡 Medium |
| **Custom Ollama Modelfile Management** | API endpoints to create, list, and deploy custom Ollama Modelfiles (system prompts, parameter tuning, stop tokens) directly from the gateway. Enable faculty to create domain-specific model profiles (e.g., `apex-compiler`, `apex-networks`). | 🟡 Medium |
| **Prompt Templates & Presets** | Reusable, shareable prompt templates stored in the database. Faculty can create templates (e.g., "Code Review", "Explain Like I'm 5", "Architecture Critique") that students can invoke by name in any room. | 🟡 Medium |
| **Response Caching** | Content-addressable cache (SHA-256 of model + messages + temperature) with configurable TTL. Serve identical queries instantly without hitting Ollama. Particularly effective for documentation and explanation queries. | 🟢 Low |
| **Multi-Model & Multi-Backend Support** | Extend beyond two Ollama models to support additional backends — remote Ollama instances, vLLM servers, or cloud API fallbacks (Gemini, Claude) as overflow when local GPU is saturated. | 🟢 Low |

---

### Phase 3 — Analytics & Observability

| Feature | Description | Priority |
|---------|-------------|----------|
| **Admin Analytics Dashboard** | Web-based dashboard (extend `static/index.html` or separate React SPA) visualizing `request_logs` data: requests per hour, average latency by model, token consumption trends, top users, error rate heatmaps, and model routing distribution. | 🔴 High |
| **Real-Time GPU & System Metrics** | Poll Ollama `/api/ps` and NVIDIA `nvidia-smi` for live GPU utilization, VRAM usage, model load status, and inference queue depth. Surface in `/health` and the admin dashboard. | 🟡 Medium |
| **Structured JSON Logging** | Migrate from plain text logging to structured JSON log format for easier parsing by log aggregation tools (ELK, Grafana Loki). Add request correlation IDs across all log entries. | 🟡 Medium |
| **Webhook & Alerting** | Configurable webhook notifications (Discord, Slack, email) triggered by: Ollama going offline, error rate exceeding threshold, GPU temperature warnings, or quota exhaustion. | 🟢 Low |

---

### Phase 4 — Advanced Chat & Collaboration

| Feature | Description | Priority |
|---------|-------------|----------|
| **RAG — Retrieval-Augmented Generation** | File upload endpoint (`/v1/rooms/{id}/documents`) supporting PDF, code files, and Markdown. Chunk and embed documents using a local embedding model, store vectors in a lightweight vector DB (ChromaDB/SQLite-VSS), and inject relevant context into prompts automatically. | 🔴 High |
| **Conversation Export & Import** | Export room history as Markdown, JSON, or PDF. Import conversations from other tools. Enable faculty to share annotated conversations as teaching materials. | 🟡 Medium |
| **WebSocket Streaming** | Add `ws://` endpoint alongside SSE for lower-latency bidirectional streaming. Better suited for real-time IDE integrations and interactive chat UIs. | 🟡 Medium |
| **Shared / Collaborative Rooms** | Allow room owners to invite other users with read-only or read-write access. Enable pair-programming-style collaborative AI sessions with activity indicators. | 🟢 Low |
| **Branching Conversations** | Fork a conversation at any message to explore alternative approaches without losing the original thread. Stored as a tree structure with parent message references. | 🟢 Low |

---

### Phase 5 — Deployment & Infrastructure

| Feature | Description | Priority |
|---------|-------------|----------|
| **Docker & Docker Compose** | Containerize the gateway with a `Dockerfile` and `docker-compose.yml` bundling the gateway, PostgreSQL, and optional Ollama sidecar. One-command deployment for new lab machines. | 🔴 High |
| **Load Balancing Across Multiple GPUs** | Support multiple Ollama instances (e.g., 2× RTX 5060 Ti) with round-robin or least-connections routing. Health-check each backend and failover automatically. | 🟡 Medium |
| **Automated Backup & Restore** | Scheduled database backups (SQLite snapshots or `pg_dump`) with configurable retention. One-click restore from the admin dashboard. | 🟡 Medium |
| **HTTPS & TLS Termination** | Built-in TLS support via Uvicorn or reverse proxy config templates (Nginx/Caddy) for secure LAN and remote access. Auto-generate self-signed certificates for lab environments. | 🟡 Medium |
| **CI/CD Pipeline** | GitHub Actions workflow for automated testing, linting (`ruff`), type checking (`mypy`), and optional deployment to a staging server on every push. | 🟢 Low |

---

### Phase 6 — Ecosystem & Extensibility

| Feature | Description | Priority |
|---------|-------------|----------|
| **Plugin / Middleware System** | Extensible middleware pipeline allowing custom pre/post-processing hooks on requests (e.g., content filtering, automatic prompt augmentation, usage billing, PII redaction). | 🟡 Medium |
| **Model Performance Benchmarking** | Built-in benchmarking tool that runs a standardized prompt suite against all installed models and reports latency percentiles, tokens/sec, and quality scores. Helps faculty decide optimal model configurations. | 🟡 Medium |
| **Multimodal Support (Vision)** | Extend chat completions to accept image inputs (base64 or file upload) for vision-capable models. Forward to Ollama's multimodal API with proper payload transformation. | 🟢 Low |
| **OpenAI Assistants API Compatibility** | Implement the Assistants API surface (`/v1/assistants`, `/v1/threads`, `/v1/runs`) for richer agent workflows, enabling local tool-use and function-calling patterns. | 🟢 Low |
| **Student Playground UI** | Lightweight chat web UI (extend the developer portal) where students can interact with models directly in the browser without needing IDE setup. Include syntax-highlighted code blocks and Markdown rendering. | 🟡 Medium |

