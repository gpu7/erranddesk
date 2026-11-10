#!/usr/bin/env python3
"""FAQ and schema parity for city pages and guides.

From the repo root:
    python3 site-src/tools/test_faq.py

Builds once in a temporary directory. Counts come from origin/main and that build.
"""
import html as htmlmod, json, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "site-src" / "build.py"
ORIGIN = "origin/main:erranddesk-site"


def origin_text(path):
    raw = subprocess.run(["git", "show", f"{ORIGIN}/{path}"], cwd=ROOT, capture_output=True)
    if raw.returncode != 0:
        raise SystemExit(f"missing {ORIGIN}/{path}")
    return raw.stdout.decode()


def plain(fragment):
    """Same visible-text rules build.py uses for FAQPage JSON-LD."""
    x = re.sub(r"<sup>.*?</sup>", "", fragment, flags=re.S)
    x = htmlmod.unescape(re.sub(r"<[^>]+>", "", x))
    x = re.sub(r"\s+", " ", x).strip()
    return re.sub(r"\s+([.,;:])", r"\1", x)


def detail_pairs(html):
    return re.findall(r"<details><summary>(.*?)</summary>(.*?)</details>", html, re.S)


def questions(html):
    return [(plain(q), plain(a)) for q, a in detail_pairs(html) if plain(q).endswith("?")]


def graph(html):
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    if not blocks:
        return None
    if len(blocks) != 1:
        raise SystemExit(f"expected one JSON-LD block, found {len(blocks)}")
    return json.loads(blocks[0].strip().replace("<\\/", "</"))


def faq_node(html):
    data = graph(html)
    if not data:
        return None
    nodes = [node for node in data["@graph"] if node.get("@type") == "FAQPage"]
    if not nodes:
        return None
    if len(nodes) != 1:
        raise SystemExit(f"more than one FAQPage")
    return nodes[0]


def audit(read, strict):
    """read(rel) -> html. strict requires every schema answer to match a visible question."""
    city_visible = city_schema = 0
    guide_visible = guide_schema = 0
    cities = guides = 0
    mismatched = []
    for rel in sorted(read_list):
        html = read(rel)
        qs = questions(html)
        node = faq_node(html)
        is_guide = rel.startswith("guides/")
        if is_guide:
            guides += 1
            if qs:
                guide_visible += 1
            if node:
                guide_schema += 1
        else:
            cities += 1
            if qs:
                city_visible += 1
            if node:
                city_schema += 1
        if bool(qs) != bool(node):
            raise SystemExit(f"{rel}: visible FAQ {len(qs)} vs schema {bool(node)}")
        if node:
            main = node["mainEntity"]
            paired = len(main) == len(qs) and all(
                item.get("name") == q and item["acceptedAnswer"]["text"] == a and q.endswith("?") and a
                for (q, a), item in zip(qs, main)
            )
            if not paired:
                mismatched.append(rel)
                if strict:
                    raise SystemExit(f"{rel}: schema text drifted ({qs[0][0] if qs else 'no question'!r})")
            folded = [q.casefold() for q, _ in qs]
            if len(folded) != len(set(folded)):
                raise SystemExit(f"{rel}: duplicate question")
        data = graph(html)
        if data:
            if data.get("@context") != "https://schema.org":
                raise SystemExit(f"{rel}: schema context")
            types = [node.get("@type") for node in data["@graph"]]
            if "LocalBusiness" in types or any(isinstance(t, list) and "LocalBusiness" in t for t in types):
                raise SystemExit(f"{rel}: LocalBusiness is not supported by this page")
            if types.count("FAQPage") > 1:
                raise SystemExit(f"{rel}: repeated FAQPage")
        if strict and node:
            names = {item["name"] for item in node["mainEntity"]}
            for q, _ in detail_pairs(html):
                label = plain(q)
                if not label.endswith("?") and label in names:
                    raise SystemExit(f"{rel}: non-question disclosure entered FAQPage")
    return {
        "cities": cities,
        "city_visible": city_visible,
        "city_schema": city_schema,
        "guides": guides,
        "guide_visible": guide_visible,
        "guide_schema": guide_schema,
        "mismatched": mismatched,
    }


def answer(html, question):
    for q, a in questions(html):
        if q == question:
            return a
    raise SystemExit(f"missing question: {question}")


def main():
    global read_list
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, str(BUILD), "--out", tmp], check=True, cwd=ROOT)
        out = Path(tmp)
        read_list = []
        for path in sorted(out.glob("*/index.html")):
            rel = path.relative_to(out).as_posix()
            if rel in ("about/index.html", "disclosure/index.html", "map/index.html", "search/index.html", "contact/index.html", "privacy/index.html"):
                continue
            if rel.startswith("guides/"):
                continue
            read_list.append(rel)
        for path in sorted((out / "guides").glob("*/index.html")):
            read_list.append(path.relative_to(out).as_posix())
        before = audit(origin_text, strict=False)
        after = audit(lambda rel: (out / rel).read_text(), strict=True)
        print("before", before)
        print("after", after)
        # The published New York page on origin/main matches its FAQ schema.
        assert before["mismatched"] == []
        assert before["cities"] == after["cities"] == 265
        assert before["city_visible"] == before["city_schema"] == 265
        assert after["city_visible"] == after["city_schema"] == 265
        assert before["guides"] == after["guides"] == 20
        assert before["guide_visible"] == before["guide_schema"] == 20
        assert after["guide_visible"] == after["guide_schema"] == 20

        expanded = 0
        added_questions = 0
        for rel in read_list:
            old_q = questions(origin_text(rel))
            new_q = questions((out / rel).read_text())
            old_map = dict(old_q)
            if len(new_q) < len(old_q):
                raise SystemExit(f"{rel}: lost a question")
            if len(new_q) > len(old_q) + 2:
                raise SystemExit(f"{rel}: more than two new questions")
            added_questions += len(new_q) - len(old_q)
            for q, a in new_q:
                if q not in old_map:
                    if "Nov 6, 2026" in a or "November 6" in a:
                        raise SystemExit(f"{rel}: new FAQ claims a Nov 6 check ({q})")
                    continue
                if a != old_map[q]:
                    expanded += 1
                    if "Nov 6, 2026" in a:
                        raise SystemExit(f"{rel}: expanded FAQ claims a Nov 6 check ({q})")
            title = re.search(r"<title>(.*?)</title>", (out / rel).read_text()).group(1)
            old_title = re.search(r"<title>(.*?)</title>", origin_text(rel)).group(1)
            if title != old_title:
                raise SystemExit(f"{rel}: title changed")
            desc = re.search(r'<meta name="description" content="([^"]*)">', (out / rel).read_text()).group(1)
            old_desc = re.search(r'<meta name="description" content="([^"]*)">', origin_text(rel)).group(1)
            if desc != old_desc:
                raise SystemExit(f"{rel}: description changed")

        denver = (out / "denver" / "index.html").read_text()
        denver_a = answer(denver, "Does the Denver Public Library offer notary service?")
        assert "didn't find" in denver_a and "free" not in denver_a.lower()
        duluth_a = answer((out / "duluth" / "index.html").read_text(), "Can I get something notarized at the Duluth library?")
        assert duluth_a == answer(origin_text("duluth/index.html"), "Can I get something notarized at the Duluth library?")
        assert "We didn't find a fee" in duluth_a and "not guaranteed" in duluth_a and "free" not in duluth_a.lower()
        savannah_a = answer((out / "savannah" / "index.html").read_text(), "Can I get something notarized at the Savannah library?")
        assert "$2.00 per document" in savannah_a
        island_a = answer((out / "grand-island" / "index.html").read_text(), "Can I get something notarized at the Grand Island library?")
        assert "does not provide public notary services" in island_a
        hilo = (out / "hilo" / "index.html").read_text()
        hilo_p = answer(hilo, "Where can I apply for a passport in Hilo?")
        assert "0 passport acceptance facilities" in hilo_p and "not Hilo" in hilo_p
        hilo_print = answer(hilo, "How much does printing cost at the Hilo library?")
        assert "donation" in hilo_print and "not less than 20¢" in hilo_print
        morgantown_a = answer((out / "morgantown" / "index.html").read_text(), "Can I get something notarized at the Morgantown library?")
        assert "didn't confirm a fee" in morgantown_a and "doesn't call it free" in morgantown_a
        abq = answer(origin_text("albuquerque/index.html"), "Is there a free notary in Albuquerque?")
        assert abq == answer((out / "albuquerque" / "index.html").read_text(), "Is there a free notary in Albuquerque?")
        assert "outside providers" in abq
        checklist = (out / "guides" / "passport-checklist" / "index.html").read_text()
        renew = answer(checklist, "What documents do I need to renew a passport by mail?")
        assert "DS-82" in renew and "16 or older" in renew and "Don't send cash" in renew
        notary = (out / "guides" / "notary-options" / "index.html").read_text()
        assert "How do I get something notarized?" in notary
        nyc = (out / "new-york-city" / "index.html").read_text()
        assert "Manhattan (New York County): 25 facilities" in nyc
        nyc_names = [item["name"] for item in faq_node(nyc)["mainEntity"]]
        assert all(name.endswith("?") for name in nyc_names)
        assert not any(name.startswith("Manhattan") for name in nyc_names)
        sm = (out / "sitemap.xml").read_text()
        old_sm = origin_text("sitemap.xml")
        sm_norm = re.sub(
            r"  <url><loc>https://erranddesk.com/(?:contact|privacy)/</loc><lastmod>2026-11-10</lastmod></url>\n",
            "",
            sm,
        )
        sm_norm = sm_norm.replace(
            "<loc>https://erranddesk.com/about/</loc><lastmod>2026-11-10</lastmod>",
            "<loc>https://erranddesk.com/about/</loc><lastmod>2026-10-21</lastmod>",
        )
        # knoxville/bangor/columbus-ga lastmods are already 2026-11-09 on origin/main.
        assert sm_norm == old_sm
        print(f"added questions {added_questions}; expanded answers {expanded}")
    print("ok")


if __name__ == "__main__":
    main()
