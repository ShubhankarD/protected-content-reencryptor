"""Simple permission tester for Microsoft Graph and (placeholder) Rights Management APIs.

Usage:
  python -m src.permission_tester [--interactive]

The script will obtain a token using `AuthManager` in this repo then call a few Graph
endpoints that correspond to the permissions in your screenshot and report whether the
call succeeded (permission likely granted) or returned 403/401 (permission missing).

Notes:
- For confidential (app-only) clients the script requests the app token (/.default).
- For public (delegated) clients the script will try silent auth and use interactive
  if you pass --interactive.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict

import requests

# Ensure the repository `src` path is on sys.path so absolute imports in modules like
# `auth.py` and `logging_setup.py` work regardless of how the script is invoked.
THIS_DIR = os.path.dirname(__file__)
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)
from auth import AuthManager


ENDPOINTS: Dict[str, Dict[str, str]] = {
    # Tests that map to permissions in your screenshot
    "users_list": {
        "url": "https://graph.microsoft.com/v1.0/users?$top=1",
        "desc": "Read all users' full profiles (User.Read.All application or delegated where allowed)",
    },
    "me_profile": {
        "url": "https://graph.microsoft.com/v1.0/me",
        "desc": "Sign in and read user profile (User.Read delegated)",
    },
    "drive_root": {
        "url": "https://graph.microsoft.com/v1.0/me/drive/root",
        "desc": "Files access (Files.Read.All or Files.ReadWrite.All)",
    },
    "sites_search": {
        "url": "https://graph.microsoft.com/v1.0/sites?search=*",
        "desc": "Site collections access (Sites.FullControl.All)",
    },
}


def call_endpoint(token: str, url: str) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    return requests.get(url, headers=headers, timeout=30)


def report_result(name: str, desc: str, resp: requests.Response) -> None:
    if resp.status_code == 200:
        try:
            data = resp.json()
            sample = json.dumps(data if isinstance(data, dict) else {"result": data}, indent=2)[:1000]
        except Exception:
            sample = resp.text[:1000]
        print(f"[PASS] {name}: {desc} -> 200 OK\n  sample: {sample}\n")
    elif resp.status_code in (401, 403):
        print(f"[FAIL] {name}: {desc} -> {resp.status_code} {resp.reason} (likely missing permission)\n  body: {resp.text[:500]}\n")
    else:
        print(f"[WARN] {name}: {desc} -> {resp.status_code} {resp.reason}\n  body: {resp.text[:500]}\n")


def test_graph_permissions(interactive: bool = False) -> None:
    am = AuthManager()

    # Choose scopes depending on client mode. Confidential clients should use .default
    if am.client_mode == "confidential":
        scopes = ["https://graph.microsoft.com/.default"]
    else:
        # For delegated scenarios, request general Graph scopes that map to your screenshot
        scopes = ["User.Read", "Files.Read.All", "Sites.FullControl.All"]

    print(f"Client mode: {am.client_mode}; requesting scopes: {scopes}")
    token = am.get_token(scopes=scopes, interactive=interactive)
    if not token:
        print("No access token obtained. Try running with --interactive for public clients or check your app credentials.")
        sys.exit(2)

    print("Access token obtained — running endpoint checks...\n")

    for name, info in ENDPOINTS.items():
        url = info["url"]
        desc = info["desc"]
        try:
            resp = call_endpoint(token, url)
            report_result(name, desc, resp)
        except Exception as exc:
            print(f"[ERROR] {name}: exception calling {url}: {exc}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Permission tester that calls Microsoft Graph endpoints")
    parser.add_argument("--interactive", action="store_true", help="Force interactive consent for public clients")
    args = parser.parse_args()

    test_graph_permissions(interactive=args.interactive)


if __name__ == "__main__":
    main()
