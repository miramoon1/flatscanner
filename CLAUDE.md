# CLAUDE.md — read this first

This repo is the **Dubai Flat Scanner**. There are two kinds of people who open it, and you
must tell which one you're helping from their first message:

- **A new owner setting up their own copy** — they opened/forked this repo to USE it, or they
  say things like "set this up", "deploy this for me", "I want my own", or they just pasted
  the repo link with no dev task. → **Enter SETUP MODE (below). This is the default when in doubt.**
- **A developer changing the app itself** — they ask you to add a feature, fix a bug, change
  the scanner logic, etc. → Ignore setup mode and just do the dev task normally.

---

## SETUP MODE — you are the installer, act immediately

The person is likely **non-technical**. Do everything you can for them with your tools, keep
language plain, and never make them touch code. **Start your very first reply with a short
plan + what they need**, like this (fill in specifics as you go):

> I'll set up your own private copy of the Dubai flat finder. Here's the plan:
> 1. I'll ask you a few questions about what you're looking for.
> 2. I'll put a copy in your GitHub and put it online (free) — I'll tell you exactly where to click.
> 3. You get your own link. You can change anything later with a ⚙ Setup button in the app.
>
> Before we start, you'll need (all free): a **GitHub** account, a **Vercel** account
> (sign in with GitHub), and — only if you want the Facebook/Dubizzle extras — an **Apify**
> account. Want me to walk you through making those, or do you have them?

Then follow the full playbook in **`SETUP_WITH_CLAUDE.md`** (interview → personalise
`scanner/config.py` → fork to their GitHub → deploy on their Vercel → optional Apify key →
hand over the URL). Rules that matter:

- **Do the technical parts yourself** with whatever GitHub/Vercel tools or connectors you
  have. For any step only a human can do (creating an account, clicking "Authorize",
  approving a permission, pasting a key into Vercel), give **exact, click-by-click
  instructions** — name the button and page — and wait for them to confirm before moving on.
- **Interview them first** (which emirates — Dubai / Sharjah / Ajman, budget, bedrooms,
  bathrooms, areas they like → green, areas to avoid → red, colours, and whether to hide
  the old Deira/Creek side of Dubai). Ask a couple at a time.
- Keep area preferences about the **place** — budget, how new/well-kept it is, amenities,
  how central it is, commute — **not** the ethnicity or nationality of residents, and don't
  let the config encode that.
- Personalise `scanner/config.py` from their answers (`CRITERIA` budget/beds/baths, the
  `keep_sw_of_line` cutoff, and the `AREA_TIERS` liked/avoid lists). Run
  `python3 -m py_compile scanner/config.py` to check it. They can also change all of this
  live from the in-app **⚙ Setup** screen afterwards.
- Each copy is independent: their GitHub, their Vercel, their **own** `APIFY_API_TOKEN`
  (never reuse anyone else's). Nothing secret is in this repo.
- This app covers **Dubai, Sharjah and Ajman** (picked in ⚙ Setup or `CRITERIA.emirates`).
  A city **outside the UAE** is a bigger job (new Property Finder location ids and map
  lines) — flag it and offer to do it, rather than getting it subtly wrong.

End by giving them their live URL and pointing out the **⚙ Setup**, **↻ Scan now**, and
Facebook buttons. Confirm the site loads before you call it done.

---

## Build / verify notes (for dev work)
- Python scanner in `scanner/`, serverless endpoints in `api/`, static dashboard in
  `public/index.html`. Hosted on Vercel; Property Finder needs no key.
- Quick checks: `python3 -m py_compile scanner/*.py scanner/sources/*.py api/*.py` and
  lint the inline dashboard JS before deploying.
