#!/usr/bin/env python3
"""Checks for same-state city links, guide anchors, and the map's guide link.

From the repo root:
    python3 site-src/tools/test_links.py

Builds the site once in a temporary directory. It does not write erranddesk-site/.
"""
import html as html_mod, json, re, subprocess, sys, tempfile
from pathlib import Path
from urllib.parse import urlparse

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


POLICY_FOOTER_LINKS = (
    '    <p class="small"><a href="/about/">About</a> · <a href="/disclosure/">Disclosure</a> '
    '· <a href="/privacy/">Privacy</a> · <a href="/contact/">Contact</a></p>\n'
)
NEW_POLICY_SITEMAP = {
    "https://erranddesk.com/privacy/",
    "https://erranddesk.com/contact/",
}


def drop_policy_footer(text):
    """Remove the Privacy/Contact footer line added in November 2026."""
    return text.replace(POLICY_FOOTER_LINKS, "")


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


# PR345's notary how-to FAQ and Duluth library FAQ stay on origin/main.
# This pass does not rewrite them. Duluth is checked by the assertions below.

# Three new guides. City links are only the places the page actually discusses.
NEW_GUIDES = {
    "passport-acceptance-visit": {"denver", "houston", "austin"},
    "in-person-vs-remote-notary": {"cheyenne", "duluth"},
    "library-printing": {"cheyenne", "denver", "duluth", "houston"},
}
NEW_GUIDE_TITLES = {
    "passport-acceptance-visit": "Passport Acceptance Visit: What to Expect (2026)",
    "in-person-vs-remote-notary": "In-Person vs Remote Online Notary (2026)",
    "library-printing": "Library Printing: What to Bring (2026)",
}
OFFICIAL_HOSTS = {
    "www.usps.com",
    "houstonlibrary.org",
    "library.austintexas.gov",
    "www.nass.org",
    "www.flsenate.gov",
    "www.sos.state.tx.us",
    "notary.cdn.sos.ca.gov",
    "lclsonline.org",
    "duluthlibrary.org",
    "www.denverlibrary.org",
}


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


_JSONLD_BLOCK = re.compile(r'<script type="application/ld\+json">.*?</script>\n?', re.S)
_DETAILS_BLOCK = re.compile(r"<details><summary>(.*?)</summary>.*?</details>\n?", re.S)


def page_outside_faq(html):
    """Page bytes with JSON-LD and question <details> removed. Other disclosures stay."""
    def keep(match):
        return "" if plain_faq(match.group(1)).endswith("?") else match.group(0)
    return _DETAILS_BLOCK.sub(keep, _JSONLD_BLOCK.sub("", html))


def detail_pairs(html):
    return re.findall(r"<details><summary>(.*?)</summary>(.*?)</details>", html, re.S)


def visible_question_faqs(html):
    """FAQ schema follows question disclosures only, not every <details> list."""
    return [(q, a) for q, a in detail_pairs(html) if plain_faq(q).endswith("?")]


def assert_visible_faq_matches_schema(html, label):
    graph = jsonld_graph(html)
    visible = visible_question_faqs(html)
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
    if faqs[0].get("url") != re.search(r'<link rel="canonical" href="([^"]+)"', html).group(1):
        raise SystemExit(f"{label}: FAQPage url is not the page canonical")
    main = faqs[0]["mainEntity"]
    if len(main) != len(visible):
        raise SystemExit(f"{label}: FAQ count {len(visible)} visible vs {len(main)} in JSON-LD")
    names = []
    for (question, answer), item in zip(visible, main):
        q, a = plain_faq(question), plain_faq(answer)
        if not q or not a:
            raise SystemExit(f"{label}: empty FAQ question or answer")
        if item.get("@type") != "Question" or item.get("acceptedAnswer", {}).get("@type") != "Answer":
            raise SystemExit(f"{label}: FAQ entity types are not Question/Answer")
        if item.get("name") != q or item.get("acceptedAnswer", {}).get("text") != a:
            raise SystemExit(f"{label}: visible FAQ does not match JSON-LD ({q!r})")
        names.append(q)
    if len(names) != len({name.casefold() for name in names}):
        raise SystemExit(f"{label}: duplicate FAQ questions")
    for question, _ in detail_pairs(html):
        label_text = plain_faq(question)
        if not label_text.endswith("?") and label_text in names:
            raise SystemExit(f"{label}: non-question disclosure is in FAQPage ({label_text!r})")


def assert_new_guide(html, name, sitemap, index):
    """A new guide is indexable, sourced, and titled like the rest of the site."""
    title = html_mod.unescape(re.search(r"<title>(.*?)</title>", html).group(1))
    assert title == NEW_GUIDE_TITLES[name], (name, title)
    assert len(title) <= 60, (name, len(title), title)
    canon = f"https://erranddesk.com/guides/{name}/"
    assert f'<link rel="canonical" href="{canon}">' in html
    assert "noindex" not in html
    assert f"<loc>{canon}</loc>" in sitemap
    urls = {doc["u"] for doc in index["docs"]}
    assert f"/guides/{name}/" in urls
    graph = jsonld_graph(html)
    types = {node.get("@type") for node in graph["@graph"]}
    assert "Article" in types and "FAQPage" in types, (name, types)
    sources = re.search(r'<ol class="sources">(.*?)</ol>', html, re.S)
    assert sources, name
    items = re.findall(r'<li id="([^"]+)">(.*?)</li>', sources.group(1), re.S)
    assert len(items) >= 3, name
    ids = {item_id for item_id, _ in items}
    for item_id, body in items:
        assert "(last checked Nov 6, 2026)" in body, (name, item_id)
        links = re.findall(r'href="(https://[^"]+)"', body)
        assert links, (name, item_id)
        for link in links:
            host = urlparse(link).hostname
            assert host in OFFICIAL_HOSTS, (name, host)
    for href in re.findall(r'href="#([^"]+)"', html):
        assert f'id="{href}"' in html, (name, href)
    body = re.sub(r'<ol class="sources">.*?</ol>', " ", html, flags=re.S)
    assert "nearby" not in body.lower() and "nearest" not in body.lower()
    # Citation markers point at a source on the same page.
    for sup in re.findall(r"<sup>.*?</sup>", html, re.S):
        cites = re.findall(r'href="#([^"]+)"', sup)
        assert cites, name
        for cite in cites:
            assert cite in ids, (name, cite)



def assert_recheck_c1_browser(html, old, slug):
    """AL/AK/AZ/AR quarterly recheck browser follow-up (Nov 9, 2026)."""
    assert 'Details last checked <time datetime="2026-11-09">Nov 9, 2026</time>' in html, slug
    assert '"dateModified": "2026-11-09"' in html, slug
    if slug == "birmingham":
        assert "jccal.org/m/newsflash/Archive/Item/82?arcId=202" in html
        assert "Home/Detail/82" not in html
    elif slug == "montgomery":
        assert "montgomeryprobatecourtal.gov/home-probateoffice" in html
        assert "montgomeryprobatecourtal.gov/divisions/records-recording" in html
        assert "city-clerk-s-office/request-for-public-records" in html
        assert "montgomerycountyal.gov/departments/probate-court" not in html
        assert "how-do-i/request/public-record" not in html
    else:
        assert "azsos.gov/business/notary" in html
        assert "azsos.gov/business/notary-public/remote-enotary" in html
        assert re.search(r"azsos\.gov/business/notary-public(?!/)", html) is None, slug
        assert "A Travel ID or Travel driver license, original or renewal, is $25." in html
        assert "A non-travel driver license is $25 (ages 16–39), $20 (40–44), $15 (45–49), or $10 (age 50 and older, and five-year licenses)" in html
        assert "A Travel ID or driver license, original or renewal, is $25" not in html
    # Titles and descriptions stay.
    assert re.search(r"<title>(.*?)</title>", html).group(1) == re.search(r"<title>(.*?)</title>", old).group(1)
    assert re.search(r'<meta name="description" content="([^"]*)">', html).group(1) == re.search(
        r'<meta name="description" content="([^"]*)">', old).group(1)


def assert_nov9_city_facts(html, old, slug):
    """Knoxville notary end date, Bangor clerk URL, Columbus GA probate address."""
    assert 'Details last checked <time datetime="2026-11-09">Nov 9, 2026</time>' in html, slug
    assert '"dateModified": "2026-11-09"' in html, slug
    assert re.search(r"<title>(.*?)</title>", html).group(1) == re.search(r"<title>(.*?)</title>", old).group(1)
    assert re.search(r'<meta name="description" content="([^"]*)">', html).group(1) == re.search(
        r'<meta name="description" content="([^"]*)">', old).group(1)
    if slug == "knoxville":
        assert "after October 31, 2026 it no longer notarizes documents" in html
        assert "still shows the old $3.00 fee" in html
        assert "knoxcounty.org/clerk/notary.php</a> (last checked Nov 9, 2026)" in html
        assert "will no longer offer this service" not in html
        assert "Don't plan on it." not in html
        assert "$3.00 notary service ends" not in html
    elif slug == "bangor":
        assert "bangormaine.gov/173/City-Clerk-Treasury" in html
        assert "195/City-Clerk" not in html
        assert "Absentee-Early-Voting" not in html
        assert "Monday–Friday 8 a.m.–4:15 p.m. at 73 Harlow St." in html
        assert "Dedimus Justice $5 and Attestation $5" in html
        assert "1st Copy 15$" in html and "marriage license 40$" in html
        assert "bangormaine.gov/DocumentCenter/View/1652/Clerk--Treasury-Fee-Schedule-PDF</a> (last checked Nov 9, 2026)" in html
    else:
        assert "100 10th St., 2nd Floor, Columbus, GA 31901" in html
        assert "John D. Allen Government Center" in html
        assert "as of November 9, 2026" in html
        assert "We didn't find a current relocation notice" in html
        assert "moving this week" not in html
        assert "closes at 3 p.m. on Nov. 6" not in html
        assert "The court is moving" not in html
        assert "100 10th St., 6th Floor" in html
        assert "columbusga.gov/probate/</a> (last checked Nov 9, 2026)" in html or "columbusga.gov/probate</a> (last checked Nov 9, 2026)" in html
        assert "100 10th Street, 2nd Floor Tower" in html
        assert "closed Monday, Nov. 9, 2026, from 8:00 a.m. to 5:00 p.m." in html


def assert_sioux_falls_shredder(html, old):
    """Downtown Library guest shredder is the only Sioux Falls body change."""
    assert visible_question_faqs(html) == visible_question_faqs(old)
    shred = re.search(r'<h2 id="shredding">(.*?)</ul>', html, re.S).group(1)
    assert "Downtown Library (free, guest-operated)" in shred
    assert "confirmed on Nov 8, 2026" in shred
    assert "guests can use a shredder there during open hours" in shred
    assert "it is free" in shred
    assert "does not offer shredding events" in shred
    assert "reported, not a public library page" in shred
    assert 'href="#s28"' in shred and 'href="#s3"' in shred
    assert "That page's feature list does not include shredding" in shred
    assert "doesn't state a page limit, an appointment rule or a capacity" in shred
    assert "we didn't find an upcoming free shred event on the official city and county pages we checked." in shred
    assert "2601 S Minnesota Ave" in shred
    assert "mailto:" not in shred
    assert "@" not in shred
    sources = re.search(r'<ol class="sources">(.*?)</ol>', html, re.S).group(1)
    old_sources = re.search(r'<ol class="sources">(.*?)</ol>', old, re.S).group(1)
    s28 = re.search(r'<li id="s28">(.*?)</li>', sources, re.S)
    assert s28, "missing staff-confirmation source"
    note = s28.group(1)
    assert "confirmation dated Nov 8, 2026" in note
    assert "reported, not a public library page" in note
    assert "There is no public URL for this reply." in note
    assert "that page does not list shredding" in note
    assert "https://www.siouxlandlib.org/Venues/downtown-library" in note
    assert "mailto:" not in note and "@" not in note
    assert "(last checked Nov 8, 2026)" in note
    without_new = re.sub(r'\s*<li id="s28">.*?</li>', "", sources, count=1, flags=re.S)
    without_new = without_new.replace(
        "siouxlandlib.org/Venues/downtown-library</a> (last checked Nov 8, 2026)",
        "siouxlandlib.org/Venues/downtown-library</a> (last checked Oct 29, 2026)",
    )
    assert without_new == old_sources
    reverted = html.replace(
        'Details last checked <time datetime="2026-11-08">Nov 8, 2026</time>',
        'All details last checked <time datetime="2026-10-29">Oct 29, 2026</time>',
    ).replace(
        '"dateModified": "2026-11-08"',
        '"dateModified": "2026-10-29"',
    ).replace(
        "Sources last checked Oct 29 or Nov 8, 2026, as marked on each, except the locator data file.",
        "All sources last checked Oct 29, 2026, except the locator data file.",
    )
    old_ul = re.search(r'(<h2 id="shredding">.*?</ul>)', old, re.S).group(1)
    reverted = re.sub(r'<h2 id="shredding">.*?</ul>', lambda m: old_ul, reverted, count=1, flags=re.S)
    reverted = re.sub(r'\s*<li id="s28">.*?</li>', "", reverted, count=1, flags=re.S)
    reverted = reverted.replace(
        "siouxlandlib.org/Venues/downtown-library</a> (last checked Nov 8, 2026)",
        "siouxlandlib.org/Venues/downtown-library</a> (last checked Oct 29, 2026)",
    )
    assert "Nov 8, 2026" not in reverted
    assert reverted == old


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
    old_sm = origin_text("sitemap.xml")
    assert sm.count("<loc>") == 293
    assert old_sm.count("<loc>") == 293
    old_rows = re.findall(r"<loc>(.*?)</loc><lastmod>(.*?)</lastmod>", old_sm)
    new_rows = re.findall(r"<loc>(.*?)</loc><lastmod>(.*?)</lastmod>", sm)
    old_locs = [loc for loc, _ in old_rows]
    new_locs = [loc for loc, _ in new_rows]
    assert new_locs == old_locs
    new_dates = dict(new_rows)
    assert new_dates["https://erranddesk.com/about/"] == "2026-11-10"
    assert new_dates["https://erranddesk.com/privacy/"] == "2026-11-10"
    assert new_dates["https://erranddesk.com/contact/"] == "2026-11-10"
    recheck_lastmod = {
        "https://erranddesk.com/sioux-falls/": ("2026-11-08", "2026-11-08"),
        "https://erranddesk.com/birmingham/": ("2026-11-09", "2026-11-09"),
        "https://erranddesk.com/montgomery/": ("2026-11-09", "2026-11-09"),
        "https://erranddesk.com/phoenix/": ("2026-11-09", "2026-11-09"),
        "https://erranddesk.com/tucson/": ("2026-11-09", "2026-11-09"),
        "https://erranddesk.com/mesa/": ("2026-11-09", "2026-11-09"),
        "https://erranddesk.com/gilbert/": ("2026-11-09", "2026-11-09"),
        "https://erranddesk.com/chandler/": ("2026-11-09", "2026-11-09"),
        "https://erranddesk.com/knoxville/": ("2026-11-09", "2026-11-09"),
        "https://erranddesk.com/bangor/": ("2026-11-09", "2026-11-09"),
        "https://erranddesk.com/columbus-ga/": ("2026-11-09", "2026-11-09"),
    }
    new_by_loc = dict(new_rows)
    policy_lastmod = {
        "https://erranddesk.com/about/",
        "https://erranddesk.com/privacy/",
        "https://erranddesk.com/contact/",
    }
    for loc, old_date in old_rows:
        new_date = new_by_loc[loc]
        if loc in recheck_lastmod:
            assert (old_date, new_date) == recheck_lastmod[loc], (loc, old_date, new_date)
        elif loc in policy_lastmod:
            continue
        else:
            assert old_date == new_date, (loc, old_date, new_date)
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
        # A practical FAQ may be added or tightened. Titles, sources, and the
        # non-FAQ graph stay on origin/main. Non-question disclosures stay too.
        # Sioux Falls adds the Nov 8, 2026 Downtown Library shredder confirmation.
        # AL/AK/AZ/AR quarterly recheck browser follow-up (Nov 9, 2026): citation
        # URL redirects and Arizona MVD fee wording on seven city pages.
        if slug == "sioux-falls":
            # Shredder confirmation already on origin/main (PR #349).
            assert drop_policy_footer(html) == drop_policy_footer(old)
        elif slug in {"birmingham", "montgomery", "phoenix", "tucson", "mesa", "gilbert", "chandler"}:
            assert_recheck_c1_browser(html, old, slug)
        elif slug in {"knoxville", "bangor", "columbus-ga"}:
            assert_nov9_city_facts(html, old, slug)
        else:
            assert drop_policy_footer(page_outside_faq(html)) == drop_policy_footer(page_outside_faq(old)), slug
            if visible_question_faqs(html) == visible_question_faqs(old):
                assert jsonld_re.findall(html) == jsonld_re.findall(old), slug
            else:
                assert graph_without_faq(html) == graph_without_faq(old), slug
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
        if name in NEW_GUIDES:
            assert_new_guide(html, name, sm, index)
            body = sources_re.sub(" ", html)
            found = set()
            for href in city_hrefs(body):
                target = href.strip("/")
                if target in graph.by_slug:
                    found.add(target)
            assert found == NEW_GUIDES[name], (name, found, NEW_GUIDES[name])
            continue
        old = origin_text(f"guides/{name}/index.html")
        assert title_re.search(html).group(1) == title_re.search(old).group(1)
        assert desc_re.search(html).group(1) == desc_re.search(old).group(1)
        assert canon_re.search(html).group(1) == canon_re.search(old).group(1)
        assert drop_policy_footer(page_outside_faq(html)) == drop_policy_footer(page_outside_faq(old)), name
        if visible_question_faqs(html) == visible_question_faqs(old):
            assert jsonld_re.findall(html) == jsonld_re.findall(old), name
        else:
            assert graph_without_faq(html) == graph_without_faq(old), name
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
    for slug in NEW_GUIDES:
        assert f'href="/guides/{slug}/"' in index_html
    notary = (out / "guides" / "notary-options" / "index.html").read_text()
    assert "How do I get something notarized?" in notary
    assert 'href="/guides/in-person-vs-remote-notary/"' in notary
    duluth = (out / "duluth" / "index.html").read_text()
    duluth_faq = re.search(
        r"Can I get something notarized at the Duluth library\?</summary><p>(.*?)</p>", duluth).group(1)
    assert "We didn't find a fee on the page" in duluth_faq
    assert "not guaranteed" in duluth_faq
    assert "free" not in duluth_faq.lower()
    assert 'href="/guides/passport-acceptance-visit/"' in (out / "guides" / "passport-checklist" / "index.html").read_text()
    assert 'href="/guides/library-printing/"' in (out / "guides" / "printing-prices" / "index.html").read_text()
    # The guides index already lists every city. It does not get another generated block.
    assert "more-in-state" not in index_html
    for slug, title in (("privacy", "Privacy Policy | Errand Desk"), ("contact", "Contact Errand Desk")):
        html = (out / slug / "index.html").read_text()
        assert f"<title>{title}</title>" in html
        assert len(title) <= 60
        assert f'<link rel="canonical" href="https://erranddesk.com/{slug}/">' in html
        assert "erranddesk@protonmail.com" in html
        assert f"<loc>https://erranddesk.com/{slug}/</loc>" in sm
    about = (out / "about" / "index.html").read_text()
    assert "corrections contact will be added" not in about
    assert "erranddesk@protonmail.com" in about
    assert 'href="/contact/"' in about
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
