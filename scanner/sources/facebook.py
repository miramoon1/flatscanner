"""Facebook Marketplace scraper — best-effort, opt-in.

Confirmed live (Sept 2026): an anonymous request to Facebook Marketplace 302-redirects
to /login — there is no logged-out way to read it. This source only runs if
fb_state.json (a saved login session) exists; see scanner/sources/facebook_login.py and
the README for how to create one. scanner/main.py only wires this source in when
--with-facebook is passed, and only passes that when a session file is actually present.

Marketplace has no separate "beds"/"baths" fields in the listing feed the way property
portals do — that data (when present at all) is embedded in the free-text title, e.g.
"2 Bed 2 Bath Apartment in Jumeirah". We regex it out of the title on a best-effort
basis; listings that don't state beds/baths in the title are dropped, since we can't
verify they match.

This is inherently the least reliable of the four sources: Facebook changes Marketplace
markup often, sessions expire, and automated traffic can trigger checkpoints — expect to
occasionally have to redo the login step. Failures here are caught by scanner/main.py
and never block the other three sources.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..config import Criteria
from ..models import Listing
from . import Source

STATE_PATH = Path(__file__).resolve().parent.parent.parent / "fb_state.json"
MARKETPLACE_URL = "https://www.facebook.com/marketplace/dubai/propertyrentals"

BEDS_RE = re.compile(r"(\d+)\s*(?:bed|br|bhk)", re.I)
BATHS_RE = re.compile(r"(\d+)\s*(?:bath|ba)\b", re.I)


class FacebookMarketplaceSource(Source):
    name = "facebook"

    def fetch(self, criteria: Criteria) -> list[Listing]:
        if not STATE_PATH.exists():
            return []

        from playwright.sync_api import sync_playwright

        listings: list[Listing] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=str(STATE_PATH))
            page = context.new_page()
            try:
                page.goto(MARKETPLACE_URL, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)

                # Marketplace is an infinite-scroll feed; a few scrolls is enough for a
                # periodic scan (we only care about what's newly listed since last run).
                for _ in range(6):
                    page.mouse.wheel(0, 3000)
                    page.wait_for_timeout(1500)

                cards = page.query_selector_all('a[href*="/marketplace/item/"]')
                for card in cards:
                    listing = _parse_card(card)
                    if listing is not None:
                        listings.append(listing)
            finally:
                browser.close()

        return listings


def _parse_card(card) -> Listing | None:
    try:
        href = card.get_attribute("href")
        if not href:
            return None
        url = href.split("?")[0]
        if not url.startswith("http"):
            url = f"https://www.facebook.com{url}"

        text = (card.inner_text() or "").strip()
        if not text:
            return None
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        price_monthly = _parse_price_to_monthly(text)
        beds_match = BEDS_RE.search(text)
        baths_match = BATHS_RE.search(text)
        if not beds_match or not baths_match:
            return None  # can't verify bed/bath count from the card, skip rather than guess

        title = lines[1] if len(lines) > 1 else lines[0]
        area = lines[-1] if len(lines) > 2 else ""

        source_id = url.rstrip("/").rsplit("/", 1)[-1]

        return Listing(
            source="facebook",
            source_id=source_id or url,
            title=title,
            url=url,
            price_monthly_aed=price_monthly,
            bedrooms=int(beds_match.group(1)),
            bathrooms=int(baths_match.group(1)),
            area=area,
            image_url=None,
        )
    except Exception:
        return None


def _parse_price_to_monthly(text: str) -> float | None:
    match = re.search(r"AED\s*([\d,]+)", text, re.I)
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    if re.search(r"/\s*year|yearly|per year", text, re.I):
        return value / 12
    if re.search(r"/\s*mo|month", text, re.I):
        return value
    # Marketplace rentals are usually listed per-month by convention; assume monthly
    # unless the text says otherwise.
    return value
