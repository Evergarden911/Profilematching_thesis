"""Batch-capture FastAPI HTML pages into Figma via html-to-design hash URLs."""
from __future__ import annotations

import time
import urllib.parse

import requests
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"

SCREENS = [
    {
        "name": "01 | Login",
        "path": "/login",
        "capture_id": "16f2aeeb-0d67-47ac-ba48-8ca5160b2219",
        "auth": None,
    },
    {
        "name": "02 | Dashboard — Kepala Cabang",
        "path": "/dashboard",
        "capture_id": "23bd40a9-87dd-40b5-9ed2-23b944a4ce65",
        "auth": ("admin_cabang", "cabang123"),
    },
    {
        "name": "03 | Request — Kepala Bagian",
        "path": "/requests",
        "capture_id": "a9db412e-89b6-4268-abfe-eda5e4314046",
        "auth": ("admin_divisi", "divisi123"),
    },
    {
        "name": "04 | Workload Analysis — Kepala Bagian",
        "path": "/wla",
        "capture_id": "d635bdbf-ca96-43c5-81c3-8ec12f8054f8",
        "auth": ("admin_divisi", "divisi123"),
    },
    {
        "name": "05 | Data Master — Kepala Cabang",
        "path": "/divisions",
        "capture_id": "7d572ba2-67e3-4a8f-bb03-2391ab8ed1dd",
        "auth": ("admin_cabang", "cabang123"),
    },
    {
        "name": "06 | Profile Matching — Manajer HRD",
        "path": "/results",
        "capture_id": "ca2c122c-e0ff-4398-92a9-3fb7ab347520",
        "auth": ("admin_hrd", "hrd123"),
    },
    {
        "name": "07 | Approval — Kepala Cabang",
        "path": "/gates",
        "capture_id": "3d157079-cc68-4961-87ca-eade4026ea46",
        "auth": ("admin_cabang", "cabang123"),
    },
    {
        "name": "08 | Riwayat Rotasi — Manajer HRD",
        "path": "/history",
        "capture_id": "652bcf9e-2b0b-4d9e-a242-17fd447ffeaa",
        "auth": ("admin_hrd", "hrd123"),
    },
    {
        "name": "09 | Admin — Manajer HRD",
        "path": "/admin",
        "capture_id": "8abb6657-2096-4ba3-a8a8-9cbb4769593a",
        "auth": ("admin_hrd", "hrd123"),
    },
    {
        "name": "10 | Reporting — Kepala Cabang",
        "path": "/history",
        "capture_id": "e04d3412-7965-444b-8588-dbc81e976027",
        "auth": ("admin_cabang", "cabang123"),
    },
]


def login_cookie(username: str, password: str) -> str | None:
    resp = requests.post(
        f"{BASE}/api/auth/token",
        data={"username": username, "password": password},
        timeout=30,
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    for cookie in resp.cookies:
        if cookie.name == "access_token":
            return cookie.value
    return f"Bearer {token}"


def capture_url(path: str, capture_id: str) -> str:
    endpoint = (
        f"https://mcp.figma.com/mcp/capture/{capture_id}/submit?bindVariables=true"
    )
    fragment = (
        f"figmacapture={capture_id}"
        f"&figmaendpoint={urllib.parse.quote(endpoint, safe='')}"
        f"&figmadelay=2500"
    )
    return f"{BASE}{path}#{fragment}"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})

        for screen in SCREENS:
            print(f"Capturing: {screen['name']} ...")
            context.clear_cookies()

            if screen["auth"]:
                username, password = screen["auth"]
                cookie_val = login_cookie(username, password)
                context.add_cookies(
                    [
                        {
                            "name": "access_token",
                            "value": cookie_val,
                            "domain": "127.0.0.1",
                            "path": "/",
                        }
                    ]
                )

            page = context.new_page()
            url = capture_url(screen["path"], screen["capture_id"])
            page.goto(url, wait_until="networkidle", timeout=120_000)
            page.wait_for_timeout(8000)
            page.close()
            print(f"  submitted: {screen['capture_id']}")
            time.sleep(2)

        browser.close()
    print("All capture URLs submitted.")


if __name__ == "__main__":
    main()
