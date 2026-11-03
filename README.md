# APEX — Local AI Model Gateway & Developer Platform

**APEX** is a local-first, modular API gateway that bridges local [Ollama](https://ollama.com/) instances running on GPU hardware (NVIDIA RTX 5060 Ti) to developer tools, IDEs (VS Code, Continue, Antigravity, Cursor, Cline), and autonomous AI agents via OpenAI-compatible endpoints and Model Context Protocol (MCP).

---

## Key Capabilities

- **OpenAI-Compatible Endpoints**: Seamless drop-in replacement for `/v1/chat/completions`, `/v1/models`, and `/v1/completions`.
- **Intelligent Model Auto-Routing**: Automatically inspects prompt complexity (concurrency, architecture, multi-file reasoning, etc.) and dispatches between:
  - `apex-fast:latest` (Qwen 2.5 Coder 7B) — Low-latency responses, syntax, documentation.
  - `apex-pro:latest` (Qwen 2.5 Coder 14B) — Deep architectural reasoning, distributed systems debugging, complex refactoring.
- **Tri-Layer Authentication**:
  - Master System Key (`APEX_API_KEY` from `.env`)
  - Personal User API Keys (`apex_live_...` with SHA-256 storage and expiration)
  - JWT Access Tokens (bcrypt password hashing, 24-hour expiry)
- **Persistent Multi-Room Chat**: Isolated conversation threads per user with sliding-window history (last 12 messages), automatic room titling, and streaming responses.
- **Web Developer Portal**: Built-in dark-themed web UI at `http://localhost:8000/` for user registration, login, personal API key generation, and VS Code configuration snippet copying.
- **Dual-Database Support**: Zero-config async SQLite by default, with complete async migration to PostgreSQL for production multi-tenant environments.
- **Model Context Protocol (MCP)**: Native stdio JSON-RPC 2.0 server (`mcp_server.py`) exposing `apex_chat`, `apex_route`, and `apex_model_status` tools.
- **Real-Time Audit Logging**: Non-blocking SQLite/PostgreSQL request logging tracking duration, prompt tokens, completion tokens, and HTTP status codes.

---

## Repository Structure

```
.
├── apex-gateway/                        # Main FastAPI Gateway service
│   ├── app/
│   │   ├── main.py                      # FastAPI application factory & middleware
│   │   ├── config.py                    # Pydantic Settings & environment validation
│   │   ├── dependencies.py              # Auth guards & database session dependency
│   │   ├── api/                         # Endpoint routers (health, auth, chat, rooms, models, route)
│   │   ├── core/                        # Router heuristic, Ollama client, model registry, security
│   │   ├── schemas/                     # Pydantic v2 schemas for all requests & responses
│   │   ├── services/                    # Business logic for chat, rooms, and model routing
│   │   └── database/                    # Async SQLAlchemy 2.x models & engine
│   ├── static/
│   │   └── index.html                   # Developer Portal UI (Registration, Keys, IDE Config)
│   ├── tests/                           # 19 comprehensive pytest tests (100% mocked Ollama)
│   ├── mcp_server.py                    # Stdio MCP server for agent integrations
│   ├── run.py                           # CLI entrypoint
│   ├── requirements.txt                 # Dependencies
│   └── README.md                        # Gateway technical reference
├── .agents/
│   ├── mcp_config.json                  # MCP agent configuration
│   └── skills/
│       └── apex-ai/
│           └── SKILL.md                 # Antigravity skill for local model delegation
├── start_gateway.bat                    # Windows 1-click launcher (LAN mode: 0.0.0.0:8000)
├── quickstart.py                        # Automated end-to-end test script
├── inspect_db.py                        # Terminal database viewer
├── migrate_sqlite_to_postgres.py        # SQLite -> PostgreSQL migration script
└── apex.db                              # Local SQLite database
```

---

## Quick Start (Windows)

### 1. Prerequisites
- Python 3.13+ installed.
- [Ollama](https://ollama.com/) running locally:
  ```powershell
  ollama run apex-fast:latest
  ollama run apex-pro:latest
  ```

### 2. Install Dependencies
```powershell
# Create & activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install requirements
pip install -r apex-gateway\requirements.txt
```

### 3. Configure Environment
```powershell
cp apex-gateway\.env.example apex-gateway\.env
```

### 4. Start the Gateway
Double-click `start_gateway.bat` or run:
```powershell
python apex-gateway\run.py
```

The gateway is now running:
- **Developer Portal**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Swagger Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 5. Verify Installation
Run the automated quickstart test in a new terminal:
```powershell
python quickstart.py
```

---

## Connecting External Tools

### VS Code (Continue Extension)
Add to `~/.continue/config.json`:
```json
{
  "models": [
    {
      "title": "APEX Auto-Route",
      "provider": "openai",
      "model": "auto",
      "apiBase": "http://127.0.0.1:8000/v1",
      "apiKey": "YOUR_PERSONAL_OR_MASTER_API_KEY"
    }
  ]
}
```

### Antigravity & Agent IDEs
Select **OpenAI Compatible**:
- **Base URL**: `http://127.0.0.1:8000/v1`
- **API Key**: `YOUR_PERSONAL_OR_MASTER_API_KEY`
- **Model**: `auto`, `apex-fast:latest`, or `apex-pro:latest`

### Python OpenAI SDK
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="YOUR_API_KEY",
)

response = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "How do I implement binary search in Python?"}],
)
print(response.choices[0].message.content)
```

---

## Testing

Execute the test suite with pytest:
```powershell
cd apex-gateway
pytest -v
```

All 19 tests verify health, model discovery, SSE streaming, timeouts, auth guards, tenant isolation, and heuristic routing without needing an active Ollama connection.

---

## Future Roadmap

The detailed implementation roadmap is organized into 6 phases:
1. **Security & Access Control**: Granular RBAC, rate limiting, token usage quotas, SSO.
2. **Intelligence & Routing**: Adaptive ML routing, custom Ollama Modelfile deployment, response caching.
3. **Analytics & Observability**: Web analytics dashboard, real-time GPU VRAM telemetry, JSON logging.
4. **Advanced Chat & Collaboration**: Local RAG with vector search, conversation export, WebSocket streaming.
5. **Deployment & Infrastructure**: Docker Compose containerization, multi-GPU load balancing, TLS termination.
6. **Ecosystem & Extensibility**: Middleware plugin system, model benchmarking, multimodal vision inputs.

See [`apex-gateway/README.md`](apex-gateway/README.md#future-implementation-roadmap) for full details.

