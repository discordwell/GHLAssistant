"""Browser automation agent with screenshot and network capture."""

import asyncio
import base64
import json
import os
import signal
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import nodriver as uc

from .network import NetworkCapture
from .screenshots import take_screenshot

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"


class BrowserAgent:
    """Browser automation agent with screenshot and network capture.

    Usage:
        async with BrowserAgent(profile="ghl_session") as agent:
            await agent.navigate("https://app.gohighlevel.com/")
            state = await agent.get_page_state()
            print(state)
    """

    def __init__(
        self,
        profile_name: str = "default",
        headless: bool = False,
        capture_network: bool = True,
    ):
        self.profile_name = profile_name
        self.headless = headless
        self.capture_network = capture_network

        self.browser = None
        self.page = None
        self.network: NetworkCapture | None = None

        # Directories
        self.profile_dir = DATA_DIR / "browser_profiles" / profile_name
        self.screenshot_dir = DATA_DIR / "screenshots"
        self.network_dir = DATA_DIR / "network_logs"

        # Ensure directories exist
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.network_dir.mkdir(parents=True, exist_ok=True)

        self.screenshots: list[str] = []
        # When we attach to an existing DevTools session (connect_existing=True),
        # nodriver won't own the subprocess and can't reliably terminate it.
        # Track it so we can clean up on stop.
        self._external_debug_port: int | None = None
        self._external_chrome_pids: list[int] = []

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()

    def _find_chrome_pids_for_profile(self, *, port: int, profile_dir: str) -> list[int]:
        """Best-effort: find Chrome PIDs for a given DevTools port + user-data-dir."""
        try:
            out = subprocess.check_output(
                ["ps", "-ax", "-o", "pid=,command="],
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            return []

        want_port = f"--remote-debugging-port={port}"
        want_dir = f"--user-data-dir={profile_dir}"

        pids: list[int] = []
        for raw_line in out.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # pid and command are separated by whitespace; pid is first token.
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            pid_s, cmd = parts
            if want_port not in cmd:
                continue
            if want_dir not in cmd:
                continue
            try:
                pids.append(int(pid_s))
            except ValueError:
                continue

        return pids

    def _kill_pids(self, pids: list[int]) -> None:
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                continue
            except PermissionError:
                continue
            except Exception:
                continue

    async def _wait_for_devtools(self, *, host: str, port: int, timeout_seconds: float) -> bool:
        url = f"http://{host}:{port}/json/version"
        deadline = datetime.now().timestamp() + float(timeout_seconds)

        def _probe() -> bool:
            with urllib.request.urlopen(url, timeout=1) as resp:
                resp.read(1)
            return True

        while datetime.now().timestamp() < deadline:
            try:
                await asyncio.get_running_loop().run_in_executor(None, _probe)
                return True
            except Exception:
                await asyncio.sleep(0.25)
        return False

    async def start(self):
        """Start the browser with persistent profile."""
        # nodriver can occasionally race Chrome startup and fail its initial
        # connection attempt; when that happens, Chrome may still be launching.
        # We'll retry and/or attach to the spawned DevTools port.
        last_exc: Exception | None = None
        for attempt in range(1, 4):
            config = uc.Config()
            config.sandbox = False  # Adds --no-sandbox when False.
            config.user_data_dir = str(self.profile_dir)
            config.headless = self.headless

            try:
                self.browser = await uc.start(config=config)
                self._external_debug_port = None
                self._external_chrome_pids = []
                break
            except Exception as exc:
                last_exc = exc
                message = str(exc)
                if "Failed to connect to browser" not in message:
                    raise

                host = getattr(config, "host", None)
                port = getattr(config, "port", None)
                if isinstance(host, str) and host and isinstance(port, int) and port:
                    # If Chrome is still coming up, wait a bit longer for DevTools.
                    if await self._wait_for_devtools(host=host, port=port, timeout_seconds=15.0):
                        pids = self._find_chrome_pids_for_profile(
                            port=port,
                            profile_dir=str(self.profile_dir),
                        )
                        try:
                            self.browser = await uc.start(host=host, port=port)
                            self._external_debug_port = port
                            self._external_chrome_pids = pids
                            break
                        except Exception:
                            # If attach failed, kill any strays we can identify and retry.
                            self._kill_pids(pids)

                # Backoff before retrying a fresh launch.
                await asyncio.sleep(min(2.0, 0.5 * attempt))

        if not self.browser:
            raise last_exc or RuntimeError("Failed to start browser")

        # Get the main page/tab
        self.page = await self.browser.get("about:blank")

        # Enable network capture if requested
        if self.capture_network:
            self.network = NetworkCapture(self.page)
            await self.network.enable()

        print(f"Browser started with profile: {self.profile_name}")

    async def stop(self):
        """Stop the browser."""
        if self.browser:
            self.browser.stop()
            print("Browser stopped")
        # If we attached to an existing session, ensure the subprocess is terminated.
        if self._external_debug_port:
            pids = self._external_chrome_pids or self._find_chrome_pids_for_profile(
                port=self._external_debug_port,
                profile_dir=str(self.profile_dir),
            )
            self._kill_pids(pids)
            self._external_debug_port = None
            self._external_chrome_pids = []

    async def navigate(self, url: str) -> dict:
        """Navigate to a URL and return page state."""
        normalized = self._normalize_app_url(url)
        if normalized != url:
            print(f"Navigating to: {url} (rewrote to: {normalized})")
            url = normalized
        else:
            print(f"Navigating to: {url}")
        # Reuse the existing tab when possible. Creating a new tab would detach
        # previously-registered CDP handlers and make network capture unreliable.
        if self.page is not None:
            await self.page.get(url)
        else:
            self.page = await self.browser.get(url)

        # Ensure network capture is enabled on the active page.
        if self.capture_network:
            if not self.network or self.network.page is not self.page:
                self.network = NetworkCapture(self.page)
            await self.network.enable()

        await self._wait_for_load()
        return await self.get_page_state()

    def _normalize_app_url(self, url: str) -> str:
        """Rewrite some GHL app URLs to deep-link form.

        As of early 2026, many UI routes on app.gohighlevel.com (e.g. /contacts/)
        return 404 when fetched directly. The web app supports deep linking via:

            https://app.gohighlevel.com/?url=%2Fcontacts%2F
        """
        if not isinstance(url, str) or not url:
            return url

        try:
            parsed = urlparse(url)
        except Exception:
            return url

        if parsed.scheme not in {"http", "https"}:
            return url
        if parsed.netloc != "app.gohighlevel.com":
            return url

        # Location-scoped routes generally work as direct paths and should not be
        # rewritten to deep-link form (doing so can trigger redirects back to the
        # agency launchpad for some accounts).
        if parsed.path.startswith("/location/"):
            return url

        # Already on root (including existing deep links like /?url=...).
        if parsed.path in {"", "/"}:
            return url

        # Don't rewrite obvious static assets.
        path_l = parsed.path.lower()
        if any(
            path_l.endswith(ext)
            for ext in (
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
            )
        ):
            return url

        inner = parsed.path
        if parsed.query:
            inner += f"?{parsed.query}"
        if parsed.fragment:
            inner += f"#{parsed.fragment}"

        # Encode everything, including slashes, to match GHL's expected format.
        return f"{parsed.scheme}://{parsed.netloc}/?url={quote(inner, safe='')}"

    async def _wait_for_load(self, timeout: float = 10.0):
        """Wait for page to finish loading."""
        try:
            # Wait for document ready state
            for _ in range(int(timeout * 2)):
                ready_state = await self.page.evaluate("document.readyState")
                if ready_state == "complete":
                    break
                await asyncio.sleep(0.5)
        except Exception:
            pass  # Best effort

    async def get_page_state(self) -> dict:
        """Get current page state."""
        try:
            url = await self.page.evaluate("window.location.href")
            title = await self.page.evaluate("document.title")

            return {
                "url": url,
                "title": title,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"error": str(e)}

    async def screenshot(self, name: str | None = None) -> str:
        """Take a screenshot and return the file path."""
        if name is None:
            name = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        filepath = self.screenshot_dir / f"{name}.png"
        await take_screenshot(self.page, filepath)

        self.screenshots.append(str(filepath))
        print(f"Screenshot saved: {filepath}")
        return str(filepath)

    async def click(self, selector: str) -> dict:
        """Click an element by CSS selector."""
        try:
            element = await self.page.select(selector)
            if element:
                await element.click()
                await asyncio.sleep(0.5)  # Wait for any reactions
                return {"success": True, "selector": selector}
            return {"success": False, "error": f"Element not found: {selector}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def type_text(self, selector: str, text: str) -> dict:
        """Type text into an element."""
        try:
            element = await self.page.select(selector)
            if element:
                await element.send_keys(text)
                return {"success": True, "selector": selector}
            return {"success": False, "error": f"Element not found: {selector}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def wait_for(self, selector: str, timeout: int = 30) -> bool:
        """Wait for an element to appear."""
        for _ in range(timeout * 2):
            try:
                element = await self.page.select(selector)
                if element:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return False

    async def evaluate(self, js_code: str) -> Any:
        """Execute JavaScript and return result."""
        value = await self.page.evaluate(js_code)
        return self._unwrap_eval_value(value)

    @staticmethod
    def _unwrap_eval_value(value: Any) -> Any:
        """Best-effort normalization of nodriver's evaluate return values.

        nodriver returns primitives as Python values, but represents:
        - Arrays as lists of {"type": ..., "value": ...} items
        - Objects as lists of [key, {"type": ..., "value": ...}] pairs
        """
        if isinstance(value, dict):
            # RemoteObject-like wrapper.
            if value.get("type") in {"null", "undefined"} and "value" not in value:
                return None
            if "type" in value and "value" in value and len(value) <= 4:
                return BrowserAgent._unwrap_eval_value(value.get("value"))
            return {k: BrowserAgent._unwrap_eval_value(v) for k, v in value.items()}

        if isinstance(value, list):
            # Object represented as list of [key, value] pairs.
            if value and all(
                isinstance(item, (list, tuple))
                and len(item) == 2
                and isinstance(item[0], str)
                for item in value
            ):
                return {item[0]: BrowserAgent._unwrap_eval_value(item[1]) for item in value}
            return [BrowserAgent._unwrap_eval_value(item) for item in value]

        return value

    async def get_cookies(self) -> dict[str, str]:
        """Return current document/URL cookies as a simple name->value dict.

        Uses `document.cookie` first (fast, but excludes HttpOnly cookies),
        then merges CDP `Network.getCookies` (may include HttpOnly cookies).
        """
        cookies: dict[str, str] = {}

        try:
            raw = await self.evaluate("document.cookie")
            if isinstance(raw, dict) and raw.get("type") == "string":
                raw = raw.get("value")
            if isinstance(raw, str) and raw:
                for part in raw.split(";"):
                    part = part.strip()
                    if not part or "=" not in part:
                        continue
                    name, value = part.split("=", 1)
                    cookies[name] = value
        except Exception:
            pass

        # Always merge CDP cookies as well (may include HttpOnly cookies not present
        # in document.cookie). This significantly improves auth capture reliability.
        try:
            import nodriver.cdp.network as cdp_network

            url = None
            try:
                url = await self.page.evaluate("window.location.href")
            except Exception:
                url = None

            kwargs: dict[str, Any] = {}
            if isinstance(url, str) and url:
                kwargs["urls"] = [url]

            cookie_objs = await self.page.send(cdp_network.get_cookies(**kwargs))
            for cookie in cookie_objs:
                name = getattr(cookie, "name", None)
                value = getattr(cookie, "value", None)
                if isinstance(name, str) and name and isinstance(value, str):
                    cookies.setdefault(name, value)
        except Exception:
            pass

        return cookies

    async def extract_cookie_auth(self) -> dict[str, Any] | None:
        """Extract API auth context from known GHL cookies.

        GHL sets:
        - `m_a`: short-lived JWT used as Bearer token for backend.leadconnectorhq.com
        - `a`: base64url JSON with `companyId`, `userId`, `apiKey`

        Returns:
            dict with keys: access_token, company_id, user_id, api_key (best-effort)
            or None if nothing usable is found.
        """
        cookies = await self.get_cookies()
        if not cookies:
            return None

        access_token = cookies.get("m_a")
        if not isinstance(access_token, str) or access_token.count(".") < 2:
            access_token = None

        company_id = None
        user_id = None
        api_key = None

        raw_a = cookies.get("a")
        if isinstance(raw_a, str) and raw_a:
            try:
                padding = "=" * ((4 - (len(raw_a) % 4)) % 4)
                decoded = base64.urlsafe_b64decode(raw_a + padding)
                payload = json.loads(decoded)
                if isinstance(payload, dict):
                    api_key = payload.get("apiKey") if isinstance(payload.get("apiKey"), str) else None
                    user_id = payload.get("userId") if isinstance(payload.get("userId"), str) else None
                    company_id = (
                        payload.get("companyId") if isinstance(payload.get("companyId"), str) else None
                    )
            except Exception:
                pass

        if not (access_token or company_id or user_id):
            return None

        return {
            "access_token": access_token,
            "company_id": company_id,
            "user_id": user_id,
            "api_key": api_key,
        }

    async def login_ghl(
        self,
        email: str,
        password: str,
        *,
        timeout_seconds: int = 120,
        url: str = "https://app.gohighlevel.com/",
    ) -> dict[str, Any]:
        """Attempt to log into GHL using email/password in the current profile.

        This is best-effort: GHL may present captchas/2FA flows that require
        manual intervention. In those cases, keep the window open (headless=False)
        and complete the flow; token capture will still work via cookies.
        """
        await self.navigate(url)
        await asyncio.sleep(1)

        fill_js = f"""
        (() => {{
          const email = {json.dumps(email)};
          const password = {json.dumps(password)};

          const emailInput = document.querySelector(
            "input[type='email'], input[name*='email' i], input[id*='email' i], input[placeholder*='email' i]"
          );
          const pwInput = document.querySelector(
            "input[type='password'], input[name*='password' i], input[id*='password' i], input[placeholder*='password' i]"
          );

          if (emailInput) {{
            emailInput.focus();
            emailInput.value = email;
            emailInput.dispatchEvent(new Event("input", {{ bubbles: true }}));
            emailInput.dispatchEvent(new Event("change", {{ bubbles: true }}));
          }}

          if (pwInput) {{
            pwInput.focus();
            pwInput.value = password;
            pwInput.dispatchEvent(new Event("input", {{ bubbles: true }}));
            pwInput.dispatchEvent(new Event("change", {{ bubbles: true }}));
          }}

          const buttons = Array.from(document.querySelectorAll("button,input[type='submit']"));
          const signIn = buttons.find((el) => {{
            const t = ((el.innerText || el.value || "").trim()).toLowerCase();
            return t === "sign in" || t === "log in" || t.includes("sign in") || t.includes("log in");
          }});

          if (signIn) {{
            try {{
              signIn.scrollIntoView({{ behavior: "auto", block: "center" }});
            }} catch (e) {{}}
            try {{
              signIn.click();
            }} catch (e) {{
              return {{ ok: false, reason: String(e), hasEmail: !!emailInput, hasPassword: !!pwInput }};
            }}
          }}

          return {{
            ok: true,
            hasEmail: !!emailInput,
            hasPassword: !!pwInput,
            clicked: !!signIn
          }};
        }})()
        """

        try:
            fill_result = await self.evaluate(fill_js)
        except Exception as exc:
            return {"success": False, "error": f"login form interaction failed: {exc}"}

        # Wait for auth state to flip. If captchas/2FA appear, this will timeout.
        start = datetime.now().timestamp()
        last_state: dict[str, Any] | None = None
        while datetime.now().timestamp() - start < float(timeout_seconds):
            try:
                last_state = await self.get_page_state()
            except Exception:
                last_state = None

            try:
                if await self.is_logged_in():
                    return {
                        "success": True,
                        "fill_result": fill_result,
                        "page_state": last_state,
                    }
            except Exception:
                # If the login page is transitioning, checks can throw; retry.
                pass

            await asyncio.sleep(2)

        screenshot_path = None
        try:
            screenshot_path = await self.screenshot("ghl_login_timeout")
        except Exception:
            pass

        return {
            "success": False,
            "error": "Login timeout (may require manual captcha/2FA)",
            "fill_result": fill_result,
            "page_state": last_state,
            "screenshot": screenshot_path,
        }

    async def is_logged_in(self, login_indicators: list[str] = None) -> bool:
        """Check if user appears to be logged in.

        Args:
            login_indicators: URL patterns that indicate NOT logged in
        """
        if login_indicators is None:
            login_indicators = ["/login", "/signin", "/oauth", "/auth"]

        state = await self.get_page_state()
        url = state.get("url", "").lower()

        if any(indicator in url for indicator in login_indicators):
            return False

        # Some GHL login screens render at "/" without explicit login path.
        # Probe for login-form markers and token presence before assuming auth.
        login_check_js = """
        (() => {
            try {
                const bodyText = (document.body?.innerText || "").toLowerCase();
                const hasPasswordInput = !!document.querySelector(
                    "input[type='password'], input[name*='password' i], input[id*='password' i]"
                );
                const hasEmailInput = !!document.querySelector(
                    "input[type='email'], input[name*='email' i], input[id*='email' i]"
                );
                const hasLoginButton = Array.from(document.querySelectorAll("button,a,input[type='submit']"))
                    .some((el) => {
                        const text = ((el.innerText || el.value || "").trim()).toLowerCase();
                        return text.includes("sign in")
                            || text.includes("log in")
                            || text.includes("continue with");
                    });
                const bodyLooksLikeLogin = bodyText.includes("sign into your account")
                    || bodyText.includes("forgot password")
                    || bodyText.includes("continue with google")
                    || bodyText.includes("continue with apple");

                let hasAuthToken = false;
                try {
                    const vueStoreToken =
                        document.querySelector("#app")?.__vue_app__?.config?.globalProperties?.$store?.state?.auth?.user?.authToken;
                    hasAuthToken = hasAuthToken || !!vueStoreToken;

                    const nuxtToken = window.__NUXT__?.state?.auth?.user?.authToken;
                    hasAuthToken = hasAuthToken || !!nuxtToken;

                    const sources = [window.localStorage, window.sessionStorage];
                    for (const src of sources) {
                        for (let i = 0; i < src.length; i++) {
                            const key = src.key(i) || "";
                            const value = src.getItem(key) || "";
                            if (/token|auth|jwt|access/i.test(key) && value.length > 80) {
                                hasAuthToken = true;
                                break;
                            }
                            if (/eyJ[A-Za-z0-9_-]+\\./.test(value)) {
                                hasAuthToken = true;
                                break;
                            }
                        }
                        if (hasAuthToken) break;
                    }
                } catch (e) {
                    /* ignore token extraction issues */
                }

                return {
                    looksLikeLogin: !!(
                        bodyLooksLikeLogin
                        || (hasPasswordInput && hasEmailInput)
                        || (hasPasswordInput && hasLoginButton)
                    ),
                    hasAuthToken
                };
            } catch (e) {
                return { looksLikeLogin: false, hasAuthToken: false };
            }
        })()
        """

        try:
            check = await self.evaluate(login_check_js)
            if isinstance(check, dict):
                if bool(check.get("looksLikeLogin")):
                    return False
                if bool(check.get("hasAuthToken")):
                    return True

                # GHL often authenticates purely via cookies (m_a), so auth tokens may
                # not be present in localStorage/sessionStorage. Fall back to cookie
                # inspection when the page does not look like a login form.
                try:
                    cookie_auth = await self.extract_cookie_auth()
                    token = cookie_auth.get("access_token") if cookie_auth else None
                    if isinstance(token, str) and token.count(".") >= 2:
                        try:
                            # Best-effort expiry check (30s buffer).
                            payload_b64 = token.split(".")[1]
                            padding = "=" * ((4 - (len(payload_b64) % 4)) % 4)
                            payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
                            exp = payload.get("exp") if isinstance(payload, dict) else None
                            if isinstance(exp, (int, float)):
                                now = datetime.now().timestamp()
                                return int(exp) > int(now) + 30
                        except Exception:
                            # If we can't decode exp, still treat cookie token as a sign-in hint.
                            return True
                    if isinstance(token, str) and token:
                        return True
                except Exception:
                    pass

                return False
            if isinstance(check, bool):
                return not check
        except Exception:
            pass

        return False

    async def safe_action(self, action_fn, description: str) -> dict:
        """Execute an action with automatic screenshot on failure."""
        try:
            result = await action_fn()
            return {"success": True, "result": result}
        except Exception as e:
            screenshot_path = await self.screenshot(f"error_{description}")
            page_state = await self.get_page_state()
            return {
                "success": False,
                "error": str(e),
                "screenshot": screenshot_path,
                "page_state": page_state,
            }

    async def extract_vue_token(self) -> dict | None:
        """Extract authToken from GHL's Vue store.

        Retries up to 3 times with 2s delay (Vue store may not be populated
        immediately after page load).

        Returns:
            dict with authToken, companyId, userId or None if extraction fails
        """
        js = """
        (function() {
            try {
                var app = document.querySelector('#app');
                if (!app || !app.__vue_app__) return null;
                var store = app.__vue_app__.config.globalProperties.$store;
                if (!store) return null;
                var user = store.state.auth && store.state.auth.user;
                if (!user || !user.authToken) return null;
                return {
                    authToken: user.authToken,
                    companyId: user.companyId || null,
                    userId: user.id || null
                };
            } catch(e) { return null; }
        })()
        """
        for attempt in range(3):
            try:
                result = await self.evaluate(js)
                if result and result.get("authToken"):
                    return result
            except Exception:
                pass
            if attempt < 2:
                await asyncio.sleep(2)
        return None

    def get_network_log(self) -> list[dict]:
        """Get captured network requests."""
        if self.network:
            return self.network.get_requests()
        return []

    def get_api_calls(self, domain_filter: str | None = None) -> list[dict]:
        """Get API calls, optionally filtered by domain."""
        if self.network:
            return self.network.get_api_calls(domain_filter)
        return []

    def get_auth_tokens(self) -> dict:
        """Extract auth tokens from captured requests."""
        if self.network:
            return self.network.find_auth_tokens()
        return {}

    async def export_session(self, output_path: str | None = None) -> str:
        """Export session data (network log, screenshots, state)."""
        if output_path is None:
            output_path = str(
                self.network_dir / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

        cookie_auth = None
        try:
            cookie_auth = await self.extract_cookie_auth()
        except Exception:
            cookie_auth = None

        session_data = {
            "profile": self.profile_name,
            "captured_at": datetime.now().isoformat(),
            "page_state": await self.get_page_state(),
            "screenshots": self.screenshots,
            "auth": self.get_auth_tokens(),
            "cookie_auth": cookie_auth,
            "api_calls": self.get_api_calls(),
            "network_log": self.get_network_log(),
            "network_log_count": len(self.get_network_log()),
        }

        with open(output_path, "w") as f:
            json.dump(session_data, f, indent=2, default=str)

        print(f"Session exported: {output_path}")
        return output_path


async def run_capture_session(
    url: str = "https://app.gohighlevel.com/",
    profile: str = "ghl_session",
    duration: int = 300,
    output: str | None = None,
) -> dict:
    """Run a capture session - opens browser, captures traffic for specified duration.

    Args:
        url: Starting URL
        profile: Browser profile name (for cookie persistence)
        duration: How long to capture (seconds), 0 = until manual close
        output: Output file path for session data
    """
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _handle_signal(_signum, _frame=None) -> None:
        # Background jobs can ignore SIGINT; handle SIGTERM/SIGINT explicitly so
        # users can stop capture and still get a session file written.
        try:
            loop.call_soon_threadsafe(stop_event.set)
        except Exception:
            try:
                stop_event.set()
            except Exception:
                pass

    prev_int = None
    prev_term = None
    try:
        prev_int = signal.getsignal(signal.SIGINT)
        prev_term = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except Exception:
        prev_int = None
        prev_term = None

    try:
        async with BrowserAgent(profile_name=profile, capture_network=True) as agent:
            # Navigate to URL
            state = await agent.navigate(url)
            print(f"Page loaded: {state.get('title', 'Unknown')}")

            # Check login state
            if not await agent.is_logged_in():
                print("\n" + "=" * 60)
                print("NOT LOGGED IN - Please log in manually in the browser")
                print("The session will be saved for future use.")
                print("=" * 60 + "\n")

            if duration > 0:
                print(f"\nCapturing traffic for {duration} seconds...")
                print("Interact with the application in the browser.")
                print("Press Ctrl+C to stop early.\n")

                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=float(duration))
                    print("\nCapture stopped")
                except asyncio.TimeoutError:
                    pass
                except KeyboardInterrupt:
                    print("\nCapture interrupted by user")
            else:
                print("\nCapturing traffic until browser is closed...")
                print("Close the browser window or press Ctrl+C to stop.\n")

                try:
                    await stop_event.wait()
                    print("\nCapture stopped")
                except KeyboardInterrupt:
                    print("\nCapture stopped")

            # Export session
            output_path = await agent.export_session(output)

            # Persist the captured token into TokenManager storage so future
            # `GHLClient.from_session()` calls won't accidentally use a stale token.
            try:
                from ..auth.manager import TokenManager

                TokenManager().save_session_from_file(output_path)
            except Exception:
                pass

            # Summary
            api_calls = agent.get_api_calls()
            auth = agent.get_auth_tokens()

            print("\n" + "=" * 60)
            print("CAPTURE SUMMARY")
            print("=" * 60)
            print(f"API calls captured: {len(api_calls)}")
            print(f"Auth tokens found: {len(auth)}")
            print(f"Screenshots taken: {len(agent.screenshots)}")
            print(f"Session file: {output_path}")

            if auth:
                print("\nAuth tokens:")
                for key, value in auth.items():
                    # Truncate tokens for display
                    display_val = value[:50] + "..." if len(str(value)) > 50 else value
                    print(f"  {key}: {display_val}")

            return {
                "success": True,
                "output": output_path,
                "api_calls": len(api_calls),
                "auth_tokens": auth,
            }
    finally:
        # Restore original handlers (best-effort).
        try:
            if prev_int is not None:
                signal.signal(signal.SIGINT, prev_int)
            if prev_term is not None:
                signal.signal(signal.SIGTERM, prev_term)
        except Exception:
            pass
