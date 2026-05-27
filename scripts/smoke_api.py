#!/usr/bin/env python3
"""
Smoke test for the CeilingCRM REST API.

Verifies that all endpoints respond correctly with and without authentication.

Usage::

    # Start the API first:
    APP_ENV=development uvicorn apps.api.main:app --port 8000

    # Run with a token configured:
    API_INTERNAL_TOKEN=test-secret-token python scripts/smoke_api.py

    # Or specify base URL and token explicitly:
    python scripts/smoke_api.py --base-url http://localhost:8000 --token test-secret-token
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

# ── Defaults ────────────────────────────────────────────────────────────
DEFAULT_BASE_URL = "http://localhost:8000"

# ── Test definitions ────────────────────────────────────────────────────
TESTS: list[dict] = [
    # --- Public endpoint ---
    {
        "name": "GET /health (no token) -- should return 200",
        "method": "GET",
        "path": "/health",
        "token": None,
        "expect_status": 200,
        "expect_json_key": "status",
    },
    # --- Protected endpoints without token (expect 401) ---
    {
        "name": "GET /api/v1/health (no token) -- should return 401",
        "method": "GET",
        "path": "/api/v1/health",
        "token": None,
        "expect_status": 401,
    },
    {
        "name": "GET /api/v1/leads (no token) -- should return 401",
        "method": "GET",
        "path": "/api/v1/leads",
        "token": None,
        "expect_status": 401,
    },
    {
        "name": "GET /api/v1/pipeline/kanban (no token) -- should return 401",
        "method": "GET",
        "path": "/api/v1/pipeline/kanban",
        "token": None,
        "expect_status": 401,
    },
    {
        "name": "GET /api/v1/analytics (no token) -- should return 401",
        "method": "GET",
        "path": "/api/v1/analytics",
        "token": None,
        "expect_status": 401,
    },
    # --- Protected endpoints with wrong token (expect 401) ---
    {
        "name": "GET /api/v1/health (wrong token) -- should return 401",
        "method": "GET",
        "path": "/api/v1/health",
        "token": "definitely-wrong-token",
        "expect_status": 401,
    },
    # --- Protected endpoints with valid token (expect 200) ---
    {
        "name": "GET /api/v1/health (valid token) -- should return 200",
        "method": "GET",
        "path": "/api/v1/health",
        "token": "__VALID__",
        "expect_status": 200,
        "expect_json_key": "status",
    },
    {
        "name": "GET /api/v1/leads (valid token) -- should return 200",
        "method": "GET",
        "path": "/api/v1/leads",
        "token": "__VALID__",
        "expect_status": 200,
        "expect_json_key": "items",
    },
    {
        "name": "GET /api/v1/pipeline/kanban (valid token) -- should return 200",
        "method": "GET",
        "path": "/api/v1/pipeline/kanban",
        "token": "__VALID__",
        "expect_status": 200,
        "expect_json_key": "columns",
    },
    {
        "name": "GET /api/v1/analytics (valid token) -- should return 200",
        "method": "GET",
        "path": "/api/v1/analytics?period=week",
        "token": "__VALID__",
        "expect_status": 200,
        "expect_json_key": "total_leads",
    },
]


def _request(base_url: str, path: str, token: str | None) -> tuple[int, dict | None]:
    """Make an HTTP request and return (status_code, parsed_json_or_None)."""
    url = f"{base_url}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = None
            return resp.status, data
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            data = None
        return e.code, data


def run_tests(base_url: str, valid_token: str | None) -> bool:
    """Run all smoke tests. Returns True if all passed."""
    passed = 0
    failed = 0
    skipped = 0

    for test in TESTS:
        name = test["name"]
        token = test["token"]

        # Replace sentinel with actual token
        if token == "__VALID__":
            if not valid_token:
                print(f"  SKIP  {name}  (no token provided)")
                skipped += 1
                continue
            token = valid_token

        try:
            status_code, data = _request(base_url, test["path"], token)
        except Exception as exc:
            print(f"  FAIL  {name}")
            print(f"        Error: {exc}")
            failed += 1
            continue

        expected = test["expect_status"]
        if status_code != expected:
            print(f"  FAIL  {name}")
            print(f"        Expected {expected}, got {status_code}")
            if data:
                print(f"        Body: {json.dumps(data)[:200]}")
            failed += 1
            continue

        # Optional JSON key check
        json_key = test.get("expect_json_key")
        if json_key and data and json_key not in data:
            print(f"  FAIL  {name}")
            print(f"        Missing key '{json_key}' in response")
            failed += 1
            continue

        print(f"  PASS  {name}")
        passed += 1

    # Summary
    total = passed + failed + skipped
    print()
    print(f"Results: {passed}/{total} passed, {failed} failed, {skipped} skipped")

    return failed == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="CeilingCRM API smoke test")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("API_BASE_URL", DEFAULT_BASE_URL),
        help=f"API base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("API_INTERNAL_TOKEN"),
        help="Bearer token for protected endpoints (or set API_INTERNAL_TOKEN env var)",
    )
    args = parser.parse_args()

    print("CeilingCRM API Smoke Test")
    print(f"Base URL: {args.base_url}")
    print(f"Token:    {'(set)' if args.token else '(not set -- auth tests will be skipped)'}")
    print()

    success = run_tests(args.base_url, args.token)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
