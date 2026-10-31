#!/usr/bin/env python3
"""Writes src/pages/map.html (the /map/ page) from src/data/us-map.json and src/data/cities.json.
Run after changing either data file, src/assets/map.js, or the set of city pages:  python3 tools/make_map_page.py
Deterministic: same inputs give byte-identical output. Every dot links to an existing src/pages/<slug>.html page."""
import hashlib, html, json, math
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
LASTMOD = "2026-10-29"
m = json.loads((SRC / "data" / "us-map.json").read_text())
cdata = json.loads((SRC / "data" / "cities.json").read_text())
STATES = cdata["states"]  # e.g. {"CO": "Colorado", "WY": "Wyoming"}, in display order
cities = cdata["cities"]
for c in cities:
    pg = SRC / "pages" / f"{c['slug']}.html"
    if not pg.exists(): raise SystemExit(f"no city page for {c['slug']}")
    if c["state"] not in STATES: raise SystemExit(f"unknown state for {c['slug']}")
    if f"City guide · {c['name']}, {STATES[c['state']]}" not in pg.read_text(): raise SystemExit(f"{c['slug']} page does not name {STATES[c['state']]}")
city_pages = {p.stem for p in (SRC / "pages").glob("*.html") if '"article"' in p.read_text()[:600] and "City guide ·" in p.read_text()}
if city_pages != {c["slug"] for c in cities}:
    raise SystemExit(f"city pages and map data differ: {sorted(city_pages ^ {c['slug'] for c in cities})}")
cities = sorted(cities, key=lambda c: c["name"])
_ov = [c for c in cities if c.get("coord_note")]
OVN = "".join(" " + c["coord_note"] for c in _ov)
# Label priority when labels would collide: the order of the home page's City guides list (largest cities first).
import re
home = (SRC / "pages" / "index.html").read_text()
order = re.findall(r'<li><a href="/([a-z-]+)/">', home[home.index('id="cities"'):])
pri = {slug: i for i, slug in enumerate(order)}
def gap(c):  # distance to the nearest other city, in viewBox units; labels show once this is wide enough on screen
    return min(math.hypot(c["x"] - o["x"], c["y"] - o["y"]) for o in cities if o is not c)
den = next(c for c in cities if c["slug"] == "denver")
used = [st for st in STATES if any(c["state"] == st for c in cities)]
count = lambda st: sum(c["state"] == st for c in cities)
def and_list(xs):  # "A", "A and B", "A, B and C"
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]
st_names = and_list([STATES[st] for st in used])
metro = [c for c in cities if math.hypot(c["x"] - den["x"], c["y"] - den["y"]) <= 9.5]
mb = [min(c["x"] for c in metro), min(c["y"] for c in metro), max(c["x"] for c in metro), max(c["y"] for c in metro)]
f = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
slc = next((c for c in cities if c["slug"] == "salt-lake-city"), None)
slca = [c for c in cities if slc and math.hypot(c["x"] - slc["x"], c["y"] - slc["y"]) <= 9.5]
def padbox(cs, mn=6):  # bounding box of cs, widened to at least mn viewBox units each way
    x0, y0, x1, y1 = min(c["x"] for c in cs), min(c["y"] for c in cs), max(c["x"] for c in cs), max(c["y"] for c in cs)
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, mn), max(y1 - y0, mn)
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
slcb = padbox(slca) if len(slca) >= 2 else []
slc_btn = '\n<button type="button" data-act="slc">Salt Lake area</button>' if slcb else ""
slc_attr = f' data-slc="{" ".join(f(v) for v in slcb)}"' if slcb else ""
oma = next((c for c in cities if c["slug"] == "omaha"), None)
omaa = [c for c in cities if oma and math.hypot(c["x"] - oma["x"], c["y"] - oma["y"]) <= 9.5]
# One Omaha city zooms to a small box around it; two or more nearby (e.g. Bellevue) to their padded bounding box.
omab = padbox(omaa) if omaa else []
oma_btn = '\n<button type="button" data-act="omaha">Omaha area</button>' if omab else ""
oma_attr = f' data-omaha="{" ".join(f(v) for v in omab)}"' if omab else ""
ne_btn = '\n<button type="button" data-act="ne">Zoom to Nebraska</button>' if "NE" in used else ""
ne_attr = f' data-ne="{" ".join(f(v) for v in m["nebraska_bounds"])}"' if "NE" in used else ""
ne_path = f'\n<path class="ne" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["nebraska"]}"/>' if "NE" in used else ""
kc = next((c for c in cities if c["slug"] == "kansas-city"), None)
kca = [c for c in cities if kc and math.hypot(c["x"] - kc["x"], c["y"] - kc["y"]) <= 9.5]
# Kansas City, Kansas and its Johnson County neighbors (Overland Park, Olathe) share one padded box, like the Omaha area.
kcb = padbox(kca) if kca else []
kc_btn = '\n<button type="button" data-act="kc">Kansas City area</button>' if kcb else ""
kc_attr = f' data-kc="{" ".join(f(v) for v in kcb)}"' if kcb else ""
ks_btn = '\n<button type="button" data-act="ks">Zoom to Kansas</button>' if "KS" in used else ""
ks_attr = f' data-ks="{" ".join(f(v) for v in m["kansas_bounds"])}"' if "KS" in used else ""
ks_path = f'\n<path class="ks" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["kansas"]}"/>' if "KS" in used else ""
nm_btn = '\n<button type="button" data-act="nm">Zoom to New Mexico</button>' if "NM" in used else ""
nm_attr = f' data-nm="{" ".join(f(v) for v in m["new_mexico_bounds"])}"' if "NM" in used else ""
nm_path = f'\n<path class="nm" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["new_mexico"]}"/>' if "NM" in used else ""
az_btn = '\n<button type="button" data-act="az">Zoom to Arizona</button>' if "AZ" in used else ""
az_attr = f' data-az="{" ".join(f(v) for v in m["arizona_bounds"])}"' if "AZ" in used else ""
az_path = f'\n<path class="az" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["arizona"]}"/>' if "AZ" in used else ""
phx = next((c for c in cities if c["slug"] == "phoenix"), None)
phxa = [c for c in cities if phx and math.hypot(c["x"] - phx["x"], c["y"] - phx["y"]) <= 9.5]
# Phoenix and its East Valley neighbors (Mesa, Gilbert, Chandler) share one padded box, like the Kansas City area; shown once two or more are on the map.
phxb = padbox(phxa) if len(phxa) >= 2 else []
phx_btn = '\n<button type="button" data-act="phx">Phoenix area</button>' if phxb else ""
phx_attr = f' data-phx="{" ".join(f(v) for v in phxb)}"' if phxb else ""
sd_btn = '\n<button type="button" data-act="sd">Zoom to South Dakota</button>' if "SD" in used else ""
sd_attr = f' data-sd="{" ".join(f(v) for v in m["south_dakota_bounds"])}"' if "SD" in used else ""
sd_path = f'\n<path class="sd" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["south_dakota"]}"/>' if "SD" in used else ""
nd_btn = '\n<button type="button" data-act="nd">Zoom to North Dakota</button>' if "ND" in used else ""
nd_attr = f' data-nd="{" ".join(f(v) for v in m["north_dakota_bounds"])}"' if "ND" in used else ""
nd_path = f'\n<path class="nd" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["north_dakota"]}"/>' if "ND" in used else ""
mt_btn = '\n<button type="button" data-act="mt">Zoom to Montana</button>' if "MT" in used else ""
mt_attr = f' data-mt="{" ".join(f(v) for v in m["montana_bounds"])}"' if "MT" in used else ""
mt_path = f'\n<path class="mt" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["montana"]}"/>' if "MT" in used else ""
nv_btn = '\n<button type="button" data-act="nv">Zoom to Nevada</button>' if "NV" in used else ""
nv_attr = f' data-nv="{" ".join(f(v) for v in m["nevada_bounds"])}"' if "NV" in used else ""
nv_path = f'\n<path class="nv" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["nevada"]}"/>' if "NV" in used else ""
lv = next((c for c in cities if c["slug"] == "las-vegas"), None)
lva = [c for c in cities if lv and math.hypot(c["x"] - lv["x"], c["y"] - lv["y"]) <= 9.5]
# Las Vegas and its Clark County neighbors (Henderson, North Las Vegas) share one padded box, like the Phoenix area; shown once two or more are on the map.
lvb = padbox(lva) if len(lva) >= 2 else []
lv_btn = '\n<button type="button" data-act="lv">Las Vegas area</button>' if lvb else ""
lv_attr = f' data-lv="{" ".join(f(v) for v in lvb)}"' if lvb else ""
rno = next((c for c in cities if c["slug"] == "reno"), None)
rnoa = [c for c in cities if rno and math.hypot(c["x"] - rno["x"], c["y"] - rno["y"]) <= 9.5]
# Reno and Sparks share one padded box; shown once both are on the map.
rnob = padbox(rnoa) if len(rnoa) >= 2 else []
rno_btn = '\n<button type="button" data-act="reno">Reno area</button>' if rnob else ""
rno_attr = f' data-reno="{" ".join(f(v) for v in rnob)}"' if rnob else ""
id_btn = '\n<button type="button" data-act="id">Zoom to Idaho</button>' if "ID" in used else ""
id_attr = f' data-id="{" ".join(f(v) for v in m["idaho_bounds"])}"' if "ID" in used else ""
id_path = f'\n<path class="id" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["idaho"]}"/>' if "ID" in used else ""
boi = next((c for c in cities if c["slug"] == "boise"), None)
boia = [c for c in cities if boi and math.hypot(c["x"] - boi["x"], c["y"] - boi["y"]) <= 9.5]
# Boise and its Treasure Valley neighbors (Meridian, Nampa, Caldwell) share one padded box, like the Las Vegas area; shown once two or more are on the map.
boib = padbox(boia) if len(boia) >= 2 else []
boi_btn = '\n<button type="button" data-act="boi">Boise area</button>' if boib else ""
boi_attr = f' data-boi="{" ".join(f(v) for v in boib)}"' if boib else ""
wa_btn = '\n<button type="button" data-act="wa">Zoom to Washington</button>' if "WA" in used else ""
wa_attr = f' data-wa="{" ".join(f(v) for v in m["washington_bounds"])}"' if "WA" in used else ""
wa_path = f'\n<path class="wa" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["washington"]}"/>' if "WA" in used else ""
sea = next((c for c in cities if c["slug"] == "seattle"), None)
seaa = [c for c in cities if sea and math.hypot(c["x"] - sea["x"], c["y"] - sea["y"]) <= 9.5]
# Seattle and its Puget Sound neighbors (Tacoma, Bellevue, WA) share one padded box, like the Boise area; shown once two or more are on the map.
seab = padbox(seaa) if len(seaa) >= 2 else []
sea_btn = '\n<button type="button" data-act="sea">Seattle area</button>' if seab else ""
sea_attr = f' data-sea="{" ".join(f(v) for v in seab)}"' if seab else ""
or_btn = '\n<button type="button" data-act="or">Zoom to Oregon</button>' if "OR" in used else ""
or_attr = f' data-or="{" ".join(f(v) for v in m["oregon_bounds"])}"' if "OR" in used else ""
or_path = f'\n<path class="or" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["oregon"]}"/>' if "OR" in used else ""
pdx = next((c for c in cities if c["slug"] == "portland"), None)
pdxa = [c for c in cities if pdx and math.hypot(c["x"] - pdx["x"], c["y"] - pdx["y"]) <= 9.5]
# Portland and its neighbors (Gresham, Hillsboro and Vancouver, WA across the Columbia) share one padded box, like the Seattle area; shown once two or more are on the map.
pdxb = padbox(pdxa) if len(pdxa) >= 2 else []
pdx_btn = '\n<button type="button" data-act="pdx">Portland area</button>' if pdxb else ""
pdx_attr = f' data-pdx="{" ".join(f(v) for v in pdxb)}"' if pdxb else ""
ca_btn = '\n<button type="button" data-act="ca">Zoom to California</button>' if "CA" in used else ""
ca_attr = f' data-ca="{" ".join(f(v) for v in m["california_bounds"])}"' if "CA" in used else ""
ca_path = f'\n<path class="ca" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["california"]}"/>' if "CA" in used else ""
sfo = next((c for c in cities if c["slug"] == "san-francisco"), None)
baya = [c for c in cities if sfo and math.hypot(c["x"] - sfo["x"], c["y"] - sfo["y"]) <= 9.5]
# San Francisco and San Jose share one padded Bay Area box, like the Seattle and Portland areas; shown once two or more are on the map.
bayb = padbox(baya) if len(baya) >= 2 else []
bay_btn = '\n<button type="button" data-act="bay">Bay Area</button>' if bayb else ""
bay_attr = f' data-bay="{" ".join(f(v) for v in bayb)}"' if bayb else ""
ok_btn = '\n<button type="button" data-act="ok">Zoom to Oklahoma</button>' if "OK" in used else ""
ok_attr = f' data-ok="{" ".join(f(v) for v in m["oklahoma_bounds"])}"' if "OK" in used else ""
ok_path = f'\n<path class="ok" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["oklahoma"]}"/>' if "OK" in used else ""
tx_btn = '\n<button type="button" data-act="tx">Zoom to Texas</button>' if "TX" in used else ""
tx_attr = f' data-tx="{" ".join(f(v) for v in m["texas_bounds"])}"' if "TX" in used else ""
tx_path = f'\n<path class="tx" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["texas"]}"/>' if "TX" in used else ""
dfw = next((c for c in cities if c["slug"] == "dallas"), None)
dfwa = [c for c in cities if dfw and math.hypot(c["x"] - dfw["x"], c["y"] - dfw["y"]) <= 12]
# Dallas and Fort Worth (about 11 map units apart, wider than the 9.5 used for other areas) share one padded box; shown once both are on the map.
dfwb = padbox(dfwa) if len(dfwa) >= 2 else []
dfw_btn = '\n<button type="button" data-act="dfw">Dallas–Fort Worth area</button>' if dfwb else ""
dfw_attr = f' data-dfw="{" ".join(f(v) for v in dfwb)}"' if dfwb else ""
atx = next((c for c in cities if c["slug"] == "austin"), None)
atxa = [c for c in cities if atx and math.hypot(c["x"] - atx["x"], c["y"] - atx["y"]) <= 25]
# Austin and San Antonio (about 24 map units apart, wider than the 12 used for Dallas–Fort Worth) share one padded box; shown once both are on the map.
atxb = padbox(atxa) if len(atxa) >= 2 else []
atx_btn = '\n<button type="button" data-act="atx">Austin–San Antonio area</button>' if atxb else ""
atx_attr = f' data-atx="{" ".join(f(v) for v in atxb)}"' if atxb else ""
mn_btn = '\n<button type="button" data-act="mn">Zoom to Minnesota</button>' if "MN" in used else ""
mn_attr = f' data-mn="{" ".join(f(v) for v in m["minnesota_bounds"])}"' if "MN" in used else ""
mn_path = f'\n<path class="mn" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["minnesota"]}"/>' if "MN" in used else ""
ia_btn = '\n<button type="button" data-act="ia">Zoom to Iowa</button>' if "IA" in used else ""
ia_attr = f' data-ia="{" ".join(f(v) for v in m["iowa_bounds"])}"' if "IA" in used else ""
ia_path = f'\n<path class="ia" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m["iowa"]}"/>' if "IA" in used else ""
JS_V = hashlib.sha256((SRC / "assets" / "map.js").read_bytes()).hexdigest()[:10]
e = lambda s: html.escape(s, quote=True)

# A city name used in more than one state (e.g. Bellevue) is labeled with its state code on the map, so the two dots are told apart.
dup_names = {c["name"] for c in cities if sum(o["name"] == c["name"] for o in cities) > 1}
dots = []
for c in cities:
    name = e(c["name"])
    dots.append(f'<a href="/{c["slug"]}/" aria-label="{name}, {STATES[c["state"]]} city guide"><title>{name}, {c["state"]}</title>'
                f'<circle class="hit" cx="{f(c["x"])}" cy="{f(c["y"])}" r="4"/>'
                f'<circle class="dot" cx="{f(c["x"])}" cy="{f(c["y"])}" r="2.5"/>'
                f'<text class="lbl" data-x="{f(c["x"])}" data-y="{f(c["y"])}" data-gap="{f(gap(c))}" data-pri="{pri[c['slug']]}" style="display:none">{name + ", " + c["state"] if c["name"] in dup_names else name}</text></a>')
items = "\n".join(f'<h3 id="list-{STATES[st].lower().replace(' ', '-')}">{STATES[st]}</h3>\n<ul class="city-list">\n'
                  + "\n".join(f'<li><a href="/{c["slug"]}/">{e(c["name"])}, {STATES[st]}</a></li>' for c in cities if c["state"] == st)
                  + "\n</ul>" for st in used)
lede_n = and_list([f"{count(st)} in {STATES[st]}" for st in used])
plural = lambda n, one, many: f"{n} {one if n == 1 else many}"
n_cities, n_states = plural(len(cities), "city", "cities"), plural(len(used), "state", "states")
n_guides = plural(len(cities), "city guide", "city guides")
# "31 cities: 20 in Colorado, ... and 1 in Nebraska"; with one state, "20 cities in Colorado" (no breakdown).
summary = lambda noun: f"{noun} in {st_names}" if len(used) == 1 else f"{noun}: {lede_n}"
# Title and description scale with the data: counts only, no city names. Use the first that fits.
titles = [f"Errand Desk City Guides Map: {n_cities.title()} in {n_states.title()}", f"Errand Desk Map: {n_cities.title()} in {n_states.title()}"]
descs = [f"Map of our {summary(n_guides)}. Select a city to open its printing, fax, notary and passport guide.",
         f"Map of our {n_guides} in {n_states}: {st_names}. Select a city to open its printing, fax, notary and passport guide.",
         f"Map of our {n_guides} in {n_states}. Select a city to open its printing, fax, notary and passport guide."]
meta = {"title": next(t for t in titles if len(t) <= 60),
        "description": next(d for d in descs if len(d) <= 155),
        "nav": "map", "lastmod": LASTMOD, "schema": "page"}
vb = " ".join(str(v) for v in m["viewBox"])
page = f"""<!--meta
{json.dumps(meta)}
-->
<!-- Generated by tools/make_map_page.py from src/data/us-map.json and src/data/cities.json. Edit those, not this file. -->
<article>
<p class="meta">Map · Updated <time datetime="{LASTMOD}">Oct 29, 2026</time></p>
<h1>Map of our city guides</h1>
<p class="lede">Errand Desk has guides for {summary(n_cities)}. Each dot on the map is one city guide. Zoom in on a state and select a dot to open that city's page, or use the same guides in the list below the map, grouped by state.</p>

<div class="usmap" id="usmap">
<div class="usmap-tools" role="toolbar" aria-label="Map zoom" hidden>
<button type="button" data-act="in" aria-label="Zoom in">+</button>
<button type="button" data-act="out" aria-label="Zoom out">&minus;</button>
<button type="button" data-act="reset">Reset</button>
<button type="button" data-act="co">Zoom to Colorado</button>
<button type="button" data-act="wy">Zoom to Wyoming</button>
<button type="button" data-act="ut">Zoom to Utah</button>{ne_btn}{ks_btn}{nm_btn}{az_btn}{sd_btn}{nd_btn}{mt_btn}{nv_btn}{id_btn}{wa_btn}{or_btn}{ca_btn}{ok_btn}{tx_btn}{dfw_btn}{atx_btn}{mn_btn}{ia_btn}
<button type="button" data-act="metro">Denver area</button>{slc_btn}{oma_btn}{kc_btn}{phx_btn}{lv_btn}{rno_btn}{boi_btn}{sea_btn}{pdx_btn}{bay_btn}
</div>
<svg viewBox="{vb}" data-co="{' '.join(f(v) for v in m['colorado_bounds'])}" data-wy="{' '.join(f(v) for v in m['wyoming_bounds'])}" data-ut="{' '.join(f(v) for v in m['utah_bounds'])}" data-metro="{' '.join(f(v) for v in mb)}"{slc_attr}{ne_attr}{oma_attr}{ks_attr}{nm_attr}{az_attr}{sd_attr}{nd_attr}{mt_attr}{nv_attr}{id_attr}{wa_attr}{or_attr}{ca_attr}{ok_attr}{tx_attr}{dfw_attr}{atx_attr}{mn_attr}{ia_attr}{kc_attr}{phx_attr}{lv_attr}{rno_attr}{boi_attr}{sea_attr}{pdx_attr}{bay_attr} role="group" aria-label="Map of the United States with a dot for each city guide in {st_names}">
<path class="nation" d="{m['nation']}"/>
<path class="borders" d="{m['borders']}"/>
<path class="co" d="{m['colorado']}"/>
<path class="wy" d="{m['wyoming']}"/>
<path class="ut" style="fill:#e3eef6;stroke:var(--accent);stroke-width:1.2;vector-effect:non-scaling-stroke" d="{m['utah']}"/>{ne_path}{ks_path}{nm_path}{az_path}{sd_path}{nd_path}{mt_path}{nv_path}{id_path}{wa_path}{or_path}{ca_path}{ok_path}{tx_path}{mn_path}{ia_path}
<g class="cities">
{chr(10).join(dots)}
</g>
</svg>
<p class="small usmap-help">Drag to move the map. Zoom with the buttons, your mouse wheel or a two-finger pinch. <span class="usmap-status" aria-live="polite"></span></p>
</div>

<h2 id="list">City guides on this map</h2>
{items}

<h2 id="about-map">About this map</h2>
<p class="small">State outlines: U.S. Census Bureau cartographic boundary files (2017, 1:10,000,000), via the <a href="https://github.com/topojson/us-atlas">us-atlas</a> project (ISC license), drawn in an Albers equal-area projection with Alaska and Hawaii shown as insets. City dots: the internal point of each city in the U.S. Census Bureau's <a href="https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html">2025 Gazetteer places file</a>.{OVN} A dot marks the city, not a specific office. The map needs JavaScript to zoom; the list above works without it.</p>
</article>
<script src="/assets/map.js?v={JS_V}" defer></script>"""
(SRC / "pages" / "map.html").write_text(page + "\n")
print("wrote src/pages/map.html:", len(cities), "dots; metro:", [c["slug"] for c in metro], "; salt lake area:", [c["slug"] for c in slca], "; omaha area:", [c["slug"] for c in omaa], "; kansas city area:", [c["slug"] for c in kca], "; phoenix area:", [c["slug"] for c in phxa]); print("title:", meta["title"]); print("description:", meta["description"])
