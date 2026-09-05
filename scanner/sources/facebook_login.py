"""One-time helper: log into Facebook in a real (visible) browser and save the
session so scanner.sources.facebook can reuse it without you logging in again.

Run this locally (not in CI):

    python -m scanner.sources.facebook_login

It opens a browser window at the Facebook login page. Log in manually — including
any 2FA/checkpoint Facebook throws at you — then come back to the terminal and press
Enter. Your session is saved to fb_state.json in the repo root.

fb_state.json is equivalent to being logged into your Facebook account. It's
gitignored — never commit it. For scheduled/CI runs, paste its contents into a repo
secret named FB_STORAGE_STATE instead (see README).
"""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

STATE_PATH = Path(__file__).resolve().parent.parent.parent / "fb_state.json"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.facebook.com/login")

        input(
            "\nLog into Facebook in the opened browser window (handle any 2FA prompts too), "
            "then press Enter here once you're logged in and see your feed...\n"
        )

        context.storage_state(path=str(STATE_PATH))
        browser.close()

    print(f"Saved Facebook session to {STATE_PATH}")


if __name__ == "__main__":
    main()
