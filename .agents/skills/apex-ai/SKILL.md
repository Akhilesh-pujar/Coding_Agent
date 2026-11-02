---
name: apex-ai
description: Query and delegate coding and architecture tasks to locally hosted APEX Ollama models (apex-fast and apex-pro) via the APEX API Gateway. Use when the user asks to run a prompt locally, evaluate code with local models, or check local model status.
---

# APEX Local AI Model Delegation

This skill enables Antigravity to query the local APEX API Gateway running on this host (`http://127.0.0.1:8000`).

## Gateway Endpoints

- Base URL: `http://127.0.0.1:8000/v1`
- LAN URL: `http://172.16.25.140:8000/v1`
- Models Available:
  - `apex-fast:latest` (Qwen 2.5 Coder 7B - fast queries, docs, explanations)
  - `apex-pro:latest` (Qwen 2.5 Coder 14B - deep architecture, debugging, multi-file reasoning)
  - `auto` (Gateway automatically chooses the best model)

## How to Query the Local Model

Antigravity agents can query the local gateway via the `apex_chat` tool provided by the `apex-gateway` MCP server, or via HTTP:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer apex-secret-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [
      {"role": "user", "content": "Analyze and explain this function."}
    ]
  }'
```

