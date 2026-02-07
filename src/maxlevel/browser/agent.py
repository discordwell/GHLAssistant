"""Browser automation agent with screenshot and network capture."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

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

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()

    async def start(self):
        """Start the browser with persistent profile."""
        config = uc.Config()
        config.sandbox = False  # Required on macOS
        config.user_data_dir = str(self.profile_dir)
        config.headless = self.headless

        self.browser = await uc.start(config=config)

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

    async def navigate(self, url: str) -> dict:
        """Navigate to a URL and return page state."""
        print(f"Navigating to: {url}")
        self.page = await self.browser.get(url)

        # Re-enable network capture on new page
        if self.capture_network and self.network:
            await self.network.enable()

        await self._wait_for_load()
        return await self.get_page_state()

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
        return await self.page.evaluate(js_code)

    async def is_logged_in(self, login_indicators: list[str] = None) -> bool:
        """Check if user appears to be logged in.

        Args:
            login_indicators: URL patterns that indicate NOT logged in
        """
        if login_indicators is None:
            login_indicators = ["/login", "/signin", "/oauth", "/auth"]

        state = await self.get_page_state()
        url = state.get("url", "").lower()

        return not any(indicator in url for indicator in login_indicators)

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

        session_data = {
            "profile": self.profile_name,
            "captured_at": datetime.now().isoformat(),
            "page_state": await self.get_page_state(),
            "screenshots": self.screenshots,
            "auth": self.get_auth_tokens(),
            "api_calls": self.get_api_calls(),
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
                await asyncio.sleep(duration)
            except KeyboardInterrupt:
                print("\nCapture interrupted by user")
        else:
            print("\nCapturing traffic until browser is closed...")
            print("Close the browser window or press Ctrl+C to stop.\n")

            try:
                # Keep running until interrupted
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\nCapture stopped")

        # Export session
        output_path = await agent.export_session(output)

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
