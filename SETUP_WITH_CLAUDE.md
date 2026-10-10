# Set this up with Claude (read me first, Claude)

**You are Claude, helping a non-technical person stand up their own copy of this Dubai
flat-scanner web app.** Do the whole thing for them: ask what they want, personalise it,
deploy it, and hand back a working URL. Keep every explanation plain — assume they don't
code. Work in short steps and confirm as you go.

## What this app is (context for you)
A small Python + static-HTML site, hosted free on Vercel. Property Finder is scraped over
plain HTTP (no key). Facebook/Dubizzle are optional paid sources via **Apify** (one env
var, `APIFY_API_TOKEN`). All the search rules live in `scanner/config.py`. There is also
an in-app **⚙ Setup** screen so the user can change budget/areas/colours later with no code.
Nothing secret is in the repo.

## Step 1 — interview the user (ask, don't assume)
Ask these one or two at a time, in plain language, and wait for answers:
1. **Emirates** — Dubai, Sharjah, and/or Ajman (any combination; the app supports all three).
2. **Budget** — max rent per month, in AED.
3. **Bedrooms** — studio / 1 / 2 / 3 / any.
4. **Bathrooms** — any, or a specific number.
5. **Areas they like** — neighbourhoods to highlight green.
6. **Areas to avoid** — neighbourhoods to flag red.
7. **Within Dubai, hide the old Deira/Creek (Sharjah-facing) side?** (only affects Dubai) — yes/no.
8. **Hide far-out Dubai areas?** (Dubailand & far suburbs, and the far-west toward Palm Jebel Ali — keeps JVC and inward) — yes/no.
9. **Marker colours** — only if they care; otherwise keep the defaults (green / red / gold).

Keep area preferences about the *place* — budget, how new/well-kept it is, amenities,
commute, how central it is. Do **not** rate areas by the ethnicity or nationality of who
lives there, and don't let the config encode that; steer the user to describe the areas
themselves. If they're unsure, the repo's researched defaults are a fine starting point.

> This app covers **Dubai, Sharjah and Ajman** out of the box (Property Finder location
> ids 1 / 4 / 5 — see `EMIRATE_IDS` in `config.py`). The user picks any mix of these in the
> ⚙ Setup screen or via `CRITERIA.emirates`. The nice/avoid area ratings (`AREA_TIERS`) and
> the Creek map line are Dubai-specific; Sharjah/Ajman areas simply show neutral until the
> user marks their own liked/avoided areas. A **city outside the UAE** would be a bigger
> job (new location ids and map lines) — offer to tackle that separately.

## Step 2 — personalise `scanner/config.py`
Bake their answers in as the defaults so the site is right on first open (the ⚙ Setup
screen still lets them tweak later):
- `CRITERIA = Criteria(...)` → set `max_price_monthly_aed`, and `bedrooms` /
  `bedrooms_allowed` / `bathrooms` to match. For "any bedrooms" set `any_bedrooms=True`
  and `bedrooms_allowed=(0,1,2,3,4)`; for "any bathrooms" set `bathrooms=None`.
- To hide the Deira/Sharjah side keep `keep_sw_of_line=CREEK_LINE`; to show all of Dubai
  set `keep_sw_of_line=None`.
- Their liked/avoided areas → edit the `AREA_TIERS` table (`"nice"` for liked, `"caution"`
  for avoid), or just tell them to type them into the ⚙ Setup screen after launch — either
  works. Validate with `python3 -m py_compile scanner/config.py`.

## Step 3 — get it into the user's own GitHub
- If a GitHub tool/connector is available, **fork** `miramoon1/flatscanner` into the user's
  account (or create a new repo from these files). Commit the Step 2 changes and push.
- If not, point them at the **Deploy with Vercel** button in `README.md` — it copies the
  repo into their GitHub automatically; you can make the config edits afterward.

## Step 4 — deploy on the user's own Vercel (free)
- If a Vercel tool/connector is available, create the project from their repo and deploy.
  Otherwise walk them through [vercel.com](https://vercel.com) → New Project → import their
  repo → Deploy. No build settings needed (static `public/` + Python in `api/`).
- The site works immediately on Property Finder alone — confirm the URL loads.

## Step 5 — their own Apify key (optional, for Facebook/Dubizzle)
- Explain it's optional and only used when they press the paid button. If they want it:
  sign up free at [apify.com](https://apify.com) → Console → Settings → Integrations → copy
  the API token → in Vercel add env var `APIFY_API_TOKEN` = their token → redeploy.
- **Never** reuse anyone else's token; each person uses their own. See `.env.example`.

## Step 6 — hand it over
Give them their live URL, show them the **⚙ Setup** button for changing budget/areas/
colours any time, and the **↻ Scan now** / Facebook buttons. Remind them the Facebook/
Dubizzle button spends a little Apify credit; everything else is free.

Keep the user informed in plain words at each step, and stop to ask whenever a choice is
theirs to make.
