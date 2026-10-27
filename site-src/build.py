#!/usr/bin/env python3
"""Tiny static builder: wraps src/pages/**.html in src/layout.html -> public/ (or --out DIR).
Each page starts with <!--meta {json} --> (title, description, nav, optional lastmod, optional noindex,
optional schema: "website" | "article" | "collection" | "page").
URL scheme: src/pages/index.html -> /, src/pages/about.html -> /about/,
src/pages/guides/fax-prices.html -> /guides/fax-prices/, src/pages/guides/index.html -> /guides/.
Config: site.config.json (base_url, default_lastmod, cf_analytics_token). Env SITE_BASE_URL overrides base_url.
Also writes public/sitemap.xml and public/robots.txt, and copies src/static/* (icons, og-image.png) to the site root.
SEO: every page gets Open Graph + Twitter card tags. JSON-LD: WebSite on the home page; Article + BreadcrumbList
on guides, plus FAQPage built from the page's own <details><summary> FAQ text so markup can't drift from content."""
import argparse, hashlib, html as htmlmod, json, os, re, shutil
from pathlib import Path
from xml.sax.saxutils import escape
ROOT = Path(__file__).resolve().parent
ap = argparse.ArgumentParser(description="Build the Errand Desk static site.")
ap.add_argument("--out", help="output directory (default: public/ next to build.py). It is deleted and rebuilt.")
args = ap.parse_args()
SRC = ROOT / "src"
OUT = Path(args.out).resolve() if args.out else ROOT / "public"
if OUT in (ROOT, SRC) or OUT in ROOT.parents: raise SystemExit(f"refusing to use {OUT} as output dir")
cfg = json.loads((ROOT / "site.config.json").read_text())
BASE = os.environ.get("SITE_BASE_URL", cfg["base_url"]).rstrip("/") + "/"
CF_TOKEN = cfg.get("cf_analytics_token", "").strip()
if CF_TOKEN and not re.fullmatch(r"[A-Za-z0-9]+", CF_TOKEN): raise SystemExit("cf_analytics_token looks malformed")
# Cloudflare Web Analytics (cookie-free). Emitted only when a token is configured; otherwise nothing.
ANALYTICS = (f"<script defer src=\"https://static.cloudflareinsights.com/beacon.min.js\" data-cf-beacon='{{\"token\": \"{CF_TOKEN}\"}}'></script>\n" if CF_TOKEN else "")
layout = (SRC / "layout.html").read_text()
CSS_V = hashlib.sha256((SRC / "assets" / "style.css").read_bytes()).hexdigest()[:10]
layout = layout.replace('href="/assets/style.css"', f'href="/assets/style.css?v={CSS_V}"')  # cache-busting so assets can be cached for a year

SITE_NAME = "Errand Desk"
OG_IMAGE = BASE + "og-image.png"
OG_ALT = "Errand Desk: sourced, dated prices for fax, notary and passport photo errands"
ORG = {"@type": "Organization", "name": SITE_NAME, "url": BASE}

def attr(v): return htmlmod.escape(v, quote=True)

def social_tags(meta, url):
    kind = "article" if meta.get("schema") == "article" else "website"
    t, d = attr(meta["title"]), attr(meta["description"])
    tags = [
        f'<meta property="og:type" content="{kind}">',
        f'<meta property="og:site_name" content="{SITE_NAME}">',
        f'<meta property="og:title" content="{t}">',
        f'<meta property="og:description" content="{d}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{OG_IMAGE}">',
        '<meta property="og:image:type" content="image/png">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="{attr(OG_ALT)}">',
        '<meta property="og:locale" content="en_US">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{t}">',
        f'<meta name="twitter:description" content="{d}">',
        f'<meta name="twitter:image" content="{OG_IMAGE}">',
        f'<meta name="twitter:image:alt" content="{attr(OG_ALT)}">',
    ]
    return "\n".join(tags) + "\n"

def plain(fragment):
    """Visible text of an HTML fragment, minus citation markers (<sup>...</sup>)."""
    x = re.sub(r"<sup>.*?</sup>", "", fragment, flags=re.S)
    x = htmlmod.unescape(re.sub(r"<[^>]+>", "", x))
    x = re.sub(r"\s+", " ", x).strip()
    return re.sub(r"\s+([.,;:])", r"\1", x)

def jsonld(meta, body, url, lastmod):
    graph, kind = [], meta.get("schema")
    if kind == "website":
        graph.append({"@type": "WebSite", "name": SITE_NAME, "url": BASE, "description": meta["description"],
                      "inLanguage": "en-US", "publisher": ORG})
    elif kind == "article":
        h1 = plain(re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S).group(1))
        graph.append({"@type": "Article", "headline": h1, "description": meta["description"], "url": url,
                      "mainEntityOfPage": url, "dateModified": lastmod, "image": OG_IMAGE,
                      "inLanguage": "en-US", "author": ORG, "publisher": ORG})
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": BASE},
            {"@type": "ListItem", "position": 2, "name": h1, "item": url}]})
        faqs = re.findall(r"<details><summary>(.*?)</summary>(.*?)</details>", body, re.S)
        if faqs:
            graph.append({"@type": "FAQPage", "url": url, "mainEntity": [
                {"@type": "Question", "name": plain(q), "acceptedAnswer": {"@type": "Answer", "text": plain(a)}}
                for q, a in faqs]})
    elif kind == "collection":
        h1 = plain(re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S).group(1))
        graph.append({"@type": "CollectionPage", "name": h1, "description": meta["description"], "url": url,
                      "dateModified": lastmod, "inLanguage": "en-US", "publisher": ORG})
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": BASE},
            {"@type": "ListItem", "position": 2, "name": h1, "item": url}]})
    if not graph: return ""
    data = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=1)
    data = data.replace("</", "<\\/")  # never close the script element early
    return f'<script type="application/ld+json">\n{data}\n</script>\n'

if OUT.exists(): shutil.rmtree(OUT)
shutil.copytree(SRC / "assets", OUT / "assets")
for f in (SRC / "static").glob("*"): shutil.copy(f, OUT / f.name)
urls = []
for page in sorted((SRC / "pages").rglob("*.html")):
    raw = page.read_text()
    m = re.match(r"\s*<!--meta\s*(\{.*?\})\s*-->", raw, re.S)
    meta = json.loads(m.group(1)); body = raw[m.end():].strip()
    rel = page.relative_to(SRC / "pages").with_suffix("")
    path = "" if str(rel) == "index" else (f"{rel.parent.as_posix()}/" if rel.name == "index" else f"{rel.as_posix()}/")
    dest = OUT / path / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    url, lastmod = BASE + path, meta.get("lastmod", cfg["default_lastmod"])
    html = (layout.replace("{{title}}", meta["title"]).replace("{{description}}", meta["description"])
        .replace("{{canonical}}", url)
        .replace("{{social}}", social_tags(meta, url))
        .replace("{{jsonld}}", jsonld(meta, body, url, lastmod))
        .replace("{{nav_fax}}", ' aria-current="page"' if meta.get("nav") == "fax" else "")
        .replace("{{nav_notary}}", ' aria-current="page"' if meta.get("nav") == "notary" else "")
        .replace("{{nav_passport}}", ' aria-current="page"' if meta.get("nav") == "passport" else "")
        .replace("{{nav_printing}}", ' aria-current="page"' if meta.get("nav") == "printing" else "")
        .replace("{{nav_scanning}}", ' aria-current="page"' if meta.get("nav") == "scanning" else "")
        .replace("{{nav_free_notary}}", ' aria-current="page"' if meta.get("nav") == "free-notary" else "")
        .replace("{{nav_guides}}", ' aria-current="page"' if meta.get("nav") == "guides" else "")
        .replace("{{nav_about}}", ' aria-current="page"' if meta.get("nav") == "about" else "")
        .replace("{{analytics}}", ANALYTICS)
        .replace("{{content}}", body))
    dest.write_text(html); print("built", dest.relative_to(OUT))
    if not meta.get("noindex"):
        urls.append((url, lastmod))
sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
sm += [f"  <url><loc>{escape(u)}</loc><lastmod>{d}</lastmod></url>" for u, d in urls]
sm.append("</urlset>")
(OUT / "sitemap.xml").write_text("\n".join(sm) + "\n")
(OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n")
print(f"built sitemap.xml ({len(urls)} urls) and robots.txt, base {BASE}")
