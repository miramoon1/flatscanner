"""Dubizzle scraper.

Dubizzle (dubai.dubizzle.com) sits behind Imperva Incapsula (confirmed live: a plain
`requests` call gets an `incap_ses_...` cookie challenge / "Request unsuccessful"
page) — a stricter bot-management vendor than Bayut's, and one that commonly also
blocks plain headless Playwright without extra stealth measures and/or residential
proxies. This module is the most likely of the three portals to need extra work
(a stealth-patched browser such as `playwright-stealth`/`camoufox`, and/or a proxy)
before it reliably returns anything outside this project's own dev sandbox.

Selectors target Dubizzle's `data-aut-id` markup (it shares lineage with the
OLX/Frontier Digital platform, which consistently exposes these test-id attributes),
matching common public write-ups on scraping Dubizzle — **unverified end-to-end** in
this project's environment; defensive parsing means a selector mismatch skips that
card instead of raising (see scanner/main.py, which also catches exceptions per-source).
"""
from __future__ import annotations

from ..config import Criteria
from ..models import Listing
from . import Source

BASE_URL = "https://dubai.dubizzle.com/property-for-rent/residential/apartments/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
MAX_PAGES = 10


class DubizzleSource(Source):
    name = "dubizzle"

    def fetch(self, criteria: Criteria) -> list[Listing]:
        from playwright.sync_api import sync_playwright

        listings: list[Listing] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT, locale="en-US")
            try:
                for page_num in range(1, MAX_PAGES + 1):
                    url = BASE_URL if page_num == 1 else f"{BASE_URL}?page={page_num}"
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)

                    cards = page.query_selector_all('[data-aut-id="itemBox3"]')
                    if not cards:
                        break

                    for card in cards:
                        listing = _parse_card(card)
                        if listing is not None:
                            listings.append(listing)
            finally:
                browser.close()

        return listings


def _parse_card(card) -> Listing | None:
    try:
        link_el = card.query_selector("a")
        href = link_el.get_attribute("href") if link_el else None
        if not href:
            return None
        url = href if href.startswith("http") else f"https://dubai.dubizzle.com{href}"

        title_el = card.query_selector('[data-aut-id="itemTitle"]')
        price_el = card.query_selector('[data-aut-id="itemPrice"]')
        location_el = card.query_selector('[data-aut-id="item-location"]')
        details_el = card.query_selector('[data-aut-id="itemFeature"], [data-aut-id="itemDetail"]')
        img_el = card.query_selector("img")

        price_monthly = _parse_price_to_monthly(price_el.inner_text() if price_el else None)
        bedrooms, bathrooms = _parse_beds_baths(card)

        source_id = url.rstrip("/").rsplit("-", 1)[-1].split(".")[0]

        return Listing(
            source="dubizzle",
            source_id=source_id or url,
            title=title_el.inner_text() if title_el else "",
            url=url,
            price_monthly_aed=price_monthly,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            area=location_el.inner_text() if location_el else "",
            image_url=img_el.get_attribute("src") if img_el else None,
        )
    except Exception:
        return None


def _parse_beds_baths(card) -> tuple[int | None, int | None]:
    bedrooms = bathrooms = None
    for feature in card.query_selector_all('[data-aut-id="itemFeature"], span'):
        text = (feature.inner_text() or "").strip().lower()
        if "bed" in text:
            bedrooms = _parse_int(text)
        elif "bath" in text:
            bathrooms = _parse_int(text)
    return bedrooms, bathrooms


def _parse_price_to_monthly(text: str | None) -> float | None:
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    value = float(digits)
    if "month" in text.lower() or "/mo" in text.lower():
        return value
    return value / 12


def _parse_int(text: str | None) -> int | None:
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None
