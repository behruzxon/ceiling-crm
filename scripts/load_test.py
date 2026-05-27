#!/usr/bin/env python3
"""
Lightweight load test for CeilingCRM bot.

Simulates concurrent users hitting key endpoints to measure response time
and error rate.  No heavy frameworks required — just asyncio + aiohttp.

Usage:
    # Against local polling bot (must be running)
    python scripts/load_test.py --url http://localhost:8080/webhook --users 100

    # Quick smoke test
    python scripts/load_test.py --url http://localhost:8080/webhook --users 10 --rounds 2

    # Full stress test
    python scripts/load_test.py --url http://localhost:8080/webhook --users 300 --rounds 5

The script sends fake Telegram webhook payloads to the bot's webhook endpoint.
This only works when the bot is running in webhook mode (docker/staging).

For polling mode, use --mode direct to test service layers directly.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time
from dataclasses import dataclass, field


@dataclass
class Stats:
    """Accumulates per-request timing and error data."""

    successes: int = 0
    failures: int = 0
    errors: list[str] = field(default_factory=list)
    latencies: list[float] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.successes + self.failures

    @property
    def error_rate(self) -> float:
        return self.failures / max(self.total, 1) * 100

    def summary(self) -> str:
        lines = [
            "",
            "=" * 60,
            "LOAD TEST RESULTS",
            "=" * 60,
            f"Total requests:  {self.total}",
            f"Successes:       {self.successes}",
            f"Failures:        {self.failures}",
            f"Error rate:      {self.error_rate:.1f}%",
        ]
        if self.latencies:
            lines += [
                "",
                f"Avg latency:     {statistics.mean(self.latencies)*1000:.1f} ms",
                f"P50 latency:     {statistics.median(self.latencies)*1000:.1f} ms",
                f"P95 latency:     {_percentile(self.latencies, 0.95)*1000:.1f} ms",
                f"P99 latency:     {_percentile(self.latencies, 0.99)*1000:.1f} ms",
                f"Min latency:     {min(self.latencies)*1000:.1f} ms",
                f"Max latency:     {max(self.latencies)*1000:.1f} ms",
            ]
        if self.errors:
            unique = set(self.errors[:20])
            lines += ["", "Sample errors:"]
            for err in list(unique)[:5]:
                lines.append(f"  - {err}")
        lines.append("=" * 60)
        return "\n".join(lines)


def _percentile(data: list[float], p: float) -> float:
    """Calculate percentile without numpy."""
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p)
    return sorted_data[min(idx, len(sorted_data) - 1)]


# ── Fake Telegram update payloads ─────────────────────────────────────────────

_DISTRICTS = [
    "Chilonzor",
    "Sergeli",
    "Yunusobod",
    "Mirzo Ulug'bek",
    "Olmazor",
    "Yakkasaroy",
    "Shayxontohur",
    "Mirobod",
]
_NAMES = [
    "Alisher",
    "Dilshod",
    "Sardor",
    "Farrux",
    "Bobur",
    "Nodira",
    "Gulnora",
    "Malika",
    "Aziza",
    "Kamola",
]
_COMMANDS = ["/start", "/menu", "/catalog", "/price", "/help"]
_TEXTS = [
    "Salom, shift potolok narxi qancha?",
    "Bepul o'lchov bormi?",
    "30 m2 xona uchun narx ayting",
    "Matviy oq potolok kerak",
    "Yulduzli potolok qilib berasizmi?",
    "Premium paket narxi?",
    "Chilonzorga chiqasizmi?",
    "Qancha vaqt ketadi?",
    "Kafolat bormi?",
    "LED yoritish qo'shsa bo'ladimi?",
]


def _fake_user_id() -> int:
    """Generate a fake Telegram user ID (high range to avoid real users)."""
    return random.randint(9_000_000_000, 9_999_999_999)


def _make_message_update(user_id: int, text: str) -> dict:
    """Build a minimal Telegram Update JSON for a private message."""
    return {
        "update_id": random.randint(100000, 999999),
        "message": {
            "message_id": random.randint(1, 99999),
            "from": {
                "id": user_id,
                "is_bot": False,
                "first_name": random.choice(_NAMES),
                "language_code": "uz",
            },
            "chat": {
                "id": user_id,
                "type": "private",
            },
            "date": int(time.time()),
            "text": text,
        },
    }


def _make_callback_update(user_id: int, callback_data: str) -> dict:
    """Build a minimal Telegram Update JSON for a callback query."""
    return {
        "update_id": random.randint(100000, 999999),
        "callback_query": {
            "id": str(random.randint(100000, 999999)),
            "from": {
                "id": user_id,
                "is_bot": False,
                "first_name": random.choice(_NAMES),
                "language_code": "uz",
            },
            "chat_instance": str(random.randint(100000, 999999)),
            "data": callback_data,
        },
    }


def _random_update(user_id: int) -> dict:
    """Generate a random update (message or callback)."""
    r = random.random()
    if r < 0.3:
        return _make_message_update(user_id, random.choice(_COMMANDS))
    elif r < 0.8:
        return _make_message_update(user_id, random.choice(_TEXTS))
    else:
        cb_options = [
            "cta:catalog",
            "cta:pricing",
            "cta:order",
            "cta:operator",
        ]
        return _make_callback_update(user_id, random.choice(cb_options))


# ── HTTP load test (webhook mode) ─────────────────────────────────────────────


async def _send_request(
    session: aiohttp.ClientSession,
    url: str,
    payload: dict,
    stats: Stats,
) -> None:
    """Send one fake update and record timing."""
    t0 = time.monotonic()
    try:
        async with session.post(
            url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            elapsed = time.monotonic() - t0
            stats.latencies.append(elapsed)
            if resp.status in (200, 204):
                stats.successes += 1
            else:
                stats.failures += 1
                body = await resp.text()
                stats.errors.append(f"HTTP {resp.status}: {body[:100]}")
    except Exception as exc:
        elapsed = time.monotonic() - t0
        stats.latencies.append(elapsed)
        stats.failures += 1
        stats.errors.append(f"{type(exc).__name__}: {exc}")


async def run_webhook_load_test(
    url: str,
    num_users: int,
    rounds: int,
    concurrency: int,
) -> Stats:
    """Run the load test against a webhook endpoint."""
    import aiohttp

    stats = Stats()
    user_ids = [_fake_user_id() for _ in range(num_users)]
    semaphore = asyncio.Semaphore(concurrency)

    async with aiohttp.ClientSession() as session:
        for round_num in range(1, rounds + 1):
            print(f"Round {round_num}/{rounds} — {num_users} users...")
            tasks = []
            for uid in user_ids:
                payload = _random_update(uid)

                async def _bounded_send(p: dict = payload) -> None:
                    async with semaphore:
                        await _send_request(session, url, p, stats)

                tasks.append(asyncio.create_task(_bounded_send()))

            await asyncio.gather(*tasks)
            print(
                f"  Done: {stats.successes} ok, {stats.failures} failed "
                f"({stats.error_rate:.1f}% error rate)"
            )

    return stats


# ── Direct service test (polling mode) ────────────────────────────────────────


async def run_direct_load_test(num_users: int, rounds: int) -> Stats:
    """Test service layers directly without HTTP. Requires DB + Redis."""
    stats = Stats()

    # Import heavy dependencies only when needed
    from infrastructure.cache.client import connect_redis
    from infrastructure.database.session import connect_database, get_session_factory
    from infrastructure.di import get_lead_repo, get_pipeline_service

    await connect_database()
    await connect_redis()

    factory = get_session_factory()

    for round_num in range(1, rounds + 1):
        print(f"Round {round_num}/{rounds} — {num_users} DB queries...")
        tasks = []
        for _ in range(num_users):

            async def _query() -> None:
                t0 = time.monotonic()
                try:
                    async with factory() as session:
                        repo = get_lead_repo(session)
                        # Simulate common queries
                        op = random.choice(["counts", "search", "recent"])
                        if op == "counts":
                            svc = get_pipeline_service(session)
                            await svc.get_stage_counts()
                        elif op == "search":
                            await repo.search(limit=10, offset=0)
                        else:
                            await repo.search(limit=5, offset=0)

                    stats.latencies.append(time.monotonic() - t0)
                    stats.successes += 1
                except Exception as exc:
                    stats.latencies.append(time.monotonic() - t0)
                    stats.failures += 1
                    stats.errors.append(str(exc))

            tasks.append(asyncio.create_task(_query()))

        await asyncio.gather(*tasks)
        print(
            f"  Done: {stats.successes} ok, {stats.failures} failed "
            f"({stats.error_rate:.1f}% error rate)"
        )

    return stats


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="CeilingCRM load test")
    parser.add_argument(
        "--url",
        default="http://localhost:8080/webhook",
        help="Webhook URL to test (default: http://localhost:8080/webhook)",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=100,
        help="Number of simulated users (default: 100)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="Number of rounds (default: 3)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=50,
        help="Max concurrent requests (default: 50)",
    )
    parser.add_argument(
        "--mode",
        choices=["webhook", "direct"],
        default="webhook",
        help="Test mode: 'webhook' (HTTP) or 'direct' (DB queries)",
    )
    args = parser.parse_args()

    print("CeilingCRM Load Test")
    print(f"Mode: {args.mode}")
    print(f"Users: {args.users}, Rounds: {args.rounds}, Concurrency: {args.concurrency}")
    print()

    if args.mode == "webhook":
        # Import aiohttp only when needed
        global aiohttp
        import aiohttp  # noqa: F811

        stats = asyncio.run(
            run_webhook_load_test(args.url, args.users, args.rounds, args.concurrency)
        )
    else:
        stats = asyncio.run(run_direct_load_test(args.users, args.rounds))

    print(stats.summary())


if __name__ == "__main__":
    main()
