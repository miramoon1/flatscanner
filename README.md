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
- Listed within the last 30 days (`scanner/filters.py`, `MAX_LISTING_AGE`) — **only
  enforced for sources that actually expose a posted date**. Property Finder does
  (verified live); Bayut and Dubizzle's search-results cards don't expose one, so
  their listings currently skip this check rather than being wrongly dropped. See the
  "No listed_at or coordinates" comments in `scanner/sources/bayut.py`/`dubizzle.py`.

## Map view

The dashboard has a List/Map toggle (Leaflet + OpenStreetMap, no API key needed).
Same caveat as the freshness filter: only listings with coordinates get a marker.
Property Finder provides them on every listing (verified); Bayut/Dubizzle currently
don't (same reason as above); Facebook/Apify is best-effort depending on what that
actor's dataset includes. The map footer always shows "X of Y listings have map
coordinates" so it's obvious when a source isn't contributing to it.

## Room-sublet estimate

Every card also shows what you'd actually net-pay if you sublet the second bedroom —
useful if you're renting the flat yourself and covering part of the cost that way.
This is **not scraped live data**: Dubai's room/shared-accommodation listings
(Dubizzle's "Rooms for rent" category, mainly) sit behind the same Imperva Incapsula
wall that blocks the Dubizzle flat scraper, so `scanner/room_rent.py` uses tiered
estimates built from published market ranges instead — three tiers (budget / mid /
premium) keyed off area name, winter/peak-season figures since that's Dubai's highest
room-demand season:

| Tier | Areas | Typical | Max |
|---|---|---|---|
| Budget | Deira, Bur Dubai, Al Nahda, International City, Muhaisnah, Al Warqa, Al Qusais, Discovery Gardens, Al Quoz | 2,200 AED/mo | 3,500 AED/mo |
| Mid (default) | everything else | 3,200 AED/mo | 4,500 AED/mo |
| Premium | same "preferred" list as the main criteria, plus Downtown/Business Bay | 4,800 AED/mo | 7,000 AED/mo |

Treat these as a ballpark for budgeting, not a quote — the real rate for a specific
room depends heavily on furnishing, the exact building, and who you rent to. If you
want to tighten these numbers, `scanner/room_rent.py` is the one place to edit.

**A bug this surfaced and fixed:** the "Preferred area" tagging used to substring-match
a bare `"jumeirah"`, which silently matched non-water areas that just have "Jumeirah"
in their name — Jumeirah Village Circle, Jumeirah Lake Towers, Jumeirah Park, Jumeirah
Heights — none of which are the actual coastal Jumeirah district. That's fixed now
(`scanner/config.py` only matches the specific real sub-areas), which also fixed the
room-rent tier for those areas — they were getting the premium tier's inflated
estimate before the fix.

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m scanner.main
open docs/index.html   # or just double-click it
```

This writes `docs/index.html` (the dashboard) and `docs/data.json` (raw matches).

## Run it on a schedule with a hosted dashboard

`.github/workflows/scan.yml` runs every 3 hours, re-scans everything, and commits the
refreshed `docs/index.html` + `docs/data.json` straight back into the repo. Vercel's
GitHub integration auto-redeploys on every push (see `vercel.json`), so that commit is
what actually keeps the live dashboard current — no extra deploy step needed once
Vercel is connected to this repo.

This used to also deploy to GitHub Pages via a second job, but that job referenced a
`github-pages` deployment environment that was never provisioned (Pages was never
enabled in repo settings) — and GitHub rejects an entire workflow run before scheduling
*any* job when a job in it references a nonexistent environment. That silently failed
**every single scheduled run** (0 jobs executed, 6/6 failures) until it was caught and
removed — meaning the schedule, including Facebook/Apify, had never actually executed;
every dashboard update up to that point came from manual local runs. If you want a
GitHub Pages mirror too, enable **Settings → Pages → Source → GitHub Actions** and
re-add a `deploy` job — just confirm Pages is actually enabled first this time.

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
