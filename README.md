# Dubai Flat Scanner

Scans Bayut, Dubizzle, Property Finder (and, best-effort, Facebook Marketplace) for Dubai
rentals matching your criteria, and publishes a simple dashboard of everything it finds.

**Default criteria** (edit in `scanner/config.py`):
- Budget: ≤ 6,000 AED/month
- 2 bedrooms, 2 bathrooms
- Excludes Dubai Marina and JLT
- Jumeirah and other water-adjacent areas (JBR, Palm Jumeirah, La Mer, Bluewaters, etc.)
  are flagged "Preferred area" and sorted first, but matching listings anywhere else
  (outside the excluded areas) still show up.

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m scanner.main
open docs/index.html   # or just double-click it
```

This writes `docs/index.html` (the dashboard) and `docs/data.json` (raw matches).

## Run it on a schedule with a hosted dashboard (GitHub Pages)

This repo already includes `.github/workflows/scan.yml`, which runs every 3 hours,
re-scans everything, and publishes `docs/` to GitHub Pages.

One-time setup after pushing this repo to GitHub:
1. Repo **Settings → Pages → Source** → set to **GitHub Actions**.
2. Push to `main` (or run the workflow manually from the **Actions** tab).
3. Your dashboard will be live at `https://<you>.github.io/<repo>/`.

## Facebook Marketplace (optional — via Apify, recommended)

Facebook requires a logged-in session and its Terms of Service explicitly ban
automated access even while logged in as yourself — so this project does **not**
use your own Facebook login. Instead it calls the official `apify/facebook-marketplace-scraper`
actor, which runs on Apify's own infrastructure. Your Facebook account is never
involved and carries no ban exposure.

1. Sign up at [apify.com](https://apify.com) (free — $5/month usage credit, roughly
   1,000 listings/month, comfortably enough for a once-a-day check).
2. Get an API token: Apify Console → Settings → Integrations.
3. **Local runs:** `export APIFY_API_TOKEN=your_token` then `python -m scanner.main --with-facebook`.
4. **Scheduled/GitHub Actions runs:** add it as a repository secret named
   `APIFY_API_TOKEN` (Settings → Secrets and variables → Actions). The workflow
   picks it up automatically once it's set.

The confirmed Marketplace URL this scans is Dubai's property-rentals category
(`facebook.com/marketplace/111070818917271/propertyrentals/` — Facebook uses a
numeric place ID per city, not a name like "dubai"). Marketplace listings don't have
separate bedroom/bathroom fields, so bed/bath counts are parsed out of each listing's
title/description text; a listing that doesn't state both is skipped rather than
guessed at.

This actor's exact output field names weren't independently verified end-to-end while
building this (no Apify token was available in that environment) — `_to_listing` in
`scanner/sources/facebook_apify.py` tries several likely field names defensively, but
if it comes back empty, run the actor once from the Apify Console with the URL above
and diff its real output against that function.

### Legacy fallback: your own login (not recommended)

`scanner/sources/facebook.py` + `facebook_login.py` still exist as a fallback that logs
in as you via a saved Playwright session, in case Apify ever stops working for this.
**This carries real risk to your Facebook account** — Meta's Jan 2025 ToS update closed
the "logged in, so it's fine" loophole, and automated sessions are detected via browser
fingerprinting and request timing, not just IP reputation. If you ever fall back to it:
run it manually and infrequently from your own home connection, never on a schedule/CI,
and never headless. It only activates if `fb_state.json` exists and no `APIFY_API_TOKEN`
is set (see `main.py`).

## Project layout

```
scanner/
  config.py        criteria (budget, beds/baths, areas)
  models.py        Listing data model
  filters.py        matching + ranking logic
  dashboard.py      renders docs/index.html + docs/data.json
  main.py            orchestrator / CLI entrypoint
  sources/
    bayut.py
    dubizzle.py
    propertyfinder.py
    facebook_apify.py   Facebook via Apify (recommended, no personal login)
    facebook.py          legacy fallback: your own login via Playwright (not recommended)
```

Each source module exposes one `Source` subclass with a `fetch(criteria) -> list[Listing]`
method — add a new source by dropping in another file and registering it in `main.py`.

## Notes

This is a personal-use tool for apartment hunting, scanning public search-result pages.
Sites' terms of service and page structures change; if a source starts returning nothing,
check the log output first — the source module likely needs a selector/endpoint update.
