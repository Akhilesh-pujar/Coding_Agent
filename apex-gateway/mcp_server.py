"""Model Context Protocol (MCP) stdio server for APEX Gateway.

Allows Antigravity, VS Code, and MCP-compatible agents to seamlessly use
locally hosted apex-fast and apex-pro models as tools.
"""

import sys
import json
import logging
from pathlib import Path
import httpx

# Add gateway root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

log_dir = BASE_DIR / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(log_dir / "mcp_server.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
from app.config import get_settings
logger = logging.getLogger("apex.mcp")


def get_gateway_headers() -> dict:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.APEX_API_KEY}",
        "Content-Type": "application/json",
    }


def get_gateway_url() -> str:
    settings = get_settings()
    # Always connect locally when MCP server runs on the same machine
    return f"http://127.0.0.1:{settings.APEX_PORT}"


def handle_tools_list() -> dict:
    return {
        "tools": [
            {
                "name": "apex_chat",
                "description": "Send a prompt or coding task to local Ollama models (apex-fast, apex-pro, or auto-route).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "The instruction or question for the local AI model.",
                        },
                        "model": {
                            "type": "string",
                            "enum": ["auto", "apex-fast:latest", "apex-pro:latest"],
                            "default": "auto",
                            "description": "Choose 'auto' for intelligent routing, or specify 'apex-fast:latest' or 'apex-pro:latest'.",
                        },
                        "temperature": {
                            "type": "number",
                            "default": 0.2,
                            "description": "Sampling temperature (0.0 to 1.0).",
                        },
                    },
                    "required": ["prompt"],
                },
            },
            {
                "name": "apex_route",
                "description": "Evaluate task complexity and return recommended model tier (apex-fast or apex-pro).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_description": {
                            "type": "string",
                            "description": "Description or snippet of the coding task to evaluate.",
                        }
                    },
                    "required": ["task_description"],
                },
            },
            {
                "name": "apex_model_status",
                "description": "Check real-time health and verified status of local Ollama models.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]
    }


def handle_tool_call(name: str, arguments: dict) -> dict:
    base_url = get_gateway_url()
    headers = get_gateway_headers()

    with httpx.Client(timeout=300.0) as client:
        if name == "apex_chat":
            prompt = arguments.get("prompt", "")
            model = arguments.get("model", "auto")
            temp = arguments.get("temperature", 0.2)

            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temp,
            }
            resp = client.post(f"{base_url}/v1/chat/completions", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                selected_model = data.get("model", model)
                usage = data.get("usage", {})
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"[{selected_model}]\n{content}\n\n(Tokens: {usage.get('total_tokens', 'N/A')})",
                        }
                    ]
                }
            return {
                "content": [{"type": "text", "text": f"Error {resp.status_code}: {resp.text}"}],
                "isError": True,
            }

        elif name == "apex_route":
            desc = arguments.get("task_description", "")
            payload = {"prompt": desc}
            resp = client.post(f"{base_url}/api/route", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Recommended Model: {data.get('selected_model')}\n"
                                f"Classification: {data.get('classification')}\n"
                                f"Confidence: {data.get('confidence'):.0%}\n"
                                f"Reason: {data.get('routing_reason')}"
                            ),
                        }
                    ]
                }
            return {
                "content": [{"type": "text", "text": f"Error {resp.status_code}: {resp.text}"}],
                "isError": True,
            }

        elif name == "apex_model_status":
            resp = client.get(f"{base_url}/health")
            if resp.status_code == 200:
                return {"content": [{"type": "text", "text": json.dumps(resp.json(), indent=2)}]}
            return {
                "content": [{"type": "text", "text": f"Error {resp.status_code}: {resp.text}"}],
                "isError": True,
            }

        return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}


def main():
    """Main JSON-RPC 2.0 loop reading from stdin and writing to stdout."""
    logger.info("APEX MCP Stdio server started.")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "apex-gateway-mcp", "version": "1.0.0"},
                },
            }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            logger.info("MCP client initialized.")

        elif method == "tools/list":
            res = {"jsonrpc": "2.0", "id": req_id, "result": handle_tools_list()}
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            call_result = handle_tool_call(tool_name, tool_args)
            res = {"jsonrpc": "2.0", "id": req_id, "result": call_result}
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

        elif req_id is not None:
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method '{method}' not found"},
            }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
