"""Asset downloader with streaming + blobstore writes."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import unquote, urlparse

import httpx

from .blobstore import Sha256BlobStore, BlobWriteResult


class DownloadError(Exception):
    pass


_FILENAME_RE = re.compile(
    r"filename\\*?=(?:UTF-8''|utf-8'')?\"?([^\";]+)\"?",
    re.IGNORECASE,
)


def _filename_from_content_disposition(value: str | None) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    m = _FILENAME_RE.search(value)
    if not m:
        return None
    raw = m.group(1).strip()
    if not raw:
        return None
    # RFC5987 style may be percent-encoded
    return unquote(raw)


def _filename_from_url(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    name = Path(parsed.path or "").name
    return name or None


def _is_data_uri(url: str) -> bool:
    return isinstance(url, str) and url.startswith("data:")


def _parse_data_uri(uri: str) -> tuple[bytes, str | None]:
    """Return (bytes, content_type) for a data: URI."""
    if not isinstance(uri, str) or not uri.startswith("data:"):
        raise DownloadError("not a data URI")

    header, _, payload = uri.partition(",")
    if not payload:
        return b"", None

    # data:[<mediatype>][;base64],<data>
    # Example: data:image/png;base64,AAAA
    ct = None
    base64_flag = False
    parts = header[5:].split(";") if header.startswith("data:") else []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.lower() == "base64":
            base64_flag = True
            continue
        if "/" in part and ct is None:
            ct = part

    if base64_flag:
        try:
            return base64.b64decode(payload, validate=False), ct
        except Exception as e:
            raise DownloadError(f"data URI base64 decode failed: {e}") from e

    # Percent-decoded bytes
    try:
        return unquote(payload).encode("utf-8"), ct
    except Exception as e:
        raise DownloadError(f"data URI decode failed: {e}") from e


@dataclass(frozen=True)
class AssetDownloadResult:
    sha256: str
    size_bytes: int
    blob_path: Path
    content_type: str | None = None
    original_filename: str | None = None
    final_url: str | None = None  # after redirects


class AssetDownloader:
    def __init__(
        self,
        blobstore: Sha256BlobStore,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 60.0,
    ):
        self.blobstore = blobstore
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(timeout_seconds),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def download(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> AssetDownloadResult:
        if not isinstance(url, str) or not url.strip():
            raise DownloadError("url required")

        url = url.strip()

        if _is_data_uri(url):
            data, ct = _parse_data_uri(url)
            blob = await self.blobstore.write_bytes(data)
            return AssetDownloadResult(
                sha256=blob.sha256,
                size_bytes=blob.size_bytes,
                blob_path=blob.path,
                content_type=ct,
                original_filename=None,
                final_url=None,
            )

        async with self.client.stream("GET", url, headers=headers) as resp:
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise DownloadError(f"download failed ({resp.status_code}): {url}") from e

            ct = resp.headers.get("content-type")
            cd = resp.headers.get("content-disposition")
            filename = _filename_from_content_disposition(cd) or _filename_from_url(str(resp.url))

            async def _iter_bytes() -> AsyncIterator[bytes]:
                async for chunk in resp.aiter_bytes():
                    yield chunk

            blob: BlobWriteResult = await self.blobstore.write_stream(_iter_bytes())

            return AssetDownloadResult(
                sha256=blob.sha256,
                size_bytes=blob.size_bytes,
                blob_path=blob.path,
                content_type=ct,
                original_filename=filename,
                final_url=str(resp.url) if resp.url else None,
            )
