#!/usr/bin/env python3
"""Ping IndexNow after a deploy so search engines can fetch changed pages sooner.

From the repo root, after the CloudFront invalidation completes:

    python3 site-src/tools/indexnow_ping.py --all
    python3 site-src/tools/indexnow_ping.py https://erranddesk.com/about/ ...

The key is read from the IndexNow key file in site-src/src/static/ (a 32-character
hex filename whose contents are exactly that key). --all uses every <loc> in
erranddesk-site/sitemap.xml, in batches of at most 10,000 URLs. Prints each
HTTP status from https://api.indexnow.org/indexnow.
"""
import argparse, json, re, sys, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "site-src" / "src" / "static"
SITEMAP = ROOT / "erranddesk-site" / "sitemap.xml"
ENDPOINT = "https://api.indexnow.org/indexnow"
HOST = "erranddesk.com"
BATCH = 10000
KEY_NAME = re.compile(r"^[0-9a-f]{32}\.txt$")


def load_key():
    matches = [p for p in STATIC.glob("*.txt") if KEY_NAME.match(p.name)]
    if len(matches) != 1:
        names = ", ".join(p.name for p in matches) or "none"
        raise SystemExit(f"expected one IndexNow key file in {STATIC}, found {names}")
    path = matches[0]
    key = path.read_text()
    if key != path.stem:
        raise SystemExit(f"{path.name} must contain exactly the key (the filename without .txt)")
    return key


def sitemap_urls():
    if not SITEMAP.is_file():
        raise SystemExit(f"missing sitemap: {SITEMAP}")
    urls = re.findall(r"<loc>(.*?)</loc>", SITEMAP.read_text())
    if not urls:
        raise SystemExit(f"no <loc> entries in {SITEMAP}")
    return urls


def post_batch(key, urls):
    body = json.dumps({
        "host": HOST,
        "key": key,
        "keyLocation": f"https://{HOST}/{key}.txt",
        "urlList": urls,
    }).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    print(status)
    return status


def main():
    ap = argparse.ArgumentParser(description="Submit published Errand Desk URLs to IndexNow.")
    ap.add_argument("urls", nargs="*", help="https://erranddesk.com/... URLs to submit")
    ap.add_argument("--all", action="store_true", help="submit every URL in erranddesk-site/sitemap.xml")
    args = ap.parse_args()
    if bool(args.urls) == args.all:
        raise SystemExit("pass URL arguments or --all, not both or neither")
    urls = sitemap_urls() if args.all else list(args.urls)
    key = load_key()
    ok = True
    for i in range(0, len(urls), BATCH):
        chunk = urls[i:i + BATCH]
        if post_batch(key, chunk) not in (200, 202):
            ok = False
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
