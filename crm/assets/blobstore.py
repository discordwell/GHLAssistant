"""Filesystem blobstore for canonical asset bytes.

Layout (gitignored):
  data/blobstore/sha256/<first2>/<sha256>

Notes:
  - `BlobStore` is a simple, synchronous facade (used by discovery code that
    already knows the sha256, e.g. decoded data: URIs).
  - `Sha256BlobStore` supports streaming writes where the sha256 is computed
    during download.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator


class BlobstoreError(Exception):
    pass


def _normalize_sha256_hex(value: str) -> str:
    sha = (value or "").strip().lower()
    if len(sha) != 64:
        raise BlobstoreError(f"sha256 hex must be 64 chars (got {len(sha)})")
    for ch in sha:
        if ch not in "0123456789abcdef":
            raise BlobstoreError("sha256 hex must be lowercase [0-9a-f]")
    return sha


@dataclass(frozen=True)
class BlobWriteResult:
    sha256: str
    size_bytes: int
    path: Path


class BlobStore:
    """Synchronous blobstore facade (write-by-known-sha)."""

    def __init__(self, root_dir: str | Path = "data/blobstore"):
        self.root_dir = Path(root_dir)

    def path_for_sha256(self, sha256_hex: str) -> Path:
        sha = _normalize_sha256_hex(sha256_hex)
        return self.root_dir / "sha256" / sha[:2] / sha

    def has(self, sha256_hex: str) -> bool:
        return self.path_for_sha256(sha256_hex).is_file()

    def put_bytes_atomic(self, sha256_hex: str, data: bytes) -> Path:
        """Write bytes to the blobstore using an atomic rename."""
        dest = self.path_for_sha256(sha256_hex)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.exists():
            return dest

        fd = None
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(
                prefix=f"{dest.name}.tmp.",
                dir=str(dest.parent),
            )
            with os.fdopen(fd, "wb") as f:
                fd = None
                f.write(data or b"")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, dest)
            tmp_path = None
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        return dest


class Sha256BlobStore:
    """Streaming blobstore (compute sha256 while writing)."""

    def __init__(self, root_dir: str | Path = "data/blobstore"):
        self.root_dir = Path(root_dir)
        self.algo_dir = self.root_dir / "sha256"
        self.tmp_dir = self.root_dir / ".tmp"
        self.algo_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, sha256_hex: str) -> Path:
        sha = _normalize_sha256_hex(sha256_hex)
        return self.algo_dir / sha[:2] / sha

    def exists(self, sha256_hex: str) -> bool:
        return self.path_for(sha256_hex).is_file()

    async def write_stream(self, chunks: AsyncIterator[bytes]) -> BlobWriteResult:
        tmp_path = self.tmp_dir / f"tmp_{secrets.token_hex(16)}"
        h = hashlib.sha256()
        size = 0

        try:
            with open(tmp_path, "wb") as f:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    if not isinstance(chunk, (bytes, bytearray)):
                        raise BlobstoreError("blob chunks must be bytes")
                    h.update(chunk)
                    size += len(chunk)
                    f.write(chunk)

            digest = h.hexdigest()
            final_path = self.path_for(digest)
            final_path.parent.mkdir(parents=True, exist_ok=True)

            # If another worker already wrote it, keep the existing bytes.
            if final_path.exists():
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
            else:
                os.replace(tmp_path, final_path)

            return BlobWriteResult(sha256=digest, size_bytes=size, path=final_path)
        except Exception:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise

    async def write_bytes(self, data: bytes) -> BlobWriteResult:
        async def _iter() -> AsyncIterator[bytes]:
            yield data or b""

        return await self.write_stream(_iter())

