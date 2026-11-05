"""Build the browser search index from the same pages the static builder publishes.

The search page downloads one JSON file after a person submits the form.
Other pages do not link to that file. Tokens come from each page's title,
URL, description and visible body, so a new page is included on the next
build without a hand-maintained URL list.
"""
import html as htmlmod
import json
import re

# Packed posting: (doc_id * 16) + flags. Flags fit in the low 4 bits.
TITLE, URL, DESC, BODY = 1, 2, 4, 8

# Function words. Kept in sync with STOP_LIST in src/assets/search.js (the test checks).
STOP = frozenset("""
a about above after again all also am an and any are as at be because been
before below between both but by did do does during each few for from further
had has have having he her here hers him his how i if in into is it its itself
just me more most my no nor not of off on once only or other our out over own
per same she so some such than that the their them then there these they this
those through to too under until up very was we were what when where which
while who whom why with you your
""".split())

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_SCRIPT = re.compile(r"<script\b[^>]*>.*?</script>", re.I | re.S)
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.S)
_SUP = re.compile(r"<sup\b[^>]*>.*?</sup>", re.I | re.S)
_SOURCES = re.compile(r'<ol\b[^>]*class="sources"[^>]*>.*?</ol>', re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_H1 = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.I | re.S)
_TOKEN = re.compile(r"[a-z0-9]+")
_SENT = re.compile(r"(?<=[.!?])\s+")


def plain(fragment):
    """Visible text of an HTML fragment, without citation markers or the source list."""
    x = _COMMENT.sub(" ", fragment)
    x = _SCRIPT.sub(" ", x)
    x = _STYLE.sub(" ", x)
    x = _SUP.sub("", x)
    x = _SOURCES.sub(" ", x)
    x = _TAG.sub(" ", x)
    x = htmlmod.unescape(x)
    x = x.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    x = re.sub(r"\s+", " ", x).strip()
    return x


def tokenize(text):
    """Lowercase word tokens. Apostrophes are removed so don't and dont match."""
    text = text.lower().replace("'", "").replace("\u2019", "")
    return [t for t in _TOKEN.findall(text) if len(t) >= 2 and t not in STOP]


def _h1(body, fallback):
    m = _H1.search(body)
    if not m:
        return fallback
    text = plain(m.group(1))
    return text or fallback


def _excerpt(text, df, head=480, extra=320):
    """Opening sentences, plus a few later sentences that say something rare.

    The full token index still covers the rest of the page. This text is only
    what the results page can quote.
    """
    sents = [s.strip() for s in _SENT.split(text) if len(s.strip()) >= 20]
    parts, size, used = [], 0, set()
    for s in sents:
        s = s[:240]
        if size >= head:
            break
        parts.append(s)
        used.add(s)
        size += len(s) + 1
    extra_size = 0
    for raw in sents:
        if raw[:240] in used or raw in used:
            continue
        toks = tokenize(raw)
        if not any(df.get(t, 1) == 1 for t in toks):
            continue
        s = raw[:240]
        parts.append(s)
        used.add(s)
        extra_size += len(s) + 1
        if extra_size >= extra:
            break
    return " ".join(parts)


def build_index(pages):
    """pages: list of {url, title, description, body}. url is a root-relative path.

    Title flags are dropped for tokens that appear in most page titles (the
    shared "fax, notary, passports..." wording on city guides). A query for
    one of those topics can then prefer the guide whose URL is about that
    topic, while the city name in a title still ranks that city first.
    """
    docs = []
    prepared = []
    for page in pages:
        url = page["url"]
        if not url.startswith("/") or url != "/" and not url.endswith("/"):
            raise ValueError(f"search index url must be a canonical path: {url}")
        meta_title = page["title"].strip()
        description = re.sub(r"\s+", " ", page["description"]).strip()
        body_text = plain(page["body"])
        heading = _h1(page["body"], meta_title)
        prepared.append({
            "url": url,
            "title": heading,
            "meta_title": meta_title,
            "description": description,
            "body": body_text,
        })
    prepared.sort(key=lambda d: d["url"])

    df = {}
    for doc in prepared:
        for tok in set(tokenize(doc["body"])):
            df[tok] = df.get(tok, 0) + 1

    # token -> {doc_id: flags}
    post = {}

    def add(token, doc_id, flag):
        if len(token) < 2 or token in STOP:
            return
        bucket = post.get(token)
        if bucket is None:
            bucket = {}
            post[token] = bucket
        bucket[doc_id] = bucket.get(doc_id, 0) | flag

    for doc_id, doc in enumerate(prepared):
        excerpt = _excerpt(doc["body"], df)
        item = {"u": doc["url"], "t": doc["title"], "d": doc["description"]}
        if excerpt:
            item["x"] = excerpt
        docs.append(item)
        for tok in set(tokenize(doc["title"] + " " + doc["meta_title"])):
            add(tok, doc_id, TITLE)
        for tok in set(tokenize(doc["url"])):
            add(tok, doc_id, URL)
        for tok in set(tokenize(doc["description"])):
            add(tok, doc_id, DESC)
        for tok in set(tokenize(doc["body"])):
            add(tok, doc_id, BODY)

    n = len(docs)
    title_cap = int(n * 0.75)
    if n and title_cap < n:
        for token, bucket in list(post.items()):
            title_n = sum(1 for flags in bucket.values() if flags & TITLE)
            if title_n <= title_cap:
                continue
            for doc_id in list(bucket):
                flags = bucket[doc_id] & ~TITLE
                if flags:
                    bucket[doc_id] = flags
                else:
                    del bucket[doc_id]
            if not bucket:
                del post[token]

    packed = {}
    for token in sorted(post):
        nums = [(doc_id * 16) + flags for doc_id, flags in sorted(post[token].items())]
        packed[token] = nums
    return {"v": 1, "n": n, "docs": docs, "post": packed}


def dumps(index):
    """Deterministic JSON. Key order does not depend on the clock or PYTHONHASHSEED."""
    return json.dumps(index, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
