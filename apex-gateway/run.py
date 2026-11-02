"""Entry point to launch the APEX API Gateway."""

import sys
from pathlib import Path
import uvicorn

# Ensure the gateway root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import get_settings


def main() -> None:
    """Run uvicorn ASGI server."""
    settings = get_settings()
    print(f"Starting APEX Gateway on http://{settings.APEX_HOST}:{settings.APEX_PORT}")
    uvicorn.run(
        "app.main:app",
        host=settings.APEX_HOST,
        port=settings.APEX_PORT,
        reload=False,
        log_level=settings.APEX_LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()

