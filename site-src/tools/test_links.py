#!/usr/bin/env python3
"""Checks for same-state city links, guide anchors, and the map's guide link.

From the repo root:
    python3 site-src/tools/test_links.py

Builds the site once in a temporary directory. It does not write erranddesk-site/.
"""
import html as html_mod, json, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "site-src"))
import searchindex  # noqa: E402
import statelinks  # noqa: E402

BUILD = ROOT / "site-src" / "build.py"
DATA = ROOT / "site-src" / "src" / "data" / "cities.json"

# City anchors added where the guide already names that city. Nothing else.
GUIDE_CITIES = {
    "apostille": {"phoenix"},
    "certified-copies": {"chicago", "new-york-city"},
    "fax-prices": {"cincinnati", "denver"},
    "free-notary": {"ann-arbor", "columbus"},
    "notary-options": {"ann-arbor", "charlotte", "columbus"},
    "one-stop-errands": {"ann-arbor", "columbus", "dallas", "denver"},
    "passport-photo-prices": {"charlotte"},
    "photocopies": {"dallas", "denver", "houston", "seattle"},
    "printing-prices": {"chicago", "cincinnati", "dallas", "denver", "houston", "los-angeles", "seattle"},
    "scanning": {"boston", "chicago", "dallas", "denver", "houston", "san-francisco", "seattle"},
    "shredding": {"charlotte"},
}
# These guides name places, but not a city we publish, or only as a street, bank, or mailing address.
NO_CITY_LINKS = {
    "background-checks", "mobile-notary", "money-orders", "passport-checklist",
    "shipping", "usps-services",
}


def origin_text(path):
    raw = subprocess.run(["git", "show", f"origin/main:erranddesk-site/{path}"], cwd=ROOT, capture_output=True)
    if raw.returncode != 0:
        raise SystemExit(f"missing origin/main erranddesk-site/{path}")
    return raw.stdout.decode()


def reachability(graph):
    for code, group in graph.by_state.items():
        slugs = [city["slug"] for city in group]
        outgoing = {city["slug"]: [item["slug"] for item in graph.siblings(city["slug"])] for city in group}
        for start in slugs:
            seen = set()
            stack = [start]
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                stack.extend(outgoing[cur])
            missing = [slug for slug in slugs if slug not in seen]
            if missing:
                raise SystemExit(f"{code}: {start} cannot reach {missing[:8]}")
        sets = [tuple(outgoing[slug]) for slug in slugs]
        if len(slugs) > statelinks.SIBLING_CAP + 1 and len(set(sets)) == 1:
            raise SystemExit(f"{code}: every city links to the same set")


def check_graph():
    graph = statelinks.load(DATA)
    assert len(graph.cities) == 265
    assert len(graph.by_state) == 50
    assert min(len(group) for group in graph.by_state.values()) == 5
    assert len(graph.by_state["CO"]) == 20
    reachability(graph)
    first = [city["slug"] for city in graph.by_state["CO"][:5]]
    varied = False
    for city in graph.by_state["CO"]:
        picked = [item["slug"] for item in graph.siblings(city["slug"])]
        assert city["slug"] not in picked
        assert len(picked) == len(set(picked)) == statelinks.SIBLING_CAP
        assert all(graph.by_slug[slug]["state"] == "CO" for slug in picked)
        if not set(picked) <= set(first):
            varied = True
    assert varied, "Colorado links must not all stay inside the alphabetical first cities"
    for state, group in graph.by_state.items():
        if len(group) <= statelinks.SIBLING_CAP + 1:
            for city in group:
                others = {item["slug"] for item in group if item["slug"] != city["slug"]}
                assert {item["slug"] for item in graph.siblings(city["slug"])} == others
    assert graph.label(graph.by_slug["aurora"]) == "Aurora, Colorado"
    assert graph.label(graph.by_slug["aurora-il"]) == "Aurora, Illinois"
    assert graph.label(graph.by_slug["portland"]) == "Portland, Oregon"
    assert graph.label(graph.by_slug["portland-me"]) == "Portland, Maine"
    assert graph.label(graph.by_slug["rochester"]) == "Rochester, Minnesota"
    assert graph.label(graph.by_slug["rochester-ny"]) == "Rochester, New York"
    assert graph.label(graph.by_slug["rochester-nh"]) == "Rochester, New Hampshire"
    assert graph.label(graph.by_slug["denver"]) == "Denver"
    assert "nearest" not in graph.nav_html("denver").lower()
    assert "nearby" not in graph.nav_html("denver").lower()
    assert 'href="/map/#list-colorado"' in graph.nav_html("denver")
    assert 'href="/aurora/"' not in graph.nav_html("aurora")
    print("graph ok", len(graph.cities), "cities")
    return graph


def city_hrefs(fragment):
    return re.findall(r'href="(/[a-z0-9-]+/)"', fragment)


# Pages whose FAQ text changed in this pass. Title, description, canonical,
# sources and non-FAQ JSON-LD stay locked to origin/main.
EDITED_CITIES = {"duluth"}
EDITED_GUIDES = {"notary-options"}


def plain_faq(fragment):
    """Same visible-text rules build.py uses for FAQPage JSON-LD."""
    x = re.sub(r"<sup>.*?</sup>", "", fragment, flags=re.S)
    x = html_mod.unescape(re.sub(r"<[^>]+>", "", x))
    x = re.sub(r"\s+", " ", x).strip()
    return re.sub(r"\s+([.,;:])", r"\1", x)


def jsonld_graph(html):
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    if not blocks:
        return None
    if len(blocks) != 1:
        raise SystemExit(f"expected one JSON-LD block, found {len(blocks)}")
    return json.loads(blocks[0].strip().replace("<\\/", "</"))


def graph_without_faq(html):
    graph = jsonld_graph(html)
    graph["@graph"] = [node for node in graph["@graph"] if node.get("@type") != "FAQPage"]
    return graph


def assert_visible_faq_matches_schema(html, label):
    graph = jsonld_graph(html)
    visible = re.findall(r"<details><summary>(.*?)</summary>(.*?)</details>", html, re.S)
    if graph is None:
        if visible:
            raise SystemExit(f"{label}: FAQ details without JSON-LD")
        return
    articles = [node for node in graph["@graph"] if node.get("@type") == "Article"]
    faqs = [node for node in graph["@graph"] if node.get("@type") == "FAQPage"]
    if not articles:
        if faqs:
            raise SystemExit(f"{label}: FAQPage without an Article")
        return
    if not visible:
        if faqs:
            raise SystemExit(f"{label}: FAQPage markup without a visible FAQ")
        return
    if len(faqs) != 1:
        raise SystemExit(f"{label}: expected one FAQPage, found {len(faqs)}")
    main = faqs[0]["mainEntity"]
    if len(main) != len(visible):
        raise SystemExit(f"{label}: FAQ count {len(visible)} visible vs {len(main)} in JSON-LD")
    for (question, answer), item in zip(visible, main):
        q, a = plain_faq(question), plain_faq(answer)
        if item.get("name") != q or item.get("acceptedAnswer", {}).get("text") != a:
            raise SystemExit(f"{label}: visible FAQ does not match JSON-LD ({q!r})")


def check_site(out, graph):
    map_html = (out / "map" / "index.html").read_text()
    ids = set(re.findall(r'\sid="([^"]+)"', map_html))
    dot_hrefs = re.findall(r'<g class="cities">(.*?)</g>', map_html, re.S)[0]
    dot_links = city_hrefs(dot_hrefs)
    assert len(dot_links) == 265 and len(set(dot_links)) == 265
    assert 'href="/guides/"' in map_html
    assert "Topic guides" in map_html
    # Coordinates and the state list stay. Compare the dot block and list headings to origin.
    old_map = origin_text("map/index.html")
    old_dots = re.findall(r'<g class="cities">(.*?)</g>', old_map, re.S)[0]
    assert dot_hrefs == old_dots
    assert re.findall(r'<h3 id="(list-[^"]+)">([^<]+)</h3>', map_html) == re.findall(
        r'<h3 id="(list-[^"]+)">([^<]+)</h3>', old_map)
    sm = (out / "sitemap.xml").read_text()
    assert sm.count("<loc>") == 288
    assert sm == origin_text("sitemap.xml")
    index = json.loads((out / "assets" / "search-index.json").read_text())
    by_url = {doc["u"]: i for i, doc in enumerate(index["docs"])}
    title_re = re.compile(r"<title>(.*?)</title>")
    desc_re = re.compile(r'<meta name="description" content="([^"]*)">')
    canon_re = re.compile(r'<link rel="canonical" href="([^"]+)">')
    jsonld_re = re.compile(r'<script type="application/ld\+json">.*?</script>', re.S)
    sources_re = re.compile(r'<ol class="sources">.*?</ol>', re.S)
    nav_re = re.compile(r'<nav class="more-in-state\b.*?</nav>', re.S)
    pages = 0
    for city in graph.cities:
        slug = city["slug"]
        html = (out / slug / "index.html").read_text()
        old = origin_text(f"{slug}/index.html")
        pages += 1
        assert title_re.search(html).group(1) == title_re.search(old).group(1)
        assert desc_re.search(html).group(1) == desc_re.search(old).group(1)
        assert canon_re.search(html).group(1) == canon_re.search(old).group(1)
        if slug in EDITED_CITIES:
            assert graph_without_faq(html) == graph_without_faq(old), slug
        else:
            assert jsonld_re.findall(html) == jsonld_re.findall(old)
        assert sources_re.findall(html) == sources_re.findall(old)
        navs = nav_re.findall(html)
        assert len(navs) == 1, slug
        nav = navs[0]
        assert "data-search-skip" in nav
        state_name = graph.states[city["state"]]
        assert f">More in {state_name}<" in nav
        assert "nearest" not in nav.lower() and "nearby" not in nav.lower()
        fragment = statelinks.map_list_id(state_name)
        assert f'href="/map/#{fragment}"' in nav
        assert fragment in ids, fragment
        hrefs = city_hrefs(nav)
        assert f"/{slug}/" not in hrefs
        assert len(hrefs) == len(set(hrefs))
        assert len(hrefs) <= statelinks.SIBLING_CAP
        expect = graph.siblings(slug)
        assert [href.strip("/") for href in hrefs] == [item["slug"] for item in expect]
        for item, href in zip(expect, hrefs):
            assert f">{graph.label(item)}</a>" in nav
            assert graph.by_slug[item["slug"]]["state"] == city["state"]
        # Sibling names that the article itself does not use must not be indexed as body text.
        article = nav_re.sub(" ", html)
        plain = searchindex.plain(article)
        doc_id = by_url["/" + slug + "/"]
        for item in expect:
            for token in searchindex.tokenize(graph.label(item)):
                if token in searchindex.tokenize(plain):
                    continue
                flags = 0
                for packed in index["post"].get(token, []):
                    if packed // 16 == doc_id:
                        flags = packed % 16
                assert not (flags & searchindex.BODY), (slug, token)
    assert pages == 265
    guide_dir = out / "guides"
    for path in sorted(guide_dir.glob("*/index.html")):
        name = path.parent.name
        html = path.read_text()
        old = origin_text(f"guides/{name}/index.html")
        assert title_re.search(html).group(1) == title_re.search(old).group(1)
        assert desc_re.search(html).group(1) == desc_re.search(old).group(1)
        assert canon_re.search(html).group(1) == canon_re.search(old).group(1)
        if name in EDITED_GUIDES:
            assert graph_without_faq(html) == graph_without_faq(old), name
        else:
            assert jsonld_re.findall(html) == jsonld_re.findall(old)
        assert sources_re.findall(html) == sources_re.findall(old), name
        # City links in the guide body, outside the source list.
        body = sources_re.sub(" ", html)
        found = set()
        for href in city_hrefs(body):
            target = href.strip("/")
            if target in graph.by_slug:
                found.add(target)
        if name in NO_CITY_LINKS:
            assert not found, (name, found)
        elif name in GUIDE_CITIES:
            assert found == GUIDE_CITIES[name], (name, found, GUIDE_CITIES[name])
        else:
            raise SystemExit(f"unexpected guide {name}")
    index_html = (guide_dir / "index.html").read_text()
    assert city_hrefs(index_html).count("/denver/") == 1
    # The guides index already lists every city. It does not get another generated block.
    assert "more-in-state" not in index_html
    for html_path in out.rglob("*.html"):
        assert_visible_faq_matches_schema(html_path.read_text(), html_path.relative_to(out).as_posix())
    print("html ok", pages, "city pages")


def main():
    graph = check_graph()
    with tempfile.TemporaryDirectory() as tmp:
        print("building", tmp)
        subprocess.run([sys.executable, str(BUILD), "--out", tmp], check=True, cwd=ROOT)
        check_site(Path(tmp), graph)
    print("ok")


if __name__ == "__main__":
    main()
