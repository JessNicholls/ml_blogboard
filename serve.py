"""
Dev server for blogboard/web with live reload.

Usage:
    python serve.py            # serves on http://localhost:8000
    python serve.py --port 3000
"""
import argparse
import asyncio
import mimetypes
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response, FileResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.background import BackgroundTask

WEB_DIR = Path(__file__).parent / "blogboard" / "web"

RELOAD_SNIPPET = b"""
<script>
(function(){
  var src = new EventSource('/__livereload');
  src.onmessage = function(){ location.reload(); };
  src.onerror   = function(){ src.close(); };
})();
</script>
"""


def inject_reload(html: bytes) -> bytes:
    """Inject the live-reload <script> just before </body>."""
    tag = b"</body>"
    idx = html.lower().rfind(tag)
    if idx == -1:
        return html + RELOAD_SNIPPET
    return html[:idx] + RELOAD_SNIPPET + html[idx:]


async def serve_html(request: Request) -> Response:
    """Serve .html files with the live-reload snippet injected."""
    path = request.path_params.get("path", "").lstrip("/") or "index.html"
    if not path.endswith(".html"):
        path += ".html"
    file = WEB_DIR / path
    if not file.exists() or not file.is_file():
        file = WEB_DIR / "index.html"
    html = inject_reload(file.read_bytes())
    return HTMLResponse(html.decode("utf-8"))


async def livereload_sse(request: Request) -> Response:
    """Server-Sent Events endpoint — sends a message when any file changes."""
    async def event_stream():
        from watchfiles import awatch
        yield b"data: connected\n\n"
        async for _ in awatch(str(WEB_DIR)):
            yield b"data: reload\n\n"

    return Response(
        content=event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


routes = [
    Route("/__livereload", livereload_sse),
    Route("/", serve_html),
    Route("/{path:path}.html", serve_html),
    Mount("/", app=StaticFiles(directory=str(WEB_DIR), html=True)),
]

app = Starlette(routes=routes)


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="BlogBoard dev server with live reload")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()

    print(f"\n  BlogBoard dev server")
    print(f"  http://{args.host}:{args.port}")
    print(f"  Watching: {WEB_DIR}")
    print(f"  Live reload: ON\n")

    uvicorn.run("serve:app", host=args.host, port=args.port, reload=False)
