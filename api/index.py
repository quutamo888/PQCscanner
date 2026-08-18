import os
import sys

# Ensure project root is on sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from main import app as fastapi_app

# Vercel ASGI path wrapper to resolve rewritten endpoints
async def app(scope, receive, send):
    if scope["type"] in ("http", "websocket"):
        headers = dict(scope.get("headers", []))
        matched = headers.get(b"x-matched-path")
        if matched:
            scope["path"] = matched.decode("utf-8")
    await fastapi_app(scope, receive, send)
