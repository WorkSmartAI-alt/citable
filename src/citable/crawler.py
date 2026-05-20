"""Async crawler. httpx + BeautifulSoup, per-host politeness, dual-UA SPA detection.

Crawl strategy:
1. Fetch homepage with default UA. Measure render time and body length.
2. Fetch homepage again with Googlebot UA. If rendered HTML body length
   differs by more than 30 percent, mark site as SPA and use Googlebot UA
   for subsequent fetches.
3. Discover URLs from sitemap.xml if present, fall back to internal links
   from homepage. Limit to N pages (default 20, max 100).
4. Fetch each page, parse with BeautifulSoup, extract Page fields.
5. Build SiteContext from robots.txt + sitemap.xml + homepage headers.
"""

from __future__ import annotations

import asyncio
import gzip
import re
import time
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import httpx
from bs4 import BeautifulSoup

from citable.models import Page, SiteContext

# URL extensions we never want to crawl as HTML pages
SKIP_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
    ".css", ".js", ".xml", ".gz", ".zip", ".tar", ".rar", ".7z",
    ".mp4", ".mp3", ".webm", ".avi", ".mov", ".wmv",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".rss", ".atom", ".json", ".txt",
}

# Path prefixes that belong to known framework / CDN patterns. These return
# 4xx on direct request but are handled by client-side JavaScript or are
# never meant to be navigated to. Treating them as broken links is a false
# positive. citable excludes them from crawl AND from C-22 link probing.
SKIP_PATH_PREFIXES = (
    "/cdn-cgi/",         # Cloudflare proxy paths (email obfuscation, etc.)
    "/wp-json/",         # WordPress REST API endpoints
    "/wp-admin/",        # WordPress admin
    "/wp-content/uploads/",  # WP uploads (binary, not HTML)
    "/xmlrpc.php",       # WordPress XML-RPC
    "/feed/",            # RSS feeds
    "/comments/feed/",
    "/?p=",              # WP query-string post IDs (handled by canonical)
)


def is_html_url(url: str) -> bool:
    """Skip URLs that obviously point at non-HTML resources, framework paths,
    or CDN endpoints that 4xx on direct fetch."""
    try:
        parsed = urlparse(url)
        path = parsed.path.lower()
    except Exception:
        return False
    for ext in SKIP_EXTENSIONS:
        if path.endswith(ext):
            return False
    for prefix in SKIP_PATH_PREFIXES:
        if prefix in path:
            return False
    # Query strings that look like framework artifacts (oEmbed, RSD, etc.)
    if parsed.query:
        q = parsed.query.lower()
        if any(needle in q for needle in ("rsd", "oembed", "_embed")):
            return False
    return True

DEFAULT_UA = "citable/0.1.0 (+https://work-smart.ai/citable)"
GOOGLEBOT_UA = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)

TIMEOUT = httpx.Timeout(30.0, connect=10.0)
PER_HOST_CONCURRENCY = 5
PER_HOST_DELAY = 0.2  # seconds


def normalize_domain(value: str) -> str:
    """Accept `example.com`, `https://example.com`, `example.com/blog`,
    return canonical `https://example.com` (no trailing slash).
    """
    value = value.strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    return f"{parsed.scheme}://{parsed.netloc}"


def normalize_target(value: str) -> tuple[str, str]:
    """Parse user input into (root, path_prefix).

    - `example.com` -> (`https://example.com`, ``) - audit whole site
    - `example.com/resources` -> (`https://example.com`, `/resources`) - scoped
    - `https://www.example.com/resources/` -> (`https://www.example.com`, `/resources`)

    The path_prefix is stored without trailing slash for matching. Empty string
    means whole-site (no scoping).
    """
    value = value.strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    root = f"{parsed.scheme}://{parsed.netloc}"
    if not parsed.path or parsed.path == "/":
        prefix = ""
    else:
        prefix = parsed.path.rstrip("/")
    return root, prefix


def matches_prefix(url: str, root: str, prefix: str) -> bool:
    """Return True if `url` is on the same host as root AND its path is under
    the given prefix. Empty prefix matches every same-host URL.

    Examples with prefix=`/resources`:
    - /resources -> match (exact)
    - /resources/ -> match
    - /resources/foo -> match
    - /resources-blog -> NO match (avoids accidental prefix match)
    - /about -> NO match
    """
    if not same_host(url, root):
        return False
    if not prefix:
        return True
    path = urlparse(url).path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return path == prefix or path.startswith(prefix + "/")


def _bare_host(netloc: str) -> str:
    """Strip leading `www.` from a host. Lowercase. Drop port."""
    host = netloc.lower().split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def same_host(url: str, root: str) -> bool:
    """Check if url shares the host of root. Treats www.example.com and
    example.com as the same host."""
    return _bare_host(urlparse(url).netloc) == _bare_host(urlparse(root).netloc)


def canonicalize_url(url: str) -> str:
    """Normalize a URL for dedup. Strip trailing slash on non-root paths,
    lowercase host, drop fragment, treat empty path as `/`."""
    if not url:
        return ""
    p = urlparse(url)
    path = p.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    netloc = p.netloc.lower()
    query = f"?{p.query}" if p.query else ""
    return f"{p.scheme}://{netloc}{path}{query}"


class HostRateLimiter:
    """One semaphore + one min-delay lock per host. Avoids overwhelming a site."""

    def __init__(self) -> None:
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._last_request: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _key(self, url: str) -> str:
        return urlparse(url).netloc

    async def acquire(self, url: str) -> asyncio.Semaphore:
        host = self._key(url)
        if host not in self._semaphores:
            self._semaphores[host] = asyncio.Semaphore(PER_HOST_CONCURRENCY)
            self._locks[host] = asyncio.Lock()
        sem = self._semaphores[host]
        await sem.acquire()
        async with self._locks[host]:
            last = self._last_request.get(host, 0.0)
            gap = time.monotonic() - last
            if gap < PER_HOST_DELAY:
                await asyncio.sleep(PER_HOST_DELAY - gap)
            self._last_request[host] = time.monotonic()
        return sem

    def release(self, url: str) -> None:
        host = self._key(url)
        if host in self._semaphores:
            self._semaphores[host].release()


async def fetch_one(
    client: httpx.AsyncClient,
    url: str,
    limiter: HostRateLimiter,
    ua: str,
) -> tuple[httpx.Response | None, int, str]:
    """Fetch one URL with rate limiting. Returns (response, render_ms, error)."""
    await limiter.acquire(url)
    try:
        start = time.monotonic()
        try:
            resp = await client.get(
                url,
                headers={"User-Agent": ua, "Accept": "text/html,application/xhtml+xml"},
                follow_redirects=True,
            )
            render_ms = int((time.monotonic() - start) * 1000)
            return resp, render_ms, ""
        except httpx.HTTPError as e:
            return None, 0, str(e)
    finally:
        limiter.release(url)


def parse_page(url: str, resp: httpx.Response, render_ms: int, ua: str) -> Page:
    """Parse an HTTP response into a Page object. Pure function, no I/O."""
    page = Page(
        url=url,
        status_code=resp.status_code,
        final_url=str(resp.url),
        render_time_ms=render_ms,
        headers={k.lower(): v for k, v in resp.headers.items()},
        fetched_via="googlebot" if "googlebot" in ua.lower() else "default",
    )

    if resp.status_code >= 400:
        return page

    try:
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        page.error = f"parse_error: {e}"
        return page

    # title
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        page.title = title_tag.string.strip()

    # meta description
    md = soup.find("meta", attrs={"name": "description"})
    if md and md.get("content"):
        page.meta_description = md["content"].strip()

    # html lang
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        page.html_lang = html_tag["lang"].strip()

    # H1 + H2
    page.h1_texts = [h.get_text(strip=True) for h in soup.find_all("h1")]
    page.h2_texts = [h.get_text(strip=True) for h in soup.find_all("h2")]

    # canonical
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        page.canonical = canonical["href"].strip()

    # og tags
    for tag in soup.find_all("meta", attrs={"property": True}):
        prop = tag.get("property", "")
        if prop.startswith("og:") and tag.get("content"):
            page.og[prop] = tag["content"].strip()

    # hreflang
    for link in soup.find_all("link", rel="alternate"):
        hl = link.get("hreflang")
        href = link.get("href")
        if hl and href:
            page.hreflang.append((hl.strip(), href.strip()))

    # schema (JSON-LD blocks)
    import json

    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string.strip())
            if isinstance(data, list):
                page.schema_blocks.extend(data)
            else:
                page.schema_blocks.append(data)
        except json.JSONDecodeError:
            page.schema_blocks.append({"__parse_error": True, "_raw_snippet": script.string[:120]})

    page.schema_raw_count = len(page.schema_blocks)

    # image alt
    images = soup.find_all("img")
    content_images = [
        img for img in images
        if img.get("role") != "presentation"
        and img.get("aria-hidden", "").lower() != "true"
    ]
    page.image_alt_total = len(content_images)
    page.image_alt_missing = sum(
        1 for img in content_images if not (img.get("alt") or "").strip()
    )

    # first paragraph after H1 (for answer capsule check)
    h1 = soup.find("h1")
    if h1:
        nxt = h1.find_next("p")
        if nxt:
            page.first_paragraph = nxt.get_text(" ", strip=True)

    # Internal links with anchor text (for Internal Linkage category)
    from urllib.parse import urlparse as _urlparse
    page_host = _urlparse(page.final_url or url).netloc
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(page.final_url or url, href)
        if not absolute.startswith(("http://", "https://")):
            continue
        target_host = _urlparse(absolute).netloc
        # Treat www.host and host as same
        bare_page = page_host.lower().removeprefix("www.")
        bare_target = target_host.lower().removeprefix("www.")
        if bare_page != bare_target:
            continue
        anchor = a.get_text(" ", strip=True)
        # Cap anchor text length to avoid storing massive blob text from button labels
        page.internal_links.append((absolute.split("#", 1)[0], anchor[:200]))

    return page


async def fetch_text(client: httpx.AsyncClient, url: str, limiter: HostRateLimiter, ua: str) -> tuple[int, str]:
    """Plain text fetch (for robots.txt, sitemap.xml). Returns (status, body).
    Decompresses gzipped sitemaps transparently."""
    resp, _, err = await fetch_one(client, url, limiter, ua)
    if resp is None or err:
        return 0, ""
    body = resp.text
    # Handle .xml.gz sitemaps. httpx auto-decodes Content-Encoding: gzip, so we
    # only need to manually decompress when the URL itself ends in .gz.
    if url.lower().endswith(".gz"):
        try:
            raw = resp.content
            body = gzip.decompress(raw).decode("utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            pass
    return resp.status_code, body


def discover_internal_links(homepage: Page, root: str, max_links: int) -> list[str]:
    """Pull internal links from homepage HTML for fallback URL discovery."""
    # We do not store full HTML on Page, so re-parse from a small set of clues.
    # Simpler approach: caller passes raw HTML. We will do it via response cache.
    # For now, return empty; sitemap is primary discovery path.
    _ = homepage, root, max_links
    return []


def parse_sitemap(xml_text: str, root: str) -> list[str]:
    """Extract URLs from sitemap.xml. Handles sitemapindex by returning sub-sitemap URLs
    (caller can fetch them recursively). Limits to same-host URLs.
    """
    urls: list[str] = []
    try:
        tree = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    except ET.ParseError:
        return urls
    # Strip xmlns for easier xpath
    for el in tree.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    for loc in tree.iter("loc"):
        if loc.text:
            u = loc.text.strip()
            if same_host(u, root):
                urls.append(u)
    return urls


def extract_links_from_html(html: str, root: str) -> list[str]:
    """Pull internal anchor hrefs from HTML. Returns absolute URLs on same host."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return []
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(root + "/", href)
        if same_host(absolute, root) and absolute.startswith(("http://", "https://")):
            # drop fragments
            absolute = absolute.split("#", 1)[0]
            if absolute and absolute not in links:
                links.append(absolute)
    return links


def _looks_like_sitemap_index(urls: list[str]) -> bool:
    """A sitemap-index file lists other sitemap files. Heuristic: at least 2 of
    the first 5 URLs end in .xml or .xml.gz and contain 'sitemap'."""
    sample = urls[:5]
    if not sample:
        return False
    score = sum(
        1 for u in sample
        if (u.endswith(".xml") or u.endswith(".xml.gz")) and "sitemap" in u.lower()
    )
    return score >= 2


async def _flatten_sitemap_index(
    client: httpx.AsyncClient,
    parsed: list[str],
    limiter: HostRateLimiter,
    ua: str,
    target_count: int,
    max_subsitemap_fetches: int = 25,
) -> list[str]:
    """Recursively fetch sub-sitemaps until we have enough URLs or hit the cap."""
    urls: list[str] = []
    fetched = 0
    queue = list(parsed)
    while queue and len(urls) < target_count and fetched < max_subsitemap_fetches:
        sub = queue.pop(0)
        st2, body2 = await fetch_text(client, sub, limiter, ua)
        fetched += 1
        if st2 != 200 or not body2:
            continue
        more = parse_sitemap(body2, sub)  # use sub as root for same-host check
        if _looks_like_sitemap_index(more):
            queue = more + queue  # depth-first into nested indexes
        else:
            urls.extend(more)
    return urls


async def discover_urls(
    client: httpx.AsyncClient,
    root: str,
    limiter: HostRateLimiter,
    ua: str,
    max_pages: int,
    cached_homepage_html: str | None = None,
    path_prefix: str = "",
) -> tuple[list[str], SiteContext]:
    """Build a URL list for the crawl. Prefer sitemap, fall back to homepage links,
    then depth-2 link crawl if still short.

    When `path_prefix` is non-empty (e.g. `/resources`), only URLs whose path is
    under the prefix are included. robots.txt and sitemap.xml are still fetched
    at the root (they live there), but URLs returned by the sitemap are filtered.
    """
    display_domain = f"{root}{path_prefix}" if path_prefix else root
    ctx = SiteContext(domain=display_domain)

    # robots.txt
    robots_url = f"{root}/robots.txt"
    status, body = await fetch_text(client, robots_url, limiter, ua)
    ctx.robots_status = status
    ctx.robots_txt = body if status == 200 else ""

    # sitemap candidates: well-known paths + robots.txt directive
    sitemap_candidates = [
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/sitemap-index.xml",
        "/sitemap.xml.gz",
    ]
    if ctx.robots_txt:
        for line in ctx.robots_txt.splitlines():
            m = re.match(r"\s*sitemap:\s*(\S+)", line, re.I)
            if m:
                sm_path = m.group(1)
                if sm_path not in sitemap_candidates:
                    sitemap_candidates.append(sm_path)

    sitemap_urls: list[str] = []
    for path in sitemap_candidates:
        sm_url = path if path.startswith("http") else f"{root}{path}"
        st, body = await fetch_text(client, sm_url, limiter, ua)
        if st != 200 or not body.strip():
            continue
        ctx.sitemap_url = sm_url
        ctx.sitemap_status = st
        parsed = parse_sitemap(body, root)
        if _looks_like_sitemap_index(parsed):
            # Iterate sub-sitemaps until we have plenty of URLs
            sitemap_urls = await _flatten_sitemap_index(
                client, parsed, limiter, ua, target_count=max_pages * 3
            )
        else:
            sitemap_urls = parsed
        if sitemap_urls:
            break

    # Skip non-HTML URLs from the sitemap. Apply path-prefix filter if scoped.
    sitemap_urls = [u for u in sitemap_urls if is_html_url(u)]
    if path_prefix:
        sitemap_urls = [u for u in sitemap_urls if matches_prefix(u, root, path_prefix)]
    ctx.sitemap_urls = sitemap_urls

    # The crawl seed depends on scope: prefix URL if scoped, otherwise root.
    if path_prefix:
        seed_url = f"{root}{path_prefix}/"  # explicit trailing slash; httpx follows redirects
    else:
        seed_url = root

    # Build URL list: seed + sitemap URLs (deduped via canonical form, capped)
    urls: list[str] = []
    seen: set[str] = set()
    for candidate in [seed_url] + sitemap_urls:
        if not is_html_url(candidate):
            continue
        if not matches_prefix(candidate, root, path_prefix):
            continue
        key = canonicalize_url(candidate)
        if key in seen:
            continue
        seen.add(key)
        urls.append(candidate)
        if len(urls) >= max_pages:
            break

    # Fallback 1: if we have fewer than max_pages, pull internal links from the
    # seed page (or homepage if no scope). For prefix audits this is critical:
    # the resource hub itself is the best source of in-scope links.
    fallback_source_url = seed_url if path_prefix else root
    if len(urls) < max_pages:
        # Use cached homepage HTML only if we are NOT scoped (otherwise we need
        # the prefix page's HTML, not the homepage's).
        if path_prefix:
            resp, _, _ = await fetch_one(client, fallback_source_url, limiter, ua)
            source_html = resp.text if resp and resp.status_code == 200 else None
        else:
            source_html = cached_homepage_html
            if source_html is None:
                resp, _, _ = await fetch_one(client, fallback_source_url, limiter, ua)
                if resp and resp.status_code == 200:
                    source_html = resp.text
        if source_html:
            hub_links = [
                link for link in extract_links_from_html(source_html, root)
                if is_html_url(link) and matches_prefix(link, root, path_prefix)
            ]
            for link in hub_links:
                key = canonicalize_url(link)
                if key in seen:
                    continue
                seen.add(key)
                urls.append(link)
                if len(urls) >= max_pages:
                    break

    # Fallback 2: depth-2 BFS from the hub pages, still respecting the prefix.
    if len(urls) < max(3, max_pages // 2):
        hub_budget = min(5, len(urls))
        for hub_url in list(urls)[:hub_budget]:
            if len(urls) >= max_pages:
                break
            resp, _, _ = await fetch_one(client, hub_url, limiter, ua)
            if not resp or resp.status_code != 200:
                continue
            for link in extract_links_from_html(resp.text, root):
                if not is_html_url(link):
                    continue
                if not matches_prefix(link, root, path_prefix):
                    continue
                key = canonicalize_url(link)
                if key in seen:
                    continue
                seen.add(key)
                urls.append(link)
                if len(urls) >= max_pages:
                    break

    # Scoped audits also follow 1 hop OFF-prefix to capture linked content.
    # WE Family case: /resources/ hub paginates as /resources/page/2/, /page/3/,
    # /page/4/. Each pagination page links to ~9 unique /resource/foo articles.
    # We must harvest links from EVERY in-prefix page, not just the seed.
    # The user's mental model is "audit /resources/ AND what it links to."
    if path_prefix and len(urls) < max_pages:
        in_prefix_urls = [
            u for u in urls
            if matches_prefix(u, root, path_prefix)
        ]
        # Cap how many hubs we fetch for expansion to keep audits fast.
        EXPANSION_HUB_CAP = 10
        for hub_url in in_prefix_urls[:EXPANSION_HUB_CAP]:
            if len(urls) >= max_pages:
                break
            resp, _, _ = await fetch_one(client, hub_url, limiter, ua)
            if not resp or resp.status_code != 200:
                continue
            for link in extract_links_from_html(resp.text, root):
                if not is_html_url(link):
                    continue
                # Same-host only, no prefix filter — that's the point
                if not same_host(link, root):
                    continue
                key = canonicalize_url(link)
                if key in seen:
                    continue
                seen.add(key)
                urls.append(link)
                if len(urls) >= max_pages:
                    break

    return urls[:max_pages], ctx


async def detect_spa_with_cache(
    client: httpx.AsyncClient, root: str, limiter: HostRateLimiter
) -> tuple[bool, str | None, dict[str, str]]:
    """Compare default-UA vs Googlebot-UA on the homepage. Returns
    (is_spa, googlebot_html_cache, googlebot_response_headers).
    Cache lets later steps avoid re-fetching the homepage."""
    resp_a, _, _ = await fetch_one(client, root, limiter, DEFAULT_UA)
    resp_b, _, _ = await fetch_one(client, root, limiter, GOOGLEBOT_UA)

    headers: dict[str, str] = {}
    body_b_text: str | None = None

    if resp_b is not None:
        headers = {k.lower(): v for k, v in resp_b.headers.items()}
        body_b_text = resp_b.text

    if not resp_a or not resp_b:
        return False, body_b_text, headers

    body_a_len = len(resp_a.text or "")
    body_b_len = len(body_b_text or "")

    if body_b_len == 0:
        return False, body_b_text, headers

    diff = abs(body_a_len - body_b_len) / max(body_a_len, body_b_len, 1)
    return diff > 0.30, body_b_text, headers


async def crawl(target: str, max_pages: int = 20, force_googlebot: bool = True) -> tuple[list[Page], SiteContext]:
    """Top-level crawl entry point. Accepts a domain (`example.com`) or a
    URL with a path (`example.com/resources/`) for scoped audits. Returns
    (pages, site_context)."""
    root, path_prefix = normalize_target(target)
    limiter = HostRateLimiter()

    async with httpx.AsyncClient(
        http2=True,
        timeout=TIMEOUT,
        verify=True,
    ) as client:
        spa, cached_html, homepage_headers = await detect_spa_with_cache(client, root, limiter)
        ua = GOOGLEBOT_UA if (spa or force_googlebot) else DEFAULT_UA

        urls, ctx = await discover_urls(
            client, root, limiter, ua, max_pages,
            cached_homepage_html=cached_html,
            path_prefix=path_prefix,
        )
        ctx.spa_detected = spa
        ctx.homepage_headers = homepage_headers

        # When scoped to a path, also parse the root homepage so site-level
        # checks (C-15 Organization, sameAs) can still evaluate entity identity
        # against the actual root, not the section landing page.
        if path_prefix and cached_html:
            class _FauxResponse:
                status_code = 200
                text = cached_html
                headers = homepage_headers
                url = root
            ctx.root_page = parse_page(root, _FauxResponse(), 0, ua)  # type: ignore[arg-type]

        async def fetch_and_parse(url: str) -> Page:
            resp, render_ms, err = await fetch_one(client, url, limiter, ua)
            if resp is None:
                return Page(url=url, error=err, fetched_via="googlebot" if ua == GOOGLEBOT_UA else "default")
            page = parse_page(url, resp, render_ms, ua)
            if page.html_lang:
                ctx.languages_seen.add(page.html_lang.split("-")[0].lower())
            return page

        tasks = [fetch_and_parse(u) for u in urls]
        pages = await asyncio.gather(*tasks)

        # Build link graph (URL -> list of (target, anchor)). Used by Internal
        # Linkage checks. Skip pages that failed to fetch.
        for p in pages:
            if p.status_code == 200 and p.internal_links:
                ctx.link_graph[p.final_url or p.url] = list(p.internal_links)

        # Probe link targets for broken-link detection (C-22). We sample to
        # keep the audit fast: take up to 50 unique link targets that are NOT
        # already in the crawled pages (those statuses are already known).
        crawled_urls = {canonicalize_url(p.final_url or p.url) for p in pages}
        link_targets: list[str] = []
        seen_targets: set[str] = set()
        for src, links in ctx.link_graph.items():
            for target, _anchor in links:
                key = canonicalize_url(target)
                if key in crawled_urls or key in seen_targets:
                    continue
                if not is_html_url(target):
                    continue
                seen_targets.add(key)
                link_targets.append(target)
                if len(link_targets) >= 50:
                    break
            if len(link_targets) >= 50:
                break

        # Probe with HEAD (fall back to GET if HEAD not supported)
        async def probe(target: str) -> tuple[str, int]:
            await limiter.acquire(target)
            try:
                try:
                    r = await client.head(
                        target,
                        headers={"User-Agent": ua},
                        follow_redirects=True,
                    )
                    if r.status_code == 405 or r.status_code >= 500:
                        # Some hosts disallow HEAD. Retry with GET.
                        r = await client.get(target, headers={"User-Agent": ua}, follow_redirects=True)
                    return target, r.status_code
                except httpx.HTTPError:
                    return target, 0
            finally:
                limiter.release(target)

        if link_targets:
            probe_results = await asyncio.gather(*[probe(t) for t in link_targets])
            for tgt, code in probe_results:
                ctx.link_status[tgt] = code

        # Pages already fetched: also record their statuses for completeness
        for p in pages:
            if p.status_code:
                ctx.link_status[p.final_url or p.url] = p.status_code

    return pages, ctx
