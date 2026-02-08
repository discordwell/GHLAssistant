"""Network traffic capture via Chrome DevTools Protocol."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import nodriver.cdp.network as network


@dataclass
class CapturedRequest:
    """A captured HTTP request."""

    request_id: str
    url: str
    method: str
    headers: dict
    post_data: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Response data (filled in when response arrives)
    response_status: int | None = None
    response_headers: dict | None = None
    response_body: str | None = None
    response_body_truncated: bool = False
    response_body_base64: bool = False
    response_body_length: int | None = None

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "url": self.url,
            "method": self.method,
            "headers": self.headers,
            "post_data": self.post_data,
            "timestamp": self.timestamp,
            "response_status": self.response_status,
            "response_headers": self.response_headers,
            "response_body": self.response_body,
            "response_body_truncated": self.response_body_truncated,
            "response_body_base64": self.response_body_base64,
            "response_body_length": self.response_body_length,
        }


class NetworkCapture:
    """Capture and analyze network traffic via CDP.

    Usage:
        network = NetworkCapture(page)
        await network.enable()

        # ... page navigates and makes requests ...

        api_calls = network.get_api_calls(domain_filter="leadconnectorhq.com")
        tokens = network.find_auth_tokens()
    """

    _STATIC_EXTENSIONS = (
        ".js",
        ".css",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".svg",
        ".webp",
        ".map",
        ".mp4",
        ".webm",
        ".mp3",
        ".zip",
    )

    def __init__(
        self,
        page,
        *,
        capture_response_bodies: bool = True,
        max_response_body_chars: int = 200_000,
        max_post_data_chars: int = 50_000,
    ):
        self.page = page
        self.requests: dict[str, CapturedRequest] = {}
        self._enabled = False
        self.capture_response_bodies = capture_response_bodies
        self.max_response_body_chars = max_response_body_chars
        self.max_post_data_chars = max_post_data_chars

    def _is_static_resource(self, url: str) -> bool:
        url_l = (url or "").lower()
        return any(ext in url_l for ext in self._STATIC_EXTENSIONS)

    def _should_capture_body(self, url: str, response_headers: dict | None) -> bool:
        if not self.capture_response_bodies:
            return False
        if not isinstance(url, str) or not url:
            return False
        if self._is_static_resource(url):
            return False

        # Keep response bodies only for GHL backend-ish domains (helps avoid
        # huge HTML/static payloads that make session logs unusable).
        try:
            host = urlparse(url).netloc.lower()
        except Exception:
            host = ""
        if "leadconnectorhq.com" not in host:
            return False

        ct = ""
        content_length: int | None = None
        if isinstance(response_headers, dict):
            for k, v in response_headers.items():
                if isinstance(k, str) and k.lower() == "content-type" and isinstance(v, str):
                    ct = v.lower()
                if isinstance(k, str) and k.lower() == "content-length" and isinstance(v, str):
                    try:
                        content_length = int(v.strip())
                    except Exception:
                        content_length = None

        if isinstance(content_length, int) and content_length > self.max_response_body_chars:
            return False

        # Default to capturing if content-type is missing (some responses omit it),
        # otherwise only capture likely-text content.
        if not ct:
            return True
        return ("json" in ct) or ct.startswith("text/")

    async def enable(self):
        """Enable network monitoring."""
        if self._enabled:
            return

        try:
            await self.page.send(network.enable())

            # Add event handlers
            self.page.add_handler(network.RequestWillBeSent, self._on_request)
            self.page.add_handler(network.ResponseReceived, self._on_response)

            self._enabled = True
            print("Network capture enabled")
        except Exception as e:
            print(f"Warning: Could not enable network capture: {e}")

    async def _on_request(self, event: network.RequestWillBeSent):
        """Handle outgoing request."""
        try:
            post_data = event.request.post_data if hasattr(event.request, "post_data") else None
            if isinstance(post_data, str) and len(post_data) > self.max_post_data_chars:
                post_data = post_data[: self.max_post_data_chars] + "... [truncated]"

            req = CapturedRequest(
                request_id=str(event.request_id),
                url=event.request.url,
                method=event.request.method,
                headers=dict(event.request.headers) if event.request.headers else {},
                post_data=post_data,
            )
            self.requests[req.request_id] = req
        except Exception as e:
            print(f"Warning: Error capturing request: {e}")

    async def _on_response(self, event: network.ResponseReceived):
        """Handle incoming response."""
        try:
            request_id = str(event.request_id)
            if request_id in self.requests:
                req = self.requests[request_id]
                req.response_status = event.response.status
                req.response_headers = (
                    dict(event.response.headers) if event.response.headers else {}
                )

                if not self._should_capture_body(req.url, req.response_headers):
                    return

                # Try to get response body (may fail for some requests)
                try:
                    body_result = await self.page.send(network.get_response_body(event.request_id))
                    if not body_result:
                        return

                    body = getattr(body_result, "body", None)
                    base64_encoded = bool(
                        getattr(
                            body_result,
                            "base64_encoded",
                            getattr(body_result, "base64Encoded", False),
                        )
                    )

                    if base64_encoded:
                        req.response_body_base64 = True
                        req.response_body_length = len(body) if isinstance(body, str) else None
                        return

                    if isinstance(body, str):
                        req.response_body_length = len(body)
                        if len(body) > self.max_response_body_chars:
                            req.response_body = (
                                body[: self.max_response_body_chars] + "... [truncated]"
                            )
                            req.response_body_truncated = True
                        else:
                            req.response_body = body
                except Exception:
                    pass  # Body not available for all requests
        except Exception as e:
            print(f"Warning: Error capturing response: {e}")

    def get_requests(self) -> list[dict]:
        """Get all captured requests."""
        return [req.to_dict() for req in self.requests.values()]

    def get_api_calls(self, domain_filter: str | None = None) -> list[dict]:
        """Get API calls, optionally filtered by domain.

        Args:
            domain_filter: Only include requests containing this domain
        """
        api_calls = []

        for req in self.requests.values():
            # Skip static resources
            if any(
                ext in req.url.lower()
                for ext in self._STATIC_EXTENSIONS
            ):
                continue

            # Skip browser internal URLs
            if req.url.startswith("chrome://") or req.url.startswith("about:"):
                continue

            # Apply domain filter
            if domain_filter and domain_filter not in req.url:
                continue

            api_calls.append(req.to_dict())

        return api_calls

    def find_auth_tokens(self) -> dict[str, Any]:
        """Extract auth tokens from captured requests.

        Looks for:
        - Authorization headers (Bearer tokens)
        - Cookie tokens
        - Request/response body tokens
        """
        tokens = {}

        for req in self.requests.values():
            # Check Authorization header
            auth_header = req.headers.get("Authorization") or req.headers.get("authorization")
            if auth_header:
                if auth_header.startswith("Bearer "):
                    tokens["access_token"] = auth_header[7:]  # Remove "Bearer " prefix
                else:
                    tokens["authorization"] = auth_header

            # Check for token in response body (common for OAuth)
            if req.response_body:
                try:
                    body = json.loads(req.response_body)
                    if isinstance(body, dict):
                        for key in ["access_token", "accessToken", "token", "id_token", "refresh_token"]:
                            if key in body:
                                tokens[key] = body[key]

                        # Also capture location/user IDs
                        for key in ["locationId", "location_id", "userId", "user_id", "companyId"]:
                            if key in body:
                                tokens[key] = body[key]
                except (json.JSONDecodeError, TypeError):
                    pass

            # Check cookies
            cookie_header = req.headers.get("Cookie") or req.headers.get("cookie")
            if cookie_header and "token" not in tokens:
                # Parse cookies looking for auth tokens
                for cookie in cookie_header.split(";"):
                    cookie = cookie.strip()
                    if "=" in cookie:
                        name, value = cookie.split("=", 1)
                        name = name.strip().lower()
                        if any(auth_name in name for auth_name in ["token", "auth", "session", "jwt"]):
                            tokens[f"cookie_{name}"] = value

        return tokens

    def get_ghl_specific(self) -> dict:
        """Extract GHL-specific data from captured requests."""
        ghl_data = {
            "location_id": None,
            "user_id": None,
            "company_id": None,
            "api_endpoints": [],
            "auth": {},
        }

        for req in self.requests.values():
            url = req.url

            # GHL API calls
            if "leadconnectorhq.com" in url or "gohighlevel.com" in url:
                # Extract path
                if "leadconnectorhq.com" in url:
                    path = url.split("leadconnectorhq.com")[-1].split("?")[0]
                else:
                    path = url.split("gohighlevel.com")[-1].split("?")[0]

                endpoint = {
                    "method": req.method,
                    "path": path,
                    "url": url,
                    "status": req.response_status,
                }

                # Try to parse response for schema hints
                if req.response_body:
                    try:
                        body = json.loads(req.response_body)
                        if isinstance(body, dict):
                            endpoint["response_keys"] = list(body.keys())[:10]
                    except Exception:
                        pass

                ghl_data["api_endpoints"].append(endpoint)

            # Look for IDs in URL params
            if "locationId=" in url:
                loc_id = url.split("locationId=")[1].split("&")[0]
                ghl_data["location_id"] = loc_id

        # Get auth tokens
        ghl_data["auth"] = self.find_auth_tokens()

        return ghl_data

    def export_har(self, filepath: str):
        """Export captured traffic as HAR (HTTP Archive) format."""
        har = {
            "log": {
                "version": "1.2",
                "creator": {"name": "MaxLevel", "version": "0.1.0"},
                "entries": [],
            }
        }

        for req in self.requests.values():
            entry = {
                "startedDateTime": req.timestamp,
                "request": {
                    "method": req.method,
                    "url": req.url,
                    "headers": [{"name": k, "value": v} for k, v in req.headers.items()],
                    "postData": {"text": req.post_data} if req.post_data else None,
                },
                "response": {
                    "status": req.response_status or 0,
                    "headers": (
                        [{"name": k, "value": v} for k, v in req.response_headers.items()]
                        if req.response_headers
                        else []
                    ),
                    "content": {"text": req.response_body} if req.response_body else {},
                },
            }
            har["log"]["entries"].append(entry)

        with open(filepath, "w") as f:
            json.dump(har, f, indent=2)

        print(f"HAR file exported: {filepath}")

    def clear(self):
        """Clear captured requests."""
        self.requests.clear()
