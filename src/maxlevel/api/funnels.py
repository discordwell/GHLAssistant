"""Funnels API - Funnel and page operations for GHL."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .client import GHLClient


class FunnelsAPI:
    """Funnels API for GoHighLevel.

    Usage:
        async with GHLClient.from_session() as ghl:
            # List funnels
            funnels = await ghl.funnels.list()

            # Get funnel details
            funnel = await ghl.funnels.get("funnel_id")

            # Get funnel pages
            pages = await ghl.funnels.pages("funnel_id")
    """

    def __init__(self, client: "GHLClient"):
        self._client = client
        # Cache page lists for the duration of a client context. Some endpoints
        # (e.g. /funnels/page/list) return the entire list with no pagination,
        # while our sync engine expects limit/offset pagination.
        self._pages_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

    @property
    def _location_id(self) -> str:
        lid = self._client.config.location_id
        if not lid:
            raise ValueError("location_id required")
        return lid

    async def list(
        self,
        location_id: str | None = None,
        *,
        limit: int = 100,
        offset: int = 0,
        max_pages: int = 50,
        type: str = "funnel",
        category: str = "all",
    ) -> dict[str, Any]:
        """List all funnels for location.

        Returns:
            {"funnels": [{"_id": ..., "name": ..., "steps": [...], ...}, ...]}
        """
        lid = location_id or self._location_id

        # The legacy `/funnels/` endpoint often returns `{"products": ...}` and
        # not actual funnels. The UI uses `/funnels/funnel/list`.
        all_funnels: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        current_offset = max(0, int(offset))
        page_limit = max(1, int(limit))
        total_count: int | None = None

        for _ in range(max(1, int(max_pages))):
            resp = await self._client._get(
                "/funnels/funnel/list",
                locationId=lid,
                type=type,
                category=category,
                offset=current_offset,
                limit=page_limit,
            )
            funnels = resp.get("funnels", [])
            if not isinstance(funnels, list) or not funnels:
                # Preserve metadata but return a stable shape.
                return {
                    "funnels": all_funnels,
                    "total": total_count or len(all_funnels),
                }

            new_count = 0
            for f in funnels:
                if not isinstance(f, dict):
                    continue
                fid = cast(str, f.get("_id") or f.get("id") or "")
                if fid:
                    if fid in seen_ids:
                        continue
                    seen_ids.add(fid)
                all_funnels.append(f)
                new_count += 1

            # Defensive guard when the API ignores offsets.
            if new_count == 0:
                break

            count = resp.get("count")
            if isinstance(count, int) and count >= 0:
                total_count = count
                if len(all_funnels) >= total_count:
                    break

            # If response gives fewer than requested, we're done.
            if len(funnels) < page_limit:
                break

            current_offset += len(funnels)

        return {
            "funnels": all_funnels,
            "total": total_count or len(all_funnels),
        }

    async def get(self, funnel_id: str) -> dict[str, Any]:
        """Get funnel details.

        Args:
            funnel_id: The funnel ID

        Returns:
            {"funnel": {...}} with full funnel configuration
        """
        resp = await self._client._get(f"/funnels/funnel/fetch/{funnel_id}")
        if isinstance(resp, dict) and isinstance(resp.get("data"), dict):
            return {"funnel": resp["data"]}
        return {"funnel": resp if isinstance(resp, dict) else {}}

    async def pages(
        self,
        funnel_id: str,
        limit: int = 50,
        offset: int = 0,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        """Get pages within a funnel.

        Args:
            funnel_id: The funnel ID
            limit: Max pages to return
            offset: Pagination offset
            location_id: Override default location

        Returns:
            {"pages": [{"_id": ..., "name": ..., "path": ..., ...}, ...]}
        """
        lid = location_id or self._location_id
        key = (lid, funnel_id)
        pages = self._pages_cache.get(key)
        if pages is None:
            # This endpoint returns a JSON list, not a dict.
            resp: Any = await self._client._get(
                "/funnels/page/list",
                funnelId=funnel_id,
                locationId=lid,
            )
            if isinstance(resp, list):
                pages = [p for p in resp if isinstance(p, dict)]
            elif isinstance(resp, dict) and isinstance(resp.get("pages"), list):
                pages = [p for p in resp.get("pages", []) if isinstance(p, dict)]
            else:
                pages = []
            self._pages_cache[key] = pages

        lim = max(1, int(limit))
        off = max(0, int(offset))
        batch = pages[off : off + lim] if pages else []
        return {"pages": batch, "total": len(pages)}

    async def get_page(self, funnel_id: str, page_id: str) -> dict[str, Any]:
        """Get a specific page within a funnel.

        Args:
            funnel_id: The funnel ID
            page_id: The page ID

        Returns:
            {"page": {...}} with full page configuration
        """
        # Observed UI endpoint (early 2026): `/funnels/page/<pageId>`
        # Note: `funnel_id` is unused by the backend route.
        resp: Any = await self._client._get(f"/funnels/page/{page_id}")
        if isinstance(resp, dict):
            return {"page": resp}
        return {"page": {}}

    async def get_page_builder_meta(self, page_id: str) -> dict[str, Any]:
        """Get funnel page builder metadata by page id.

        This endpoint is used by the page builder UI and can include fields
        like `pageDataUrl` / `pageDataDownloadUrl` pointing to the builder JSON.

        Args:
            page_id: Funnel page ID

        Returns:
            dict (best-effort) with page builder metadata.
        """
        return await self._client._get(f"/funnels/page/{page_id}")
