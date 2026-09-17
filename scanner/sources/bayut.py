"""Bayut scraper.

Bayut sits behind a bot-management JS challenge (confirmed live: a plain `requests`
call gets HTTP 503 from `/.humbucker/...browser.js?client=hb-challenge`), so this needs
a real browser. In this project's own sandboxed dev environment even a Playwright
Chromium request got reset at the network level before the page loaded — that may be a
quirk of this dev environment's outbound proxy rather than Bayut itself, but it means
this module is **unverified end-to-end**. Selectors below are Bayut's well-documented
`aria-label` markup (stable across most scraping write-ups), used defensively: if
anything is missing/renamed, `_parse_card` returns None for that card and it's skipped
rather than raising, so a partial break here never takes down the whole scan (see
scanner/main.py, which also catches exceptions per-source).

If this comes back empty once actually deployed, open a Bayut search page's dev tools
and diff the real markup against `_parse_card` below.
"""
from __future__ import annotations

from ..config import Criteria
from ..models import Listing
from . import Source, page_diagnostic

BASE_URL = "https://www.bayut.com/to-rent/apartments/dubai/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
MAX_PAGES = 10


CHALLENGE_MARKERS = (
    "captcha", "are you human", "incapsula", "request unsuccessful",
    "access denied", "humbucker", "just a moment", "verifying you are human",
    "attention required", "cf-browser-verification",
)


class BayutSource(Source):
    name = "bayut"

    def __init__(self) -> None:
        # Filled in on the first page so the caller (and the committed browser_sources.json)
        # can see WHY a run returned nothing: was the page blocked, or just parsed wrong?
        self.diagnostic: dict | None = None

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
                    page.wait_for_timeout(3000)  # let the JS challenge + hydration settle

                    cards = page.query_selector_all('li[aria-label="Listing"]')

                    if page_num == 1:
                        self.diagnostic = page_diagnostic(page, len(cards), CHALLENGE_MARKERS)

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
        link_el = card.query_selector('a[aria-label="Listing link"]') or card.query_selector("a")
        href = link_el.get_attribute("href") if link_el else None
        if not href:
            return None
        url = href if href.startswith("http") else f"https://www.bayut.com{href}"

        title_el = card.query_selector('h2[aria-label="Title"]')
        price_el = card.query_selector('span[aria-label="Price"]')
        beds_el = card.query_selector('span[aria-label="Beds"]')
        baths_el = card.query_selector('span[aria-label="Baths"]')
        location_el = card.query_selector('span[aria-label="Location"]')
        img_el = card.query_selector("img")

        price_monthly = _parse_price_to_monthly(price_el.inner_text() if price_el else None)
        bedrooms = _parse_int(beds_el.inner_text() if beds_el else None)
        bathrooms = _parse_int(baths_el.inner_text() if baths_el else None)

        # source_id: Bayut permalinks end in ".../<numeric-id>.html"
        source_id = url.rstrip("/").rsplit("-", 1)[-1].replace(".html", "")

        # No listed_at or coordinates: the search-results card doesn't expose a posted
        # date or lat/lon (those live on the detail page's map widget), so the 30-day
        # freshness filter and the map view can't cover Bayut listings — see
        # scanner/filters.py's _is_too_old and scanner/dashboard.py's map rendering,
        # both of which skip listings with no data rather than wrongly including/excluding.
        return Listing(
            source="bayut",
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


def _parse_price_to_monthly(text: str | None) -> float | None:
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    value = float(digits)
    # Bayut rents are quoted per-year unless the listing itself says "/month"
    if "month" in text.lower():
        return value
    return value / 12


def _parse_int(text: str | None) -> int | None:
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None
