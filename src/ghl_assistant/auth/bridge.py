"""Token Bridge - Extract GHL authToken via bookmarklet.

Starts a local HTTP server that serves a bookmarklet page.
The bookmarklet extracts authToken, companyId, and userId from
the GHL Vue store and POSTs them back to the local server.
"""

from __future__ import annotations

import json
import socket
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

_GHL_ORIGIN = "https://app.gohighlevel.com"
_MAX_BODY = 8192


class TokenBridgeHandler(BaseHTTPRequestHandler):
    """HTTP handler for the token bridge."""

    captured_token: dict | None = None

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def do_GET(self):
        """Serve the bookmarklet page or status endpoint."""
        if self.path == "/status":
            self._send_status()
        else:
            self._send_bookmarklet_page()

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_POST(self):
        """Receive token from bookmarklet."""
        if self.path != "/token":
            self.send_response(404)
            self.end_headers()
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self.send_response(400)
            self.end_headers()
            return

        if length > _MAX_BODY:
            self.send_response(413)
            self.end_headers()
            return

        body = self.rfile.read(length)

        try:
            data = json.loads(body)
        except Exception:
            self.send_response(400)
            self._cors_headers()
            self.end_headers()
            return

        auth_token = data.get("authToken")
        if not auth_token:
            self.send_response(400)
            self._cors_headers()
            self.end_headers()
            return

        TokenBridgeHandler.captured_token = {
            "authToken": auth_token,
            "companyId": data.get("companyId"),
            "userId": data.get("userId"),
        }

        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", _GHL_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_status(self):
        """Return JSON status for the polling script."""
        captured = TokenBridgeHandler.captured_token is not None
        payload = json.dumps({"captured": captured}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def _send_bookmarklet_page(self):
        port = self.server.server_address[1]
        html = _bookmarklet_page(port)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())


class TokenBridgeServer:
    """Local server for token bridge bookmarklet.

    Usage:
        server = TokenBridgeServer()
        server.start()
        # User drags bookmarklet to toolbar and clicks it on GHL
        token_data = server.wait_for_token(timeout=120)
        server.stop()
    """

    def __init__(self, port: int = 3456, host: str = "localhost"):
        self.port = port
        self.host = host
        self._server: HTTPServer | None = None
        self._thread: Thread | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def _find_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    def start(self, find_free_port: bool = True) -> int:
        """Start the bridge server. Returns the port."""
        TokenBridgeHandler.captured_token = None

        try:
            self._server = HTTPServer((self.host, self.port), TokenBridgeHandler)
        except OSError:
            if find_free_port:
                self.port = self._find_free_port()
                self._server = HTTPServer((self.host, self.port), TokenBridgeHandler)
            else:
                raise

        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.port

    def stop(self):
        """Stop the bridge server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None

    def wait_for_token(self, timeout: float = 120) -> dict:
        """Wait for the bookmarklet to send a token.

        Returns:
            dict with authToken, companyId, userId

        Raises:
            TimeoutError: If no token received within timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            if TokenBridgeHandler.captured_token is not None:
                return TokenBridgeHandler.captured_token
            time.sleep(0.2)

        raise TimeoutError(f"No token received within {timeout} seconds")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()


def _bookmarklet_page(port: int) -> str:
    """Generate the bookmarklet HTML page."""
    # The bookmarklet JS (minified inline)
    bookmarklet_js = (
        "javascript:void("
        "(function(){"
        "var s=document.querySelector('#app').__vue_app__;"
        "if(!s){alert('Not on a GHL page');return;}"
        "var st=s.config.globalProperties.$store.state;"
        "var u=st.auth&&st.auth.user;"
        "if(!u||!u.authToken){alert('No authToken found. Are you logged in?');return;}"
        "var d={authToken:u.authToken,companyId:u.companyId||'',userId:u.id||''};"
        f"fetch('http://localhost:{port}/token',"
        "{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)})"
        ".then(function(r){if(r.ok)alert('Token captured! You can close this tab.');"
        "else alert('Error sending token');})"
        ".catch(function(e){alert('Could not reach bridge server: '+e);});"
        "})()"
        ")"
    )

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>GHL Token Bridge</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        .container {{
            background: white;
            padding: 40px 60px;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            text-align: center;
            max-width: 600px;
        }}
        h1 {{ color: #333; margin-bottom: 10px; }}
        p {{ color: #666; line-height: 1.6; }}
        .bookmarklet {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 14px 28px;
            border-radius: 8px;
            text-decoration: none;
            font-size: 16px;
            font-weight: 600;
            margin: 20px 0;
            cursor: grab;
            box-shadow: 0 4px 12px rgba(102,126,234,0.4);
        }}
        .bookmarklet:hover {{
            box-shadow: 0 6px 16px rgba(102,126,234,0.6);
        }}
        .steps {{
            text-align: left;
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px 30px;
            margin-top: 20px;
        }}
        .steps li {{
            margin: 8px 0;
            color: #555;
        }}
        .status {{
            margin-top: 20px;
            padding: 12px;
            border-radius: 8px;
            font-weight: 600;
        }}
        .waiting {{ background: #fff3cd; color: #856404; }}
        .success {{ background: #d4edda; color: #155724; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>GHL Token Bridge</h1>
        <p>Drag this button to your bookmarks bar:</p>
        <a class="bookmarklet" href="{bookmarklet_js}">GHL Capture Token</a>
        <ol class="steps">
            <li>Drag the button above to your bookmarks bar</li>
            <li>Go to <strong>app.gohighlevel.com</strong> (make sure you're logged in)</li>
            <li>Click the <strong>GHL Capture Token</strong> bookmark</li>
            <li>You'll see a confirmation alert when the token is captured</li>
        </ol>
        <div id="status" class="status waiting">Waiting for token...</div>
    </div>
    <script>
        (function poll() {{
            fetch('/status')
                .then(function(r) {{ return r.json(); }})
                .then(function(d) {{
                    if (d.captured) {{
                        var el = document.getElementById('status');
                        el.className = 'status success';
                        el.textContent = 'Token captured! You can close this tab.';
                    }}
                }})
                .catch(function(){{}});
            setTimeout(poll, 2000);
        }})();
    </script>
</body>
</html>"""
