"""Screenshot utilities for browser agent."""

import base64
from pathlib import Path

import nodriver.cdp.page as page_cdp


async def take_screenshot(page, filepath: str | Path, full_page: bool = False) -> str:
    """Take a screenshot of the current page.

    Args:
        page: nodriver page/tab object
        filepath: Where to save the screenshot
        full_page: Whether to capture the full scrollable page

    Returns:
        Path to the saved screenshot
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Use CDP directly for more control
        if full_page:
            # Capture beyond viewport
            screenshot_data = await page.send(
                page_cdp.capture_screenshot(
                    format_="png",
                    capture_beyond_viewport=True,
                )
            )
        else:
            # Just the viewport
            screenshot_data = await page.send(
                page_cdp.capture_screenshot(format_="png")
            )

        # Decode and save
        image_data = base64.b64decode(screenshot_data.data)
        with open(filepath, "wb") as f:
            f.write(image_data)

        return str(filepath)

    except Exception as e:
        # Fallback to nodriver's built-in method
        try:
            await page.save_screenshot(str(filepath))
            return str(filepath)
        except Exception as e2:
            raise Exception(f"Failed to take screenshot: {e}, fallback also failed: {e2}")


async def get_screenshot_base64(page, full_page: bool = False) -> str:
    """Get screenshot as base64 string (useful for API responses).

    Args:
        page: nodriver page/tab object
        full_page: Whether to capture the full scrollable page

    Returns:
        Base64 encoded PNG image
    """
    try:
        if full_page:
            screenshot_data = await page.send(
                page_cdp.capture_screenshot(
                    format_="png",
                    capture_beyond_viewport=True,
                )
            )
        else:
            screenshot_data = await page.send(
                page_cdp.capture_screenshot(format_="png")
            )

        return screenshot_data.data

    except Exception as e:
        raise Exception(f"Failed to capture screenshot: {e}")


async def get_element_screenshot(page, selector: str, filepath: str | Path) -> str:
    """Take a screenshot of a specific element.

    Args:
        page: nodriver page/tab object
        selector: CSS selector for the element
        filepath: Where to save the screenshot

    Returns:
        Path to the saved screenshot
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    try:
        element = await page.select(selector)
        if not element:
            raise Exception(f"Element not found: {selector}")

        # Get element bounding box
        box = await page.evaluate(f"""
            (() => {{
                const el = document.querySelector('{selector}');
                if (!el) return null;
                const rect = el.getBoundingClientRect();
                return {{
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height
                }};
            }})()
        """)

        if not box:
            raise Exception(f"Could not get bounding box for: {selector}")

        # Capture with clip
        screenshot_data = await page.send(
            page_cdp.capture_screenshot(
                format_="png",
                clip=page_cdp.Viewport(
                    x=box["x"],
                    y=box["y"],
                    width=box["width"],
                    height=box["height"],
                    scale=1,
                ),
            )
        )

        image_data = base64.b64decode(screenshot_data.data)
        with open(filepath, "wb") as f:
            f.write(image_data)

        return str(filepath)

    except Exception as e:
        raise Exception(f"Failed to capture element screenshot: {e}")
