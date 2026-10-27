# Errand Desk site source

This folder is the source of truth for https://erranddesk.com. `../erranddesk-site/` is the built output that gets deployed. Don't edit it by hand. Edit the files here and rebuild.

## Build

Requirements: Python 3.8 or newer, standard library only. Pillow is only needed if you regenerate the Open Graph image with `tools/make_og_image.py`. The committed `src/static/og-image.png` is used as is.

From the repo root, this one command rebuilds the deployed folder in place:

```sh
python3 site-src/build.py --out erranddesk-site
```

- Without `--out`, the output goes to `site-src/public/`, which is git-ignored. Use that to preview, e.g. `python3 -m http.server 8787 --directory site-src/public`.
- The output directory is deleted and fully rebuilt on every run.
- The build is deterministic. Dates come only from each page's `"lastmod"` meta, or from `default_lastmod` in `site.config.json`, never from the clock. Rebuilding unchanged sources gives byte-identical output, so the sitemap doesn't churn.

## Layout

```
build.py            the builder
site.config.json    base_url, default_lastmod, cf_analytics_token (public Cloudflare Web Analytics site token)
src/layout.html     shared header, nav, footer; tokens like {{title}}, {{nav_fax}}, {{analytics}}
src/assets/         style.css (link gets ?v=<sha256 prefix> for cache-busting)
src/pages/          page bodies, each starting with <!--meta {"title","description","nav","lastmod","schema"} -->
src/static/         copied to the site root: 404.html, og-image.png, favicons, icons
tools/              make_og_image.py (optional; needs Pillow and the Inter font, so edit the font path for your machine)
```

How pages map to URLs and to `erranddesk-site/`:

| Source | URL | Output file |
|---|---|---|
| `src/pages/index.html` | `/` | `erranddesk-site/index.html` |
| `src/pages/about.html` | `/about/` | `erranddesk-site/about/index.html` |
| `src/pages/guides/index.html` | `/guides/` | `erranddesk-site/guides/index.html` |
| `src/pages/guides/<name>.html` | `/guides/<name>/` | `erranddesk-site/guides/<name>/index.html` |
| `src/assets/*` | `/assets/*` | `erranddesk-site/assets/*` |
| `src/static/*` | `/*` | `erranddesk-site/*` |

The builder also writes `sitemap.xml` (every page without `"noindex": true`) and `robots.txt`.

Page `schema` values:
- `website`: WebSite JSON-LD
- `article`: Article, BreadcrumbList and FAQPage JSON-LD, built from the page's own `<details><summary>` FAQ
- `collection`: CollectionPage and BreadcrumbList
- `page`: no JSON-LD

To add a nav item, add a `{{nav_<key>}}` token in `layout.html` and the matching `.replace` in `build.py`, then set `"nav": "<key>"` in the page meta.

## Fact rules (every page)

1. **Sourced figures only.** Every price, fee, limit or service claim comes from the provider's or agency's official page, with a numbered citation that links to it.
2. **Last-checked dates.** Each page shows "All figures last checked <date>", and every source in the Sources list ends with "(last checked <date>)". Re-check before you change a figure.
3. **No invented data.** If there's no published national price, write "No national price published" and say why, e.g. "varies by location". Never estimate, average or round. Keep qualifiers like "starting at", and don't turn "not stated" into "not available".
4. **Examples are labeled.** A single store, county or credit union is an example, never national policy.
5. **Sourced FAQs.** FAQ answers must be sourced on the same page.
6. **Notes on sensitive topics.** Legal-adjacent and government-adjacent pages carry a "not legal advice" or "not affiliated with the government" note.
7. **Affiliate links.** Every affiliate link uses `rel="sponsored nofollow noopener"` and is followed by `<span class="aff">(paid link)</span>`. Affiliate links never change the facts. No placeholder links. The disclosure is at `/disclosure/`.
8. **Stable URLs.** Never change a URL after launch; add a redirect instead.

## Deploy

After a PR that changes `erranddesk-site/` is merged to `main`:
1. Upload `erranddesk-site/` to the site's S3 bucket with explicit Content-Type and Cache-Control headers. HTML and sitemap get 5 minutes; CSS, icons and PNGs get one year, immutable; og-image.png gets one day. Don't use `--delete`.
2. Invalidate `/*` on the CloudFront distribution and wait for it to complete.
3. Spot-check the live site with curl: status codes, titles, sitemap, og-image, http→https and 404.

The bucket and distribution identifiers are deliberately kept out of this repo.
