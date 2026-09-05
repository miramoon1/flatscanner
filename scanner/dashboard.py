from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import Criteria
from .filters import is_preferred_area
from .models import Listing

DUBAI_CENTER = (25.2048, 55.2708)

# Burj Khalifa silhouette (stepped taper + spire) on a sunset gradient — reads clearly
# even at 16x16, verified by rendering it at 16/32/64/128px before wiring it in.
FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#f7d774"/>
      <stop offset="1" stop-color="#e8794f"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="14" fill="url(#sky)"/>
  <polygon fill="#1a2332" points="
    44,58 41,58 41,49 38,49 38,41 36,41 36,33 34,33 34,24 33,24 33,15 32.6,15 32.6,4
    31.4,4 31.4,15 31,15 31,24 30,24 30,33 28,33 28,41 26,41 26,49 23,49 23,58 20,58
    20,60 44,60
  "/>
</svg>
"""

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Dubai Flat Scanner</title>
<link rel="icon" type="image/svg+xml" href="favicon.svg" />
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
<style>
  :root {{
    --bg: #f7f5f2; --card: #ffffff; --text: #1a1a1a; --muted: #6b6b6b;
    --accent: #0f6f5c; --border: #e6e2db; --badge: #eaf5f1;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#15181a; --card:#1f2326; --text:#f1efe9; --muted:#9aa1a6; --accent:#4fd1b5; --border:#2c3134; --badge:#1c2b28; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text); font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
  header {{ padding: 28px 24px 16px; max-width: 1100px; margin: 0 auto; }}
  h1 {{ margin: 0 0 4px; font-size: 1.5rem; }}
  .meta {{ color: var(--muted); font-size: 0.9rem; }}
  .criteria {{ color: var(--muted); font-size: 0.85rem; margin-top: 8px; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 8px 24px 48px; }}
  .view-toggle {{ display: flex; gap: 8px; margin-bottom: 16px; }}
  .view-toggle button {{
    font: inherit; font-weight: 600; font-size: 0.85rem; padding: 7px 16px; border-radius: 999px;
    border: 1px solid var(--border); background: var(--card); color: var(--text); cursor: pointer;
  }}
  .view-toggle button[aria-pressed="true"] {{ background: var(--accent); color: var(--card); border-color: var(--accent); }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; }}
  .card img {{ width: 100%; height: 160px; object-fit: cover; background: var(--border); }}
  .card-body {{ padding: 14px 16px 16px; display: flex; flex-direction: column; gap: 6px; flex: 1; }}
  .price {{ font-size: 1.15rem; font-weight: 700; color: var(--accent); }}
  .title {{ font-weight: 600; font-size: 0.95rem; line-height: 1.3; }}
  .area {{ color: var(--muted); font-size: 0.85rem; }}
  .row {{ display: flex; justify-content: space-between; align-items: center; margin-top: auto; padding-top: 8px; }}
  .badges {{ display:flex; gap:6px; flex-wrap: wrap; }}
  .badge {{ font-size: 0.72rem; background: var(--badge); color: var(--accent); padding: 2px 8px; border-radius: 999px; font-weight: 600; }}
  .source {{ font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }}
  a.card {{ text-decoration: none; color: inherit; }}
  a.card:hover {{ border-color: var(--accent); }}
  .empty {{ color: var(--muted); padding: 40px 0; text-align: center; }}
  #map {{ height: 70vh; min-height: 420px; width: 100%; border-radius: 12px; border: 1px solid var(--border); }}
  .map-note {{ color: var(--muted); font-size: 0.8rem; margin-top: 8px; }}
  .leaflet-popup-content b {{ color: var(--accent); }}
  [hidden] {{ display: none !important; }}
</style>
</head>
<body>
<header>
  <h1>Dubai Flat Scanner</h1>
  <div class="meta">Last updated {generated_at} &middot; {count} matching listings</div>
  <div class="criteria">Budget &le; {max_price} AED/month &middot; {bedrooms} bed / {bathrooms} bath &middot; excluding Marina &amp; JLT &middot; Jumeirah &amp; water-adjacent areas preferred &middot; listed within the last 30 days</div>
</header>
<main>
  <div class="view-toggle" role="tablist">
    <button id="btn-list" type="button" aria-pressed="true">List</button>
    <button id="btn-map" type="button" aria-pressed="false">Map</button>
  </div>

  <div class="grid" id="list-view">
    {cards}
  </div>
  {empty_state}

  <div id="map-view" hidden>
    <div id="map"></div>
    <div class="map-note" id="map-note"></div>
  </div>
</main>

<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
<script>
  const MAP_POINTS = {map_points_json};

  const btnList = document.getElementById('btn-list');
  const btnMap = document.getElementById('btn-map');
  const listView = document.getElementById('list-view');
  const mapView = document.getElementById('map-view');
  const mapNote = document.getElementById('map-note');

  let map = null;

  function showList() {{
    listView.hidden = false;
    mapView.hidden = true;
    btnList.setAttribute('aria-pressed', 'true');
    btnMap.setAttribute('aria-pressed', 'false');
  }}

  function showMap() {{
    listView.hidden = true;
    mapView.hidden = false;
    btnList.setAttribute('aria-pressed', 'false');
    btnMap.setAttribute('aria-pressed', 'true');

    if (!map) {{
      map = L.map('map').setView([{center_lat}, {center_lon}], 11);
      L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19,
      }}).addTo(map);

      const bounds = [];
      MAP_POINTS.forEach(function (p) {{
        const marker = L.marker([p.lat, p.lon]).addTo(map);
        const priceText = p.price != null ? p.price.toLocaleString() + ' AED/mo' : 'Price N/A';
        marker.bindPopup(
          '<b>' + priceText + '</b><br>' +
          p.title.replace(/</g, '&lt;') + '<br>' +
          '<span style="color:#6b6b6b">' + p.area.replace(/</g, '&lt;') + ' &middot; ' + p.source + '</span><br>' +
          '<a href="' + p.url + '" target="_blank" rel="noopener">View listing &rarr;</a>'
        );
        bounds.push([p.lat, p.lon]);
      }});
      if (bounds.length) {{
        map.fitBounds(bounds, {{ padding: [30, 30], maxZoom: 14 }});
      }}
      mapNote.textContent = MAP_POINTS.length
        ? MAP_POINTS.length + ' of {count} listings have map coordinates (not every source provides them yet).'
        : 'None of the current listings have map coordinates yet — check back after the next scan.';
    }}

    // Leaflet miscalculates tile sizing when initialized inside a container
    // that was `hidden` (display:none) at init time — force a recalc now that
    // it's visible.
    setTimeout(function () {{ map.invalidateSize(); }}, 0);
  }}

  btnList.addEventListener('click', showList);
  btnMap.addEventListener('click', showMap);
</script>
</body>
</html>
"""

CARD_TEMPLATE = """
<a class="card" href="{url}" target="_blank" rel="noopener">
  <img src="{image_url}" alt="" loading="lazy" onerror="this.style.display='none'" />
  <div class="card-body">
    <div class="price">{price} AED/mo</div>
    <div class="title">{title}</div>
    <div class="area">{area}</div>
    <div class="row">
      <div class="badges">
        {preferred_badge}
      </div>
      <div class="source">{source}</div>
    </div>
  </div>
</a>
"""


def _fmt_price(v: float | None) -> str:
    if v is None:
        return "?"
    return f"{v:,.0f}"


def render_dashboard(listings: list[Listing], criteria: Criteria, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "favicon.svg").write_text(FAVICON_SVG, encoding="utf-8")

    data = [l.to_dict() for l in listings]
    (out_dir / "data.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    cards_html = []
    map_points = []
    for l in listings:
        preferred = is_preferred_area(l, criteria)
        cards_html.append(
            CARD_TEMPLATE.format(
                url=l.url,
                image_url=l.image_url or "",
                price=_fmt_price(l.price_monthly_aed),
                title=l.title,
                area=l.area,
                preferred_badge='<span class="badge">Preferred area</span>' if preferred else "",
                source=l.source,
            )
        )
        if l.latitude is not None and l.longitude is not None:
            map_points.append(
                {
                    "lat": l.latitude,
                    "lon": l.longitude,
                    "title": l.title,
                    "area": l.area,
                    "price": l.price_monthly_aed,
                    "url": l.url,
                    "source": l.source,
                }
            )

    center_lat, center_lon = DUBAI_CENTER
    if map_points:
        center_lat = sum(p["lat"] for p in map_points) / len(map_points)
        center_lon = sum(p["lon"] for p in map_points) / len(map_points)

    page = PAGE_TEMPLATE.format(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        count=len(listings),
        max_price=f"{criteria.max_price_monthly_aed:,}",
        bedrooms=criteria.bedrooms,
        bathrooms=criteria.bathrooms,
        cards="\n".join(cards_html),
        empty_state='<div class="empty">No matching listings right now — check back later.</div>' if not listings else "",
        map_points_json=json.dumps(map_points, ensure_ascii=False),
        center_lat=center_lat,
        center_lon=center_lon,
    )
    (out_dir / "index.html").write_text(page, encoding="utf-8")
