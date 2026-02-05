"""Local OAuth callback server for handling OAuth redirects.

Starts a temporary local HTTP server to receive the OAuth callback
with the authorization code.
"""

from __future__ import annotations

import asyncio
import socket
import webbrowser
from dataclasses import dataclass
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlparse

from .client import OAuthClient, OAuthTokens, OAuthError
from .storage import TokenStorage


@dataclass
class CallbackResult:
    """Result from OAuth callback."""

    code: str | None = None
    state: str | None = None
    error: str | None = None
    error_description: str | None = None

    @property
    def success(self) -> bool:
        return self.code is not None and self.error is None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    # Class-level storage for result
    callback_result: CallbackResult | None = None

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def do_GET(self):
        """Handle GET request (OAuth callback)."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # Extract callback parameters
        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]
        error = params.get("error", [None])[0]
        error_desc = params.get("error_description", [None])[0]

        # Store result
        OAuthCallbackHandler.callback_result = CallbackResult(
            code=code,
            state=state,
            error=error,
            error_description=error_desc,
        )

        # Send response
        if code:
            self._send_success_page()
        else:
            self._send_error_page(error, error_desc)

    def _send_success_page(self):
        """Send success HTML page."""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>GHL OAuth Success</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }
                .container {
                    background: white;
                    padding: 40px 60px;
                    border-radius: 12px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    text-align: center;
                }
                .checkmark {
                    font-size: 64px;
                    margin-bottom: 20px;
                }
                h1 { color: #333; margin-bottom: 10px; }
                p { color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="checkmark">✓</div>
                <h1>Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
            </div>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def _send_error_page(self, error: str | None, description: str | None):
        """Send error HTML page."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>GHL OAuth Error</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%);
                }}
                .container {{
                    background: white;
                    padding: 40px 60px;
                    border-radius: 12px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    text-align: center;
                }}
                .error-icon {{ font-size: 64px; margin-bottom: 20px; }}
                h1 {{ color: #333; margin-bottom: 10px; }}
                p {{ color: #666; }}
                .error-code {{ font-family: monospace; background: #f5f5f5; padding: 4px 8px; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error-icon">✗</div>
                <h1>Authorization Failed</h1>
                <p>{description or 'An error occurred during authorization.'}</p>
                <p><span class="error-code">{error or 'unknown_error'}</span></p>
                <p>Please try again or check the terminal for more details.</p>
            </div>
        </body>
        </html>
        """
        self.send_response(400)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())


class OAuthCallbackServer:
    """Local server for handling OAuth callbacks.

    Usage:
        server = OAuthCallbackServer(port=3000)

        # Start server in background
        server.start()

        # Wait for callback
        result = server.wait_for_callback(timeout=300)

        # Stop server
        server.stop()

    Or use as async context manager:
        async with OAuthCallbackServer(port=3000) as server:
            result = await server.wait_for_callback_async(timeout=300)
    """

    def __init__(self, port: int = 3000, host: str = "localhost"):
        self.port = port
        self.host = host
        self._server: HTTPServer | None = None
        self._thread: Thread | None = None

    @property
    def callback_url(self) -> str:
        """Get the callback URL for OAuth configuration."""
        return f"http://{self.host}:{self.port}/callback"

    def _find_free_port(self) -> int:
        """Find a free port if default is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    def start(self, find_free_port: bool = True) -> int:
        """Start the callback server.

        Args:
            find_free_port: If True, find free port if default is in use

        Returns:
            The port the server is running on
        """
        # Reset callback result
        OAuthCallbackHandler.callback_result = None

        try:
            self._server = HTTPServer((self.host, self.port), OAuthCallbackHandler)
        except OSError:
            if find_free_port:
                self.port = self._find_free_port()
                self._server = HTTPServer((self.host, self.port), OAuthCallbackHandler)
            else:
                raise

        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        return self.port

    def stop(self):
        """Stop the callback server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None

    def wait_for_callback(self, timeout: float = 300) -> CallbackResult:
        """Wait for OAuth callback.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            CallbackResult with code or error

        Raises:
            TimeoutError: If no callback received within timeout
        """
        import time

        start = time.time()
        while time.time() - start < timeout:
            if OAuthCallbackHandler.callback_result is not None:
                return OAuthCallbackHandler.callback_result
            time.sleep(0.1)

        raise TimeoutError(f"No OAuth callback received within {timeout} seconds")

    async def wait_for_callback_async(self, timeout: float = 300) -> CallbackResult:
        """Async version of wait_for_callback."""
        loop = asyncio.get_running_loop()
        start = loop.time()
        while loop.time() - start < timeout:
            if OAuthCallbackHandler.callback_result is not None:
                return OAuthCallbackHandler.callback_result
            await asyncio.sleep(0.1)

        raise TimeoutError(f"No OAuth callback received within {timeout} seconds")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    async def __aenter__(self):
        self.start()
        return self

    async def __aexit__(self, *args):
        self.stop()


async def run_oauth_flow(
    client: OAuthClient,
    storage: TokenStorage | None = None,
    port: int = 3000,
    timeout: float = 300,
    open_browser: bool = True,
) -> OAuthTokens:
    """Run the complete OAuth flow.

    1. Start local callback server
    2. Open browser to authorization URL
    3. Wait for user to authorize
    4. Exchange code for tokens
    5. Save tokens to storage

    Args:
        client: OAuthClient instance
        storage: TokenStorage for saving tokens
        port: Port for callback server
        timeout: Max seconds to wait for callback
        open_browser: Whether to auto-open browser

    Returns:
        OAuthTokens on success

    Raises:
        OAuthError: If authorization fails
        TimeoutError: If user doesn't complete flow in time
    """
    storage = storage or TokenStorage()

    async with OAuthCallbackServer(port=port) as server:
        # Update redirect URI if port changed
        if server.port != port:
            client.redirect_uri = server.callback_url

        # Generate authorization URL
        state = client.generate_state()
        auth_url = client.get_authorization_url(state=state)

        print(f"\nOpening browser for GHL authorization...")
        print(f"If browser doesn't open, visit:\n{auth_url}\n")

        if open_browser:
            webbrowser.open(auth_url)

        # Wait for callback
        print("Waiting for authorization...")
        result = await server.wait_for_callback_async(timeout=timeout)

        if not result.success:
            raise OAuthError(
                result.error_description or result.error or "Authorization failed",
                error_code=result.error,
            )

        # Exchange code for tokens
        print("Exchanging code for tokens...")
        tokens = await client.exchange_code(
            code=result.code,
            state=result.state,
            verify_state=True,
        )

        # Save tokens
        storage.save_oauth_tokens(tokens.to_storage_data())
        print("Tokens saved successfully!")

        return tokens
