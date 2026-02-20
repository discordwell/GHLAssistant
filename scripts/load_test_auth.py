#!/usr/bin/env python3
"""Simple auth load test for login endpoint with CSRF token handling."""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


async def _one_login(client: httpx.AsyncClient, base_url: str, email: str, password: str, next_path: str) -> tuple[int, float]:
    started = time.perf_counter()
    page = await client.get(f"{base_url}/auth/login", params={"next": next_path}, follow_redirects=False)
    csrf_cookie_name = None
    for name in page.cookies.keys():
        if name.endswith("_csrf"):
            csrf_cookie_name = name
            break
    csrf_token = page.cookies.get(csrf_cookie_name or "", "")
    resp = await client.post(
        f"{base_url}/auth/login",
        data={
            "email": email,
            "password": password,
            "next": next_path,
            "csrf_token": csrf_token,
        },
        cookies=page.cookies,
        follow_redirects=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return resp.status_code, elapsed_ms


async def _worker(
    queue: asyncio.Queue[int],
    client: httpx.AsyncClient,
    base_url: str,
    email: str,
    password: str,
    next_path: str,
    out: list[tuple[int, float]],
) -> None:
    while True:
        try:
            _ = queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        try:
            out.append(await _one_login(client, base_url, email, password, next_path))
        finally:
            queue.task_done()


async def run(args: argparse.Namespace) -> int:
    jobs: asyncio.Queue[int] = asyncio.Queue()
    for i in range(args.requests):
        jobs.put_nowait(i)

    results: list[tuple[int, float]] = []
    timeout = httpx.Timeout(args.timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        workers = [
            asyncio.create_task(
                _worker(
                    jobs,
                    client,
                    args.base_url.rstrip("/"),
                    args.email,
                    args.password,
                    args.next_path,
                    results,
                )
            )
            for _ in range(max(1, args.concurrency))
        ]
        await asyncio.gather(*workers)

    if not results:
        print("No requests executed")
        return 1

    codes: dict[int, int] = {}
    latencies = [lat for _, lat in results]
    for status, _ in results:
        codes[status] = codes.get(status, 0) + 1

    p50 = statistics.median(latencies)
    p95 = statistics.quantiles(latencies, n=100)[94] if len(latencies) >= 20 else max(latencies)
    p99 = statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 50 else max(latencies)

    print(f"Requests: {len(results)}")
    print(f"Concurrency: {args.concurrency}")
    print("Status counts:")
    for code in sorted(codes):
        print(f"  {code}: {codes[code]}")
    print(f"Latency ms: p50={p50:.1f} p95={p95:.1f} p99={p99:.1f} max={max(latencies):.1f}")

    if any(code >= 500 for code in codes):
        return 2
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8020", help="Service base URL")
    parser.add_argument("--email", required=True, help="Login email")
    parser.add_argument("--password", required=True, help="Login password")
    parser.add_argument("--next-path", default="/", help="Redirect path used during login")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrent workers")
    parser.add_argument("--requests", type=int, default=500, help="Total login attempts")
    parser.add_argument("--timeout-seconds", type=float, default=20.0, help="HTTP timeout per request")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
