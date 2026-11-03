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
    banner = f"""
===================================================================
 APEX API Gateway is active!
 
 Open in your browser on this computer:
   --> http://localhost:{settings.APEX_PORT}/docs
   --> http://127.0.0.1:{settings.APEX_PORT}/docs
 
 Access from another computer across the LAN (e.g. your cabin):
   --> http://172.16.25.140:{settings.APEX_PORT}/docs
 
 Database Connected:
   --> {settings.APEX_DATABASE_URL}
 
 * IMPORTANT FOR BROWSER ACCESS:
   Do NOT type '0.0.0.0' in your browser address bar.
   Chrome/Edge will say 'ERR_ADDRESS_INVALID'.
   Always use 'http://localhost:{settings.APEX_PORT}' or 'http://127.0.0.1:{settings.APEX_PORT}'.
===================================================================
"""
    print(banner)
    uvicorn.run(
        "app.main:app",
        host=settings.APEX_HOST,
        port=settings.APEX_PORT,
        reload=False,
        log_level=settings.APEX_LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()

