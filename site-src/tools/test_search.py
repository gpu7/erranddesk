#!/usr/bin/env python3
"""Checks for the static site search.

From the repo root:
    python3 site-src/tools/test_search.py

Builds the site twice in temporary directories (it does not write erranddesk-site/).
"""
import hashlib, json, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "site-src"))
import searchindex  # noqa: E402

JS = ROOT / "site-src" / "src" / "assets" / "search.js"
BUILD = ROOT / "site-src" / "build.py"

QUERIES = [
    ("denver", "/denver/"),
    ("DENVER", "/denver/"),
    ("DeNvEr", "/denver/"),
    ("scanning", "/guides/scanning/"),
    ("scan", "/guides/scanning/"),
    ("apostille", "/guides/apostille/"),
    ("money orders", "/guides/money-orders/"),
    ("money order", "/guides/money-orders/"),
    ("passport photo", "/guides/passport-photo-prices/"),
    ("passport photos", "/guides/passport-photo-prices/"),
    ("notary", "/guides/notary-options/"),
    ("free notary", "/guides/free-notary/"),
    ("fax", "/guides/fax-prices/"),
    ("map", "/map/"),
    ("city guides map", "/map/"),
    ("st. louis", "/st-louis/"),
    ("ST LOUIS", "/st-louis/"),
    ("kansas city", "/kansas-city/"),
    ("aurora", "/aurora/"),
    ("aurora illinois", "/aurora-il/"),
    ("portland", "/portland/"),
    ("portland maine", "/portland-me/"),
    ("shredding", "/guides/shredding/"),
    ("where to get an apostille", "/guides/apostille/"),
]


def build(out):
    subprocess.run([sys.executable, str(BUILD), "--out", str(out)], check=True, cwd=ROOT)


def tree_hash(out):
    h = hashlib.sha256()
    for p in sorted(out.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(out).as_posix().encode())
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


def main_block(html):
    a = html.index('<main id="main" class="wrap">')
    b = html.index("</main>", a)
    return html[a:b]


def head_block(html):
    head = html.split("</head>", 1)[0]
    return re.sub(r"style\.css\?v=[0-9a-f]+", "style.css?v=HASH", head)


def tail_block(html):
    return html.split('<footer class="site-footer">', 1)[1]


def origin_bytes(path):
    r = subprocess.run(["git", "show", f"origin/main:erranddesk-site/{path}"], cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        return None
    return r.stdout


def origin_file(path):
    raw = origin_bytes(path)
    return None if raw is None else raw.decode()


def check_synthetic():
    index = searchindex.build_index([
        {"url": "/", "title": "Home", "description": "Start here", "body": "<h1>Home</h1><p>Welcome aboard.</p>"},
        {"url": "/zeta-city/", "title": "Zeta City errands", "description": "A brand new city page",
         "body": "<h1>Zeta City errands</h1><p>Uniquezebrafax is offered at the library.</p>"},
    ])
    urls = [d["u"] for d in index["docs"]]
    assert urls == ["/", "/zeta-city/"], urls
    assert "uniquezebrafax" in index["post"], "a new page's body text must be indexed without a manual URL list"
    blob = searchindex.dumps(index)
    assert blob == searchindex.dumps(searchindex.build_index([
        {"url": "/zeta-city/", "title": "Zeta City errands", "description": "A brand new city page",
         "body": "<h1>Zeta City errands</h1><p>Uniquezebrafax is offered at the library.</p>"},
        {"url": "/", "title": "Home", "description": "Start here", "body": "<h1>Home</h1><p>Welcome aboard.</p>"},
    ])), "index bytes must not depend on input order"
    assert "javascript:" not in blob


def check_stop_list():
    text = JS.read_text()
    m = re.search(r"var STOP_LIST = \[(.*?)\];", text, re.S)
    js = [w.strip().strip('"') for w in m.group(1).split(",") if w.strip()]
    assert js == sorted(js), "STOP_LIST should be sorted"
    assert set(js) == searchindex.STOP, (set(js) ^ searchindex.STOP)


def check_js_has_no_html_injection():
    text = JS.read_text()
    for banned in ("innerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert banned not in text, banned


def check_site(out):
    index = json.loads((out / "assets" / "search-index.json").read_text())
    assert index["v"] == 1 and index["n"] == len(index["docs"])
    urls = [d["u"] for d in index["docs"]]
    assert urls == sorted(urls)
    assert len(urls) == len(set(urls))
    for u in urls:
        assert u == "/" or (u.startswith("/") and u.endswith("/") and ".." not in u.split("/"))
        assert "/assets/" not in u and not u.endswith(".js") and not u.endswith(".css")
        assert "sitemap" not in u and u != "/404.html"
    sm = (out / "sitemap.xml").read_text()
    sm_urls = []
    for line in sm.splitlines():
        m = re.search(r"<loc>https://erranddesk.com([^<]*)</loc>", line)
        if not m:
            continue
        sm_urls.append(m.group(1) or "/")
    assert sorted(sm_urls) == urls, (len(sm_urls), len(urls), set(sm_urls) ^ set(urls))
    for token in searchindex.STOP:
        assert token not in index["post"]
    home = (out / "index.html").read_text()
    assert "search-index" not in home and "search.js" not in home
    assert "/assets/search.css?v=" in home
    assert home.count('<form class="site-search"') == 1
    assert home.index("plain answers for paperwork errands") < home.index('<form class="site-search"')
    form_at = home.index('<form class="site-search"')
    assert home.index("<nav", form_at) > form_at
    assert 'action="/search/"' in home and 'method="get"' in home and 'type="submit"' in home
    assert '<label for="q">Search</label>' in home and 'id="q"' in home
    assert home.index('<form class="site-search"') - home.index("plain answers for paperwork errands") < 220
    brand = home.index('<a class="brand"')
    brand_end = home.index("</a>", brand)
    assert form_at > brand_end
    # Home keeps its title, description, canonical, JSON-LD, main column and footer.
    # The only head addition is the search stylesheet, and the header gains the form.
    published_home = origin_file("index.html")
    assert main_block(published_home) == main_block(home)
    assert tail_block(published_home) == tail_block(home)
    home_head = re.sub(r'\n<link rel="stylesheet" href="/assets/search.css\?v=[0-9a-f]+">', "", head_block(home))
    assert head_block(published_home) == home_head
    search_html = (out / "search" / "index.html").read_text()
    assert search_html.count('<form class="site-search"') == 1
    assert "/assets/search.js?v=" in search_html and "/assets/search-index.json?v=" in search_html
    assert "/assets/search.css?v=" in search_html
    assert 'rel="canonical" href="https://erranddesk.com/search/"' in search_html
    assert "<title>Search Errand Desk</title>" in search_html
    assert "application/ld+json" not in search_html
    # Every previously published page, including 404, stays byte-identical.
    # style.css is unchanged, so its fingerprint does not rewrite those pages.
    for rel in sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()):
        if rel in ("index.html", "search/index.html", "sitemap.xml") or rel.startswith("assets/search"):
            continue
        old = origin_bytes(rel)
        assert old is not None, rel
        assert old == (out / rel).read_bytes(), rel
    for rel in ("denver/index.html", "about/index.html", "map/index.html", "guides/scanning/index.html",
                "guides/apostille/index.html", "guides/money-orders/index.html", "guides/notary-options/index.html",
                "aurora-il/index.html", "404.html"):
        text = (out / rel).read_text()
        assert "site-search" not in text and "search.css" not in text and "search.js" not in text, rel
    assert "Aurora, Illinois Birth Certificates and Errands" in (out / "aurora-il/index.html").read_text()
    assert "email or USB" in (out / "guides/scanning/index.html").read_text()
    assert "which documents go to your state" in (out / "guides/apostille/index.html").read_text()
    assert "Cost and Limit" in (out / "guides/money-orders/index.html").read_text()
    assert 'href="/guides/free-notary/"' in (out / "guides/notary-options/index.html").read_text()
    broken = []
    for html_path in out.rglob("*.html"):
        text = html_path.read_text()
        for href in re.findall(r'\shref="([^"]+)"', text):
            if not href.startswith("/") or href.startswith("//"):
                continue
            path = href.split("#", 1)[0].split("?", 1)[0]
            target = out / "index.html" if path == "/" else (out / path.strip("/") / "index.html" if path.endswith("/") else out / path.strip("/"))
            if not target.is_file():
                broken.append(f"{html_path.relative_to(out)} -> {href}")
    assert not broken, broken[:20]
    return index


NODE_CHECK = r"""
const fs = require("fs");
const s = require(process.argv[1]);
const index = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const queries = JSON.parse(process.argv[3]);
let failed = 0;
function top(q, n) {
  const out = s.search(index, q);
  return {kind: out.kind, urls: (out.results || []).slice(0, n).map(r => r.url + ":" + r.score)};
}
for (const [q, expect] of queries) {
  const out = s.search(index, q);
  const got = out.results && out.results[0] && out.results[0].url;
  if (out.kind !== "hit" || got !== expect) {
    failed++;
    console.log("FAIL", JSON.stringify(q), "expected", expect, "got", got, top(q, 5));
  }
}
const both = s.search(index, "kansas city");
const urls = both.results.slice(0, 3).map(r => r.url);
if (urls[0] !== "/kansas-city/" || !urls.includes("/kansas-city-mo/")) {
  failed++;
  console.log("FAIL kansas city top", urls);
}
for (const q of ["", "   ", "\n"]) {
  const out = s.search(index, q);
  if (out.kind !== "empty" || out.results.length) { failed++; console.log("FAIL blank", q, out.kind); }
}
const vague = s.search(index, "the a of");
if (vague.kind !== "vague") { failed++; console.log("FAIL vague", vague); }
const none = s.search(index, "zzzzqqqjjj-not-a-page");
if (none.kind !== "none" || none.results.length) { failed++; console.log("FAIL none", none.kind); }
const xss = '<img src=x onerror="alert(1)"><script>alert(1)</script>';
const nasty = s.search(index, xss);
if (nasty.kind !== "none" && nasty.kind !== "vague") {
  // A weird query may match ordinary words such as "src" or "alert". That is fine.
  // The query itself must not be turned into HTML by the renderer.
}
const parts = s.highlight(xss, s.termsOf(xss));
const joined = parts.map(p => p.t).join("");
if (joined !== xss) { failed++; console.log("FAIL highlight altered text", joined); }
if (JSON.stringify(parts).indexOf("innerHTML") !== -1) { failed++; console.log("FAIL parts"); }
const evilUrl = s.safeUrl("javascript:alert(1)");
const dot = s.safeUrl("/../denver/");
const scheme = s.safeUrl("//evil.example/");
if (evilUrl || dot || scheme) { failed++; console.log("FAIL safeUrl", evilUrl, dot, scheme); }
if (s.safeUrl("/denver/") !== "/denver/" || s.safeUrl("/") !== "/") { failed++; console.log("FAIL safeUrl allow"); }
// Body-only token: one document, body flag only, not in the title.
const TITLE = 1, URL = 2, DESC = 4, BODY = 8;
let bodyTok = null, bodyUrl = null;
for (const [tok, list] of Object.entries(index.post)) {
  if (list.length !== 1) continue;
  const flags = list[0] % 16;
  if ((flags & BODY) && !(flags & (TITLE | URL | DESC)) && tok.length > 6) {
    bodyTok = tok;
    bodyUrl = index.docs[Math.floor(list[0] / 16)].u;
    break;
  }
}
if (!bodyTok) { failed++; console.log("FAIL no body-only token"); }
else {
  const out = s.search(index, bodyTok);
  if (!out.results.length || out.results[0].url !== bodyUrl) {
    failed++;
    console.log("FAIL body", bodyTok, bodyUrl, out.results.slice(0, 3).map(r => r.url));
  } else {
    const snip = out.results[0].parts.map(p => p.t).join("").toLowerCase();
    const doc = index.docs.find(d => d.u === bodyUrl);
    const hay = ((doc.t || "") + " " + (doc.d || "") + " " + (doc.x || "")).toLowerCase();
    if (hay.indexOf(bodyTok) !== -1 && snip.indexOf(bodyTok) === -1) {
      failed++;
      console.log("FAIL snippet missing body token", bodyTok, snip.slice(0, 160));
    }
  }
}
const upper = s.search(index, "ApOsTiLlE");
if (!upper.results.length || upper.results[0].url !== "/guides/apostille/") {
  failed++;
  console.log("FAIL case", upper.results.slice(0, 2));
}
const protoBefore = Object.getOwnPropertyNames(Object.prototype).sort().join("\n");
const hostile = [
  "__proto__", "constructor", "prototype", "constructor.prototype",
  "__proto__,constructor", '{"__proto__":{"polluted":true}}',
  "hasOwnProperty", "toString", "valueOf",
  "__proto__=polluted", "constructor[prototype]",
  "<script>alert(1)</script>", "javascript:alert(1)"
];
for (const q of hostile) {
  let out;
  try { out = s.search(index, q); }
  catch (err) { failed++; console.log("FAIL hostile throw", q, err); continue; }
  if (!out || !out.kind || out.kind === "error") {
    failed++;
    console.log("FAIL hostile kind", q, out && out.kind);
  }
  const badUrl = (out.results || []).some(r => !s.safeUrl(r.url));
  if (badUrl) { failed++; console.log("FAIL hostile url", q); }
}
if (s.termsOf("__proto__").join(",") !== "proto") {
  failed++;
  console.log("FAIL proto token", s.termsOf("__proto__"));
}
if (s.termsOf("constructor prototype").join(",") !== "constructor,prototype") {
  failed++;
  console.log("FAIL property tokens", s.termsOf("constructor prototype"));
}
const protoAfter = Object.getOwnPropertyNames(Object.prototype).sort().join("\n");
if (protoBefore !== protoAfter || ({}).polluted) {
  failed++;
  console.log("FAIL prototype changed");
}
const still = s.search(index, "denver");
if (!still.results.length || still.results[0].url !== "/denver/") {
  failed++;
  console.log("FAIL ranking after hostile queries", still.results && still.results[0]);
}
if (failed) process.exit(1);
console.log("node checks ok");
"""


def main():
    check_synthetic()
    check_stop_list()
    check_js_has_no_html_injection()
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        print("building", a)
        build(a)
        print("building", b)
        build(b)
        ha, hb = tree_hash(Path(a)), tree_hash(Path(b))
        assert ha == hb, "rebuild was not byte-identical"
        index = check_site(Path(a))
        blob = (Path(a) / "assets" / "search-index.json").read_bytes()
        js = (Path(a) / "assets" / "search.js").read_bytes()
        print(f"search-index.json {len(blob)} bytes, search.js {len(js)} bytes, pages {index['n']}")
        subprocess.run(
            ["node", "-e", NODE_CHECK, str(JS), str(Path(a) / "assets" / "search-index.json"), json.dumps(QUERIES)],
            check=True,
        )
    print("ok")


if __name__ == "__main__":
    main()
