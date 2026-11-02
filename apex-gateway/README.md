# APEX – Local AI API Gateway

**APEX API Gateway** is a production-grade, modular, local-first API gateway and routing layer built with FastAPI, HTTPX, and SQLAlchemy 2.x for locally hosted Ollama AI models.

It provides a unified OpenAI-compatible interface, intelligent task-based model routing between `apex-fast` (7B) and `apex-pro` (14B), streaming and non-streaming completions, performance and audit logging, and connectivity for MCP agents, IDEs, and local developer tooling.

---

## Architecture Overview

```
                      +-------------------------------------------------+
                      |              Client Applications                |
                      |  (Antigravity, VS Code, MCP Servers, cURL, etc) |
                      +-------------------------------------------------+
                                              |
                                              | (Bearer Auth + HTTP / SSE)
                                              v
                      +-------------------------------------------------+
                      |           APEX API Gateway (FastAPI)            |
                      |                                                 |
                      |   /health        /v1/models   /api/route        |
                      |   /v1/chat/completions                          |
                      +-------------------------------------------------+
                                      |                 |
                   +------------------+                 +----------------+
                   | (Intelligent Model Router)                          | (Async Audit)
                   v                                                     v
      +-------------------------+                           +-------------------------+
      |  Model Router & Heuristic|                          |   SQLite Audit DB       |
      |  - Fast: 7B (Docs/Simple) |                         |   (Request durations,   |
      |  - Pro: 14B (Architecture)|                         |    tokens, status)      |
      +-------------------------+                           +-------------------------+
                   |
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
│   ├── main.py              # Application factory, lifespan, error handling, CORS
│   ├── config.py            # Type-safe settings with Pydantic BaseSettings
│   ├── dependencies.py      # Dual-auth (JWT + API key) & database session providers
│   ├── api/
│   │   ├── health.py        # Gateway & Ollama health monitoring (/health)
│   │   ├── auth.py          # User registration, login, personal API keys (/v1/auth)
│   │   ├── rooms.py         # Persistent multi-room chat & history (/v1/rooms)
│   │   ├── models.py        # OpenAI-compatible model discovery (/v1/models)
│   │   ├── chat.py          # OpenAI-compatible completions (/v1/chat/completions)
│   │   └── routing.py       # Heuristic routing diagnostics (/api/route)
│   ├── core/
│   │   ├── security.py      # Password hashing (bcrypt) & JWT token signing (PyJWT)
│   │   ├── ollama_client.py # Async HTTPX client with connection pooling
│   │   ├── model_registry.py# Real-time model verification against Ollama
│   │   ├── model_router.py  # Intent & complexity analyzer (Fast vs Pro)
│   │   ├── authentication.py# Constant-time API Key verification
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
│       ├── connection.py    # Async SQLAlchemy 2.x SQLite session engine
│       └── models.py        # User, UserApiKey, ChatRoom, ChatMessage, RequestLog
├── tests/
│   ├── test_auth.py         # User registration, JWT login, API key lifecycle
│   ├── test_rooms.py        # Chat room persistence, sliding context, isolation
│   ├── test_health.py       # Health checks and offline tests
│   ├── test_models.py       # Model discovery and auth tests
│   ├── test_chat.py         # Streaming, non-streaming, timeouts, errors
│   └── test_routing.py      # Heuristic routing and user override tests
├── logs/                    # Rotating log files
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

