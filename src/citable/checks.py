"""The 10 v0.1.0 checks. Each function takes (pages, ctx) and returns one or more
CheckResult objects. Built with anti-false-positive guardrails baked in.

v0.2.0 will split these into a checks/ package with per-category modules.
"""

from __future__ import annotations

import re
from statistics import median
from urllib.parse import urlparse

from citable.models import Category, CheckResult, Page, Severity, SiteContext, Verdict

AI_BOTS = [
    "gptbot",
    "claudebot",
    "perplexitybot",
    "oai-searchbot",
    "google-extended",
    "applebot-extended",
]


# ---------- C-01 + C-02: Crawlability ----------


def check_robots_and_ai_bots(pages: list[Page], ctx: SiteContext) -> list[CheckResult]:
    """C-01: robots.txt exists and parseable. C-02: AI bot allowlist."""
    results: list[CheckResult] = []

    # C-01
    if ctx.robots_status == 200 and ctx.robots_txt.strip():
        results.append(CheckResult(
            check_id="C-01",
            category=Category.CRAWLABILITY,
            name="robots.txt present",
            verdict=Verdict.PASS,
            severity=Severity.P2,
            message=f"robots.txt found at {ctx.domain}/robots.txt",
            evidence_url=f"{ctx.domain}/robots.txt",
        ))
    elif ctx.robots_status == 0 or ctx.robots_status == 404:
        results.append(CheckResult(
            check_id="C-01",
            category=Category.CRAWLABILITY,
            name="robots.txt present",
            verdict=Verdict.WARN,
            severity=Severity.P2,
            message="robots.txt is missing. Crawlers will assume everything is allowed, but you also lose the chance to welcome AI bots explicitly.",
            fix_text="Create /robots.txt with at minimum: `User-agent: *` `Allow: /` `Sitemap: https://your-domain/sitemap.xml`. Then add explicit Allow directives for GPTBot, ClaudeBot, PerplexityBot, OAI-SearchBot, Google-Extended, Applebot-Extended.",
            evidence_url=f"{ctx.domain}/robots.txt",
        ))
    else:
        results.append(CheckResult(
            check_id="C-01",
            category=Category.CRAWLABILITY,
            name="robots.txt present",
            verdict=Verdict.FAIL,
            severity=Severity.P0,
            message=f"robots.txt returned HTTP {ctx.robots_status}. Crawlers cannot reach it.",
            fix_text="Investigate the server response. A 403 or 500 on /robots.txt will lock out AI crawlers that rely on it.",
            evidence_url=f"{ctx.domain}/robots.txt",
        ))

    # C-02
    robots = ctx.robots_txt.lower()
    explicit_disallow: list[str] = []
    explicit_allow: list[str] = []
    has_wildcard_group = False
    wildcard_blocks_all = False

    if robots:
        # Walk user-agent groups. `User-agent:` separator may have spaces/tabs.
        groups = re.split(r"(?im)^user-agent\s*:\s*", robots)
        for group in groups:
            ua_line, _, body = group.partition("\n")
            ua = ua_line.strip().lower()
            if not ua:
                continue
            if ua == "*":
                has_wildcard_group = True
                if re.search(r"^\s*disallow\s*:\s*/\s*$", body, re.I | re.M):
                    wildcard_blocks_all = True
                continue
            for bot in AI_BOTS:
                if ua == bot:
                    if re.search(r"^\s*disallow\s*:\s*/\s*$", body, re.I | re.M):
                        explicit_disallow.append(bot)
                    elif re.search(r"^\s*allow\s*:", body, re.I | re.M):
                        explicit_allow.append(bot)

    has_named_ai_bot = bool(explicit_disallow or explicit_allow)
    has_wildcard_only = has_wildcard_group and not has_named_ai_bot

    # Wildcard blocks all AND no AI bot has an explicit exception → real failure
    if wildcard_blocks_all and not explicit_allow:
        results.append(CheckResult(
            check_id="C-02",
            category=Category.CRAWLABILITY,
            name="AI bot allowlist",
            verdict=Verdict.FAIL,
            severity=Severity.P0,
            message="robots.txt blocks all crawlers via `User-agent: *` / `Disallow: /`. No AI bot has an explicit exception, so GPTBot, ClaudeBot, PerplexityBot and others are blocked too.",
            fix_text="Either change the wildcard to `Allow: /` or add an explicit `User-agent: GPTBot` (and the other 5 AI bots) block with `Allow: /` so they have an exception to the wildcard ban.",
            evidence_url=f"{ctx.domain}/robots.txt",
        ))
        return results

    if explicit_disallow:
        bots_str = ", ".join(sorted(set(explicit_disallow)))
        results.append(CheckResult(
            check_id="C-02",
            category=Category.CRAWLABILITY,
            name="AI bot allowlist",
            verdict=Verdict.FAIL,
            severity=Severity.P0,
            message=f"AI bots explicitly blocked: {bots_str}. These crawlers cannot index the site for AI search results.",
            fix_text="In /robots.txt, remove the `Disallow: /` lines under the named AI user-agents. Replace with `Allow: /` (or remove the explicit group to fall through to the wildcard).",
            evidence_url=f"{ctx.domain}/robots.txt",
        ))
    elif explicit_allow:
        results.append(CheckResult(
            check_id="C-02",
            category=Category.CRAWLABILITY,
            name="AI bot allowlist",
            verdict=Verdict.PASS,
            severity=Severity.P0,
            message=f"AI bots explicitly allowed: {len(set(explicit_allow))} bot(s) named.",
            evidence_url=f"{ctx.domain}/robots.txt",
        ))
    elif has_wildcard_only:
        results.append(CheckResult(
            check_id="C-02",
            category=Category.CRAWLABILITY,
            name="AI bot allowlist",
            verdict=Verdict.UNVERIFIED,
            severity=Severity.P1,
            message="No AI bots explicitly named in robots.txt. Wildcard `User-agent: *` rules apply, which is permissive by default but not a positive signal.",
            fix_text="Add explicit User-agent blocks for GPTBot, ClaudeBot, PerplexityBot, OAI-SearchBot, Google-Extended, Applebot-Extended with `Allow: /` to confirm intent.",
            evidence_url=f"{ctx.domain}/robots.txt",
        ))
    else:
        results.append(CheckResult(
            check_id="C-02",
            category=Category.CRAWLABILITY,
            name="AI bot allowlist",
            verdict=Verdict.UNVERIFIED,
            severity=Severity.P1,
            message="robots.txt absent or empty. Cannot verify AI bot policy.",
            fix_text="Create robots.txt and explicitly allow the 6 major AI crawlers (see C-01 fix).",
            evidence_url=f"{ctx.domain}/robots.txt",
        ))

    return results


# ---------- C-03: sitemap.xml ----------


def check_sitemap(pages: list[Page], ctx: SiteContext) -> list[CheckResult]:
    if ctx.sitemap_status == 200 and ctx.sitemap_urls:
        return [CheckResult(
            check_id="C-03",
            category=Category.CRAWLABILITY,
            name="sitemap.xml present",
            verdict=Verdict.PASS,
            severity=Severity.P1,
            message=f"sitemap.xml found with {len(ctx.sitemap_urls)} URLs.",
            evidence_url=ctx.sitemap_url,
        )]
    if ctx.sitemap_status == 200 and not ctx.sitemap_urls:
        return [CheckResult(
            check_id="C-03",
            category=Category.CRAWLABILITY,
            name="sitemap.xml present",
            verdict=Verdict.WARN,
            severity=Severity.P1,
            message="sitemap.xml returned 200 but contained no URLs we could parse.",
            fix_text="Validate the sitemap with `xmllint` or https://www.xml-sitemaps.com/validate-xml-sitemap.html. Common causes: empty sitemap-index, namespace issues, or escaping problems.",
            evidence_url=ctx.sitemap_url or f"{ctx.domain}/sitemap.xml",
        )]
    # Small sites can skip sitemap; warn instead of fail
    if len(pages) < 20:
        return [CheckResult(
            check_id="C-03",
            category=Category.CRAWLABILITY,
            name="sitemap.xml present",
            verdict=Verdict.WARN,
            severity=Severity.P2,
            message="sitemap.xml not found. For small sites this is optional, but it helps AI crawlers discover pages reliably.",
            fix_text="Generate a sitemap at /sitemap.xml listing every canonical URL. Reference it from robots.txt with `Sitemap: https://your-domain/sitemap.xml`.",
            evidence_url=f"{ctx.domain}/sitemap.xml",
        )]
    return [CheckResult(
        check_id="C-03",
        category=Category.CRAWLABILITY,
        name="sitemap.xml present",
        verdict=Verdict.FAIL,
        severity=Severity.P1,
        message="sitemap.xml not found on a site with 20+ pages. AI crawlers will rely on internal link discovery, which is slower and less reliable.",
        fix_text="Generate /sitemap.xml listing every canonical URL, include lastmod dates, and reference it from robots.txt.",
        evidence_url=f"{ctx.domain}/sitemap.xml",
    )]


# ---------- C-04: render time ----------


def check_render_time(pages: list[Page], ctx: SiteContext) -> list[CheckResult]:
    valid = [p for p in pages if p.status_code == 200 and p.render_time_ms > 0]
    if len(valid) < 3:
        return [CheckResult(
            check_id="C-04",
            category=Category.CRAWLABILITY,
            name="Render time (Googlebot UA, median)",
            verdict=Verdict.UNVERIFIED,
            severity=Severity.P2,
            message="Not enough successful page fetches to compute a reliable median.",
        )]
    med_ms = int(median(p.render_time_ms for p in valid))
    if med_ms < 2000:
        return [CheckResult(
            check_id="C-04",
            category=Category.CRAWLABILITY,
            name="Render time (Googlebot UA, median)",
            verdict=Verdict.PASS,
            severity=Severity.P2,
            message=f"Median render time {med_ms}ms across {len(valid)} pages. Fast.",
        )]
    if med_ms < 5000:
        return [CheckResult(
            check_id="C-04",
            category=Category.CRAWLABILITY,
            name="Render time (Googlebot UA, median)",
            verdict=Verdict.WARN,
            severity=Severity.P1,
            message=f"Median render time {med_ms}ms. Above 2s slows AI crawlers and may cap how many pages they ingest per visit.",
            fix_text="Profile the slow pages with PageSpeed Insights. Common wins: defer JS, lazy-load images, ship critical CSS inline, use HTTP/2 or HTTP/3 with a CDN.",
        )]
    return [CheckResult(
        check_id="C-04",
        category=Category.CRAWLABILITY,
        name="Render time (Googlebot UA, median)",
        verdict=Verdict.FAIL,
        severity=Severity.P0,
        message=f"Median render time {med_ms}ms is slow enough that AI crawlers may skip pages or cap your crawl budget.",
        fix_text="Audit page weight: aim for <500KB compressed HTML, deferred JS, image lazy-load, server-side rendering for hero content. CDN with edge cache cuts this fast.",
    )]


# ---------- C-05: canonical ----------


def _normalize_url(url: str) -> str:
    """Normalize URL for canonical comparison. Treat empty path and `/` as
    equivalent (root). Strip trailing slash on non-root paths. Drop fragment.
    """
    if not url:
        return ""
    p = urlparse(url)
    path = p.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return f"{p.scheme}://{p.netloc.lower()}{path}"


def check_canonical(pages: list[Page], ctx: SiteContext) -> list[CheckResult]:
    valid = [p for p in pages if p.status_code == 200]
    if not valid:
        return [CheckResult(
            check_id="C-05",
            category=Category.ENTITY,
            name="Canonical URL self-referential",
            verdict=Verdict.UNVERIFIED,
            severity=Severity.P1,
            message="No successful page fetches to check canonicals on.",
        )]

    missing = []
    cross_domain = []
    mismatch = []
    self_referential = 0

    for p in valid:
        if not p.canonical:
            missing.append(p.final_url)
            continue
        canon_host = urlparse(p.canonical).netloc.lower()
        page_host = urlparse(p.final_url).netloc.lower()
        if canon_host and canon_host != page_host:
            cross_domain.append((p.final_url, p.canonical))
        elif _normalize_url(p.canonical) == _normalize_url(p.final_url):
            self_referential += 1
        else:
            mismatch.append((p.final_url, p.canonical))

    if cross_domain:
        u, c = cross_domain[0]
        return [CheckResult(
            check_id="C-05",
            category=Category.ENTITY,
            name="Canonical URL self-referential",
            verdict=Verdict.FAIL,
            severity=Severity.P0,
            message=f"{len(cross_domain)} page(s) point canonical to a different domain. AI engines will dedupe to the canonical, not your site.",
            fix_text="Audit cross-domain canonicals. Common cause: copied content from a staging or partner site. Either remove the canonical or point it to the matching URL on this domain.",
            evidence_url=u,
            evidence_snippet=f"canonical={c}",
            pages_affected=len(cross_domain),
            total_pages=len(valid),
        )]

    pct_ok = self_referential / max(len(valid), 1)
    if missing and pct_ok > 0.7:
        return [CheckResult(
            check_id="C-05",
            category=Category.ENTITY,
            name="Canonical URL self-referential",
            verdict=Verdict.WARN,
            severity=Severity.P1,
            message=f"{len(missing)} of {len(valid)} pages lack a canonical link.",
            fix_text="Add `<link rel=\"canonical\" href=\"https://your-domain/this-page\">` to the <head> of every page. Self-referential canonicals tell crawlers which URL is the master copy.",
            evidence_url=missing[0],
            pages_affected=len(missing),
            total_pages=len(valid),
        )]
    if missing:
        return [CheckResult(
            check_id="C-05",
            category=Category.ENTITY,
            name="Canonical URL self-referential",
            verdict=Verdict.FAIL,
            severity=Severity.P0,
            message=f"{len(missing)} of {len(valid)} pages lack a canonical link.",
            fix_text="Add `<link rel=\"canonical\">` site-wide. In React/Vite, put it in your Helmet or head manager. In WordPress, use Yoast or Rank Math.",
            evidence_url=missing[0] if missing else "",
            pages_affected=len(missing),
            total_pages=len(valid),
        )]
    if mismatch:
        u, c = mismatch[0]
        return [CheckResult(
            check_id="C-05",
            category=Category.ENTITY,
            name="Canonical URL self-referential",
            verdict=Verdict.WARN,
            severity=Severity.P1,
            message=f"{len(mismatch)} page(s) canonical differs from final URL (trailing slash, scheme, or path mismatch).",
            fix_text="Make canonical match the live URL exactly after redirects. Pick one convention (trailing slash or no trailing slash) and enforce it everywhere.",
            evidence_url=u,
            evidence_snippet=f"page={u} canonical={c}",
            pages_affected=len(mismatch),
            total_pages=len(valid),
        )]
    return [CheckResult(
        check_id="C-05",
        category=Category.ENTITY,
        name="Canonical URL self-referential",
        verdict=Verdict.PASS,
        severity=Severity.P1,
        message=f"All {len(valid)} pages have self-referential canonicals.",
        total_pages=len(valid),
    )]


# ---------- C-06: OG basics ----------


def check_og_basics(pages: list[Page], ctx: SiteContext) -> list[CheckResult]:
    valid = [p for p in pages if p.status_code == 200]
    if not valid:
        return [CheckResult(
            check_id="C-06",
            category=Category.ENTITY,
            name="OG basics (og:title, og:description, og:image, og:url)",
            verdict=Verdict.UNVERIFIED,
            severity=Severity.P1,
            message="No successful page fetches.",
        )]
    fail_pages = 0
    warn_pages = 0
    for p in valid:
        present = sum(1 for k in ("og:title", "og:description", "og:image", "og:url") if p.og.get(k))
        # og:description allowed to fall back to meta description
        if not p.og.get("og:description") and p.meta_description:
            present += 1
        if present <= 1:
            fail_pages += 1
        elif present < 4:
            warn_pages += 1
    if fail_pages > len(valid) * 0.5:
        return [CheckResult(
            check_id="C-06",
            category=Category.ENTITY,
            name="OG basics (og:title, og:description, og:image, og:url)",
            verdict=Verdict.FAIL,
            severity=Severity.P1,
            message=f"{fail_pages} of {len(valid)} pages have fewer than 2 OG tags. AI crawlers and social platforms cannot generate clean cards.",
            fix_text="Add og:title, og:description, og:image, og:url to every page. og:image should be 1200x630 PNG/JPG. og:description can mirror meta description.",
            pages_affected=fail_pages,
            total_pages=len(valid),
        )]
    if fail_pages or warn_pages:
        return [CheckResult(
            check_id="C-06",
            category=Category.ENTITY,
            name="OG basics (og:title, og:description, og:image, og:url)",
            verdict=Verdict.WARN,
            severity=Severity.P2,
            message=f"{fail_pages + warn_pages} of {len(valid)} pages missing one or more OG tags.",
            fix_text="Ensure all 4 OG tags are present site-wide. Use og:image at 1200x630.",
            pages_affected=fail_pages + warn_pages,
            total_pages=len(valid),
        )]
    return [CheckResult(
        check_id="C-06",
        category=Category.ENTITY,
        name="OG basics (og:title, og:description, og:image, og:url)",
        verdict=Verdict.PASS,
        severity=Severity.P2,
        message=f"All {len(valid)} pages have complete OG tags.",
        total_pages=len(valid),
    )]


# ---------- C-09: meta description ----------


def check_meta_description(pages: list[Page], ctx: SiteContext) -> list[CheckResult]:
    valid = [p for p in pages if p.status_code == 200]
    if not valid:
        return [CheckResult(
            check_id="C-09",
            category=Category.CONTENT,
            name="Meta description present, 80-160 chars",
            verdict=Verdict.UNVERIFIED,
            severity=Severity.P1,
            message="No successful page fetches.",
        )]
    missing = sum(1 for p in valid if not p.meta_description)
    out_of_range = sum(
        1 for p in valid
        if p.meta_description and (len(p.meta_description) < 80 or len(p.meta_description) > 160)
    )
    if missing > len(valid) * 0.2:
        # Pick an example page for the action list
        ex = next((p for p in valid if not p.meta_description), None)
        return [CheckResult(
            check_id="C-09",
            category=Category.CONTENT,
            name="Meta description present, 80-160 chars",
            verdict=Verdict.FAIL,
            severity=Severity.P1,
            message=f"{missing} of {len(valid)} pages missing meta description.",
            fix_text="Write a 120-150 char meta description for every page. Lead with the buyer's question or pain. Avoid filler. Example: `Mid-market companies lose 20+ hours a week to manual reporting. Here is what a 4-week AI install looks like.`",
            evidence_url=ex.final_url if ex else "",
            pages_affected=missing,
            total_pages=len(valid),
        )]
    if missing or out_of_range:
        return [CheckResult(
            check_id="C-09",
            category=Category.CONTENT,
            name="Meta description present, 80-160 chars",
            verdict=Verdict.WARN,
            severity=Severity.P2,
            message=f"{missing} missing, {out_of_range} out of 80-160 char range.",
            fix_text="Audit short (<80) and long (>160) meta descriptions. Short ones leave Google room to rewrite. Long ones get truncated mid-sentence.",
            pages_affected=missing + out_of_range,
            total_pages=len(valid),
        )]
    return [CheckResult(
        check_id="C-09",
        category=Category.CONTENT,
        name="Meta description present, 80-160 chars",
        verdict=Verdict.PASS,
        severity=Severity.P2,
        message=f"All {len(valid)} pages have meta descriptions in the 80-160 char range.",
        total_pages=len(valid),
    )]


# ---------- C-10: title length ----------


def check_title_length(pages: list[Page], ctx: SiteContext) -> list[CheckResult]:
    valid = [p for p in pages if p.status_code == 200]
    if not valid:
        return [CheckResult(
            check_id="C-10",
            category=Category.CONTENT,
            name="Title length 30-65 chars",
            verdict=Verdict.UNVERIFIED,
            severity=Severity.P1,
            message="No successful page fetches.",
        )]
    missing = sum(1 for p in valid if not p.title)
    too_long = sum(1 for p in valid if p.title and len(p.title) > 80)
    too_short = sum(1 for p in valid if p.title and len(p.title) < 20)
    if missing + too_long + too_short > len(valid) * 0.3:
        ex = next((p for p in valid if not p.title or len(p.title) > 80 or len(p.title) < 20), None)
        return [CheckResult(
            check_id="C-10",
            category=Category.CONTENT,
            name="Title length 30-65 chars",
            verdict=Verdict.FAIL,
            severity=Severity.P1,
            message=f"{missing} missing titles, {too_short} under 20 chars, {too_long} over 80 chars.",
            fix_text="Rewrite titles to 30-65 chars. Lead with the keyword or buyer phrase, then brand. Example: `AI Visibility Audit · Work-Smart.ai`.",
            evidence_url=ex.final_url if ex else "",
            pages_affected=missing + too_long + too_short,
            total_pages=len(valid),
        )]
    if missing + too_long + too_short:
        return [CheckResult(
            check_id="C-10",
            category=Category.CONTENT,
            name="Title length 30-65 chars",
            verdict=Verdict.WARN,
            severity=Severity.P2,
            message=f"{too_short} title(s) under 20 chars, {too_long} over 80 chars, {missing} missing. Out of 30-65 char range hurts how titles render in AI engine snippets and search results.",
            fix_text="Rewrite affected titles into the 30-65 char range. Lead with the keyword or buyer phrase, then brand. Example: `Wealth Enterprise Governance: Why It Matters | WE Family Offices`. Check each title against the Per-Page Detail sheet for which pages need work.",
            pages_affected=missing + too_long + too_short,
            total_pages=len(valid),
        )]
    return [CheckResult(
        check_id="C-10",
        category=Category.CONTENT,
        name="Title length 30-65 chars",
        verdict=Verdict.PASS,
        severity=Severity.P2,
        message=f"All {len(valid)} titles within range.",
        total_pages=len(valid),
    )]


# ---------- C-11: H1 ----------


def check_h1(pages: list[Page], ctx: SiteContext) -> list[CheckResult]:
    """C-11 thresholds (v0.2.2): percentage-based, consistent with C-09/C-10.

    - 0 issues → PASS
    - 0 < issues ≤ 10% of pages → WARN (specific page(s) listed)
    - > 10% → FAIL (site-wide structural issue)

    Previous logic FAILed on any single missing H1, which gave equal weight
    to a 1-page issue and a 30-page issue. That collapsed the entire Content
    Structure category to F on small infractions.
    """
    valid = [p for p in pages if p.status_code == 200]
    if not valid:
        return [CheckResult(
            check_id="C-11",
            category=Category.CONTENT,
            name="H1 present and unique",
            verdict=Verdict.UNVERIFIED,
            severity=Severity.P1,
            message="No successful page fetches.",
        )]
    no_h1 = sum(1 for p in valid if not p.h1_texts)
    multi_h1 = sum(1 for p in valid if len(p.h1_texts) > 1)
    h1_values = [p.h1_texts[0] for p in valid if p.h1_texts]
    dup_count = len(h1_values) - len(set(h1_values))

    issues = no_h1 + multi_h1
    issue_pct = (issues / len(valid)) * 100 if valid else 0
    ex = next((p for p in valid if not p.h1_texts or len(p.h1_texts) > 1), None)

    # Site-wide structural failure (>10% of pages affected)
    if issue_pct > 10:
        return [CheckResult(
            check_id="C-11",
            category=Category.CONTENT,
            name="H1 present and unique",
            verdict=Verdict.FAIL,
            severity=Severity.P1,
            message=f"{no_h1} pages missing H1, {multi_h1} pages with multiple H1s. {issue_pct:.0f}% of pages affected.",
            fix_text="Audit and fix the H1 on each flagged page. Each page should have exactly one H1 that describes the page's topic. Multiple or missing H1s confuse AI crawlers.",
            evidence_url=ex.final_url if ex else "",
            pages_affected=issues,
            total_pages=len(valid),
        )]

    # Localized issue (1-10% of pages) — warn with the specific page listed
    if issues > 0:
        return [CheckResult(
            check_id="C-11",
            category=Category.CONTENT,
            name="H1 present and unique",
            verdict=Verdict.WARN,
            severity=Severity.P2,
            message=f"{issues} of {len(valid)} pages have H1 issues ({issue_pct:.0f}%). Specific page(s) listed in Per-Page Detail.",
            fix_text=f"Fix the H1 on the {issues} flagged page(s). Each page should have exactly one H1 that describes that page's topic.",
            evidence_url=ex.final_url if ex else "",
            pages_affected=issues,
            total_pages=len(valid),
        )]

    # Duplicate H1 text (separate signal — many pages with same H1 text)
    if dup_count > len(h1_values) * 0.15:
        return [CheckResult(
            check_id="C-11",
            category=Category.CONTENT,
            name="H1 present and unique",
            verdict=Verdict.WARN,
            severity=Severity.P2,
            message=f"{dup_count} duplicate H1s across {len(h1_values)} pages.",
            fix_text="Rewrite duplicate H1s. Each page should have a unique H1 that describes the unique content of that page.",
            pages_affected=dup_count,
            total_pages=len(valid),
        )]
    return [CheckResult(
        check_id="C-11",
        category=Category.CONTENT,
        name="H1 present and unique",
        verdict=Verdict.PASS,
        severity=Severity.P2,
        message=f"All {len(valid)} pages have a unique H1.",
        total_pages=len(valid),
    )]


# ---------- C-13: FAQPage schema ----------

QUESTION_HEADING_RE = re.compile(r"\?\s*$")


def _has_schema_type(page: Page, type_name: str) -> bool:
    for block in page.schema_blocks:
        if not isinstance(block, dict):
            continue
        t = block.get("@type")
        if isinstance(t, str) and t.lower() == type_name.lower():
            return True
        if isinstance(t, list) and any(isinstance(x, str) and x.lower() == type_name.lower() for x in t):
            return True
        # Also check @graph entries
        graph = block.get("@graph")
        if isinstance(graph, list):
            for g in graph:
                if isinstance(g, dict):
                    gt = g.get("@type")
                    if isinstance(gt, str) and gt.lower() == type_name.lower():
                        return True
                    if isinstance(gt, list) and any(isinstance(x, str) and x.lower() == type_name.lower() for x in gt):
                        return True
    return False


MIN_QA_QUESTIONS = 2
"""A single rhetorical `?` H2 is usually a CTA, not a FAQ. Require at least 2."""


def _is_qa_content(page: Page) -> bool:
    """A page has Q&A content if it has 2+ question-style H2s. We do not have
    paragraph-after-H2 in v0.1.1 (would require richer DOM tracking), so we
    rely on the question count threshold as the false-positive shield.
    """
    q_h2s = [h for h in page.h2_texts if QUESTION_HEADING_RE.search(h)]
    return len(q_h2s) >= MIN_QA_QUESTIONS


def check_faqpage_schema(pages: list[Page], ctx: SiteContext) -> list[CheckResult]:
    valid = [p for p in pages if p.status_code == 200]
    if not valid:
        return [CheckResult(
            check_id="C-13",
            category=Category.SCHEMA,
            name="FAQPage schema present where applicable",
            verdict=Verdict.UNVERIFIED,
            severity=Severity.P1,
            message="No successful page fetches.",
        )]

    has_qa_content: list[Page] = []
    has_faq_schema = 0
    qa_without_schema: list[Page] = []

    for p in valid:
        looks_qa = _is_qa_content(p)
        has_schema = _has_schema_type(p, "FAQPage")
        if looks_qa:
            has_qa_content.append(p)
            if has_schema:
                has_faq_schema += 1
            else:
                qa_without_schema.append(p)
        elif has_schema:
            has_faq_schema += 1

    if not has_qa_content and has_faq_schema == 0:
        return [CheckResult(
            check_id="C-13",
            category=Category.SCHEMA,
            name="FAQPage schema present where applicable",
            verdict=Verdict.NA,
            severity=Severity.INFO,
            message="No Q&A content detected on crawled pages. FAQPage schema not applicable.",
        )]
    if has_qa_content and qa_without_schema:
        ex = qa_without_schema[0]
        return [CheckResult(
            check_id="C-13",
            category=Category.SCHEMA,
            name="FAQPage schema present where applicable",
            verdict=Verdict.WARN,
            severity=Severity.P1,
            message=f"{len(qa_without_schema)} of {len(has_qa_content)} pages with 2+ question-style headings lack FAQPage schema. Adding it can raise Perplexity / ChatGPT inclusion rate.",
            fix_text='Wrap each Q&A block in JSON-LD: <script type="application/ld+json">{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":"...","acceptedAnswer":{"@type":"Answer","text":"..."}}]}</script>. Note: citable detects Q&A content heuristically from H2 text. Verify the page actually has FAQ-style content before adding schema.',
            evidence_url=ex.final_url,
            pages_affected=len(qa_without_schema),
            total_pages=len(has_qa_content),
        )]
    return [CheckResult(
        check_id="C-13",
        category=Category.SCHEMA,
        name="FAQPage schema present where applicable",
        verdict=Verdict.PASS,
        severity=Severity.P1,
        message=f"FAQPage schema detected on {has_faq_schema} page(s).",
        total_pages=len(valid),
    )]


# ---------- C-15: Organization schema ----------


ORG_TYPES = {
    "organization",
    "localbusiness",
    "professionalservice",
    "corporation",
    "educationalorganization",
    "governmentorganization",
    "ngo",
    "performinggroup",
    "sportsorganization",
    "medicalorganization",
    "newsmediaorganization",
    "consortium",
    "library",
    "fundingscheme",
}
"""Schema.org Organization subtypes we accept for C-15."""


def _has_org_schema(page: Page) -> str | None:
    """Return the matching Organization subtype found, or None."""
    for block in page.schema_blocks:
        if not isinstance(block, dict):
            continue
        candidates = [block]
        if isinstance(block.get("@graph"), list):
            candidates.extend([c for c in block["@graph"] if isinstance(c, dict)])
        for c in candidates:
            t = c.get("@type")
            if isinstance(t, str) and t.lower() in ORG_TYPES:
                return t
            if isinstance(t, list):
                for x in t:
                    if isinstance(x, str) and x.lower() in ORG_TYPES:
                        return x
    return None


def check_organization_schema(pages: list[Page], ctx: SiteContext) -> list[CheckResult]:
    # Entity identity is site-wide. When scoped to a path prefix, citable
    # still evaluates the root homepage's Organization schema (stored on
    # ctx.root_page) rather than the section landing page.
    homepage = ctx.root_page
    if homepage is None:
        homepage = next(
            (p for p in pages if _normalize_url(p.final_url) == _normalize_url(ctx.domain)),
            None,
        )
    if homepage is None and pages:
        homepage = pages[0]
    if not homepage or homepage.status_code != 200:
        return [CheckResult(
            check_id="C-15",
            category=Category.SCHEMA,
            name="Organization schema on homepage",
            verdict=Verdict.UNVERIFIED,
            severity=Severity.P0,
            message="Homepage did not return 200.",
        )]

    matched_type = _has_org_schema(homepage)
    if not matched_type:
        return [CheckResult(
            check_id="C-15",
            category=Category.SCHEMA,
            name="Organization schema on homepage",
            verdict=Verdict.FAIL,
            severity=Severity.P0,
            message="No Organization schema on homepage (any subtype: Organization, LocalBusiness, ProfessionalService, Corporation, NGO, etc). AI engines have no canonical entity to anchor to.",
            fix_text='Add Organization JSON-LD to homepage: <script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"...","url":"...","logo":"...","sameAs":["LinkedIn URL","X URL","Wikidata URL"]}</script>. sameAs is what AI engines use to dedupe entities.',
            evidence_url=homepage.final_url,
            total_pages=1,
        )]

    # Walk all Org-type blocks and check required fields
    required = {"name", "url", "logo", "sameAs"}
    best_org: dict = {}
    for block in homepage.schema_blocks:
        if not isinstance(block, dict):
            continue
        candidates = [block]
        if isinstance(block.get("@graph"), list):
            candidates = block["@graph"]
        for c in candidates:
            if not isinstance(c, dict):
                continue
            t = c.get("@type")
            types = []
            if isinstance(t, str):
                types = [t]
            elif isinstance(t, list):
                types = [x for x in t if isinstance(x, str)]
            if any(x.lower() in ORG_TYPES for x in types):
                present = {k for k in required if c.get(k)}
                if len(present) > len(best_org):
                    best_org = present

    missing = required - set(best_org)
    if not missing:
        return [CheckResult(
            check_id="C-15",
            category=Category.SCHEMA,
            name="Organization schema on homepage",
            verdict=Verdict.PASS,
            severity=Severity.P0,
            message="Organization schema present with name, url, logo, sameAs.",
            evidence_url=homepage.final_url,
            total_pages=1,
        )]
    return [CheckResult(
        check_id="C-15",
        category=Category.SCHEMA,
        name="Organization schema on homepage",
        verdict=Verdict.WARN,
        severity=Severity.P1,
        message=f"Organization schema present but missing fields: {', '.join(sorted(missing))}.",
        fix_text=f"Add missing fields to your Organization JSON-LD: {', '.join(sorted(missing))}. sameAs in particular should list LinkedIn, X, GitHub, Wikidata, and any verified profiles.",
        evidence_url=homepage.final_url,
        total_pages=1,
    )]


# ---------- C-19: HSTS ----------


def check_hsts(pages: list[Page], ctx: SiteContext) -> list[CheckResult]:
    sts = ctx.homepage_headers.get("strict-transport-security", "").lower()
    if not sts:
        return [CheckResult(
            check_id="C-19",
            category=Category.AUTHORITY,
            name="HSTS header present",
            verdict=Verdict.FAIL,
            severity=Severity.P1,
            message="No Strict-Transport-Security header. AI crawlers and browsers may treat the site as lower-trust.",
            fix_text="Add the header at the edge (Cloudflare, Vercel, Nginx): `Strict-Transport-Security: max-age=31536000; includeSubDomains`. On Vercel, add to vercel.json under `headers`.",
            evidence_url=ctx.domain,
        )]
    max_age_match = re.search(r"max-age\s*=\s*(\d+)", sts)
    if not max_age_match:
        return [CheckResult(
            check_id="C-19",
            category=Category.AUTHORITY,
            name="HSTS header present",
            verdict=Verdict.WARN,
            severity=Severity.P2,
            message=f"HSTS header present but unparseable: {sts}",
            fix_text="Fix the HSTS header format. Valid example: `Strict-Transport-Security: max-age=31536000; includeSubDomains`.",
            evidence_url=ctx.domain,
        )]
    max_age = int(max_age_match.group(1))
    if max_age >= 15552000:  # 180 days
        return [CheckResult(
            check_id="C-19",
            category=Category.AUTHORITY,
            name="HSTS header present",
            verdict=Verdict.PASS,
            severity=Severity.P2,
            message=f"HSTS present with max-age={max_age}.",
            evidence_url=ctx.domain,
        )]
    return [CheckResult(
        check_id="C-19",
        category=Category.AUTHORITY,
        name="HSTS header present",
        verdict=Verdict.WARN,
        severity=Severity.P2,
        message=f"HSTS present but max-age={max_age} is below 180 days.",
        fix_text="Increase max-age to at least 31536000 (1 year). Common production value: `max-age=63072000; includeSubDomains; preload`.",
        evidence_url=ctx.domain,
    )]


# ---------- C-22: Broken internal links ----------


def check_broken_internal_links(pages: list[Page], ctx: SiteContext) -> list[CheckResult]:
    """Detect internal links pointing at 4xx pages. Uses ctx.link_status
    populated during the crawl."""
    if not ctx.link_status:
        return [CheckResult(
            check_id="C-22",
            category=Category.INTERNAL_LINKS,
            name="Broken internal links",
            verdict=Verdict.NA,
            severity=Severity.INFO,
            message="No internal links discovered during crawl.",
        )]
    # Find broken targets (4xx). Ignore 0 (network error) and 3xx (followed).
    broken: list[tuple[str, str, int]] = []  # (source, target, status)
    seen_pairs: set[tuple[str, str]] = set()
    for src, links in ctx.link_graph.items():
        for target, _anchor in links:
            status = ctx.link_status.get(target, -1)
            if status >= 400 and status < 500:
                key = (src, target)
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                broken.append((src, target, status))

    if not broken:
        total_probed = sum(1 for s in ctx.link_status.values() if s >= 200)
        return [CheckResult(
            check_id="C-22",
            category=Category.INTERNAL_LINKS,
            name="Broken internal links",
            verdict=Verdict.PASS,
            severity=Severity.P0,
            message=f"No broken internal links detected across {total_probed} link targets probed.",
        )]
    ex = broken[0]
    return [CheckResult(
        check_id="C-22",
        category=Category.INTERNAL_LINKS,
        name="Broken internal links",
        verdict=Verdict.FAIL,
        severity=Severity.P0,
        message=f"{len(broken)} broken internal link(s) found. Example: {ex[1]} (HTTP {ex[2]}) linked from {ex[0]}.",
        fix_text="Fix or remove links to dead URLs. Broken internal links waste crawl budget and signal to AI engines that the site is poorly maintained. Use the Per-Page Detail sheet to find the source pages.",
        evidence_url=ex[0],
        evidence_snippet=f"links to {ex[1]} (HTTP {ex[2]})",
        pages_affected=len({src for src, _, _ in broken}),
        total_pages=len(pages),
    )]


# ---------- C-23: Anchor text quality ----------

GENERIC_ANCHORS = {
    "click here", "read more", "learn more", "see more", "find out more",
    "click", "here", "more", "details", "info", "view", "view more",
    "go", "open", "link", "this", "this link", "this page",
    "next", "prev", "previous", "back", "continue", "follow",
}


def check_anchor_text_quality(pages: list[Page], ctx: SiteContext) -> list[CheckResult]:
    """Count internal links with generic anchor text. AI engines weight anchor
    text as a topic signal. Generic anchors ('click here') waste that signal."""
    total = 0
    generic = 0
    examples: list[tuple[str, str]] = []  # (source, anchor)
    for src, links in ctx.link_graph.items():
        for _target, anchor in links:
            if not anchor:
                continue
            total += 1
            lower = anchor.strip().lower()
            if lower in GENERIC_ANCHORS:
                generic += 1
                if len(examples) < 5:
                    examples.append((src, anchor))

    if total < 20:
        return [CheckResult(
            check_id="C-23",
            category=Category.INTERNAL_LINKS,
            name="Anchor text quality",
            verdict=Verdict.NA,
            severity=Severity.INFO,
            message=f"Only {total} anchored internal links found. Not enough sample to evaluate.",
        )]

    pct = generic / total * 100
    if pct < 5:
        return [CheckResult(
            check_id="C-23",
            category=Category.INTERNAL_LINKS,
            name="Anchor text quality",
            verdict=Verdict.PASS,
            severity=Severity.P2,
            message=f"{pct:.1f}% generic anchors across {total} internal links. Strong topic signals.",
        )]
    if pct < 15:
        return [CheckResult(
            check_id="C-23",
            category=Category.INTERNAL_LINKS,
            name="Anchor text quality",
            verdict=Verdict.WARN,
            severity=Severity.P2,
            message=f"{pct:.1f}% of internal links use generic anchors like 'click here' or 'read more' ({generic} of {total}).",
            fix_text="Replace generic anchors with descriptive text containing the linked page's topic. `Read our AI visibility methodology` beats `Read more`. AI engines use anchor text as a topic signal.",
            pages_affected=len({s for s, _ in examples}),
            total_pages=len(pages),
        )]
    return [CheckResult(
        check_id="C-23",
        category=Category.INTERNAL_LINKS,
        name="Anchor text quality",
        verdict=Verdict.FAIL,
        severity=Severity.P1,
        message=f"{pct:.1f}% of internal links use generic anchors ({generic} of {total}). AI engines lose key topic signals when anchor text is non-descriptive.",
        fix_text="Audit and rewrite generic anchors site-wide. Each link's anchor text should describe what the linked page is about, using the buyer's vocabulary.",
        pages_affected=len({s for s, _ in examples}),
        total_pages=len(pages),
    )]


# ---------- C-24: Orphan pages ----------


def check_orphan_pages(pages: list[Page], ctx: SiteContext) -> list[CheckResult]:
    """A page in sitemap that is NOT linked from any crawled page is orphaned.
    Orphans signal weak information architecture and reduce AI citation odds."""
    if not ctx.sitemap_urls:
        return [CheckResult(
            check_id="C-24",
            category=Category.INTERNAL_LINKS,
            name="Orphan pages (in sitemap but unlinked)",
            verdict=Verdict.NA,
            severity=Severity.INFO,
            message="No sitemap.xml URLs to evaluate.",
        )]

    # Collect every link target across all crawled pages
    linked_targets: set[str] = set()
    for _src, links in ctx.link_graph.items():
        for target, _anchor in links:
            linked_targets.add(_normalize_url(target))

    # Add crawled URLs themselves to the linked set (a page that was crawled is
    # implicitly known about, even if not link-targeted)
    for p in pages:
        if p.status_code:
            linked_targets.add(_normalize_url(p.final_url or p.url))

    # Sitemap URLs that don't appear in linked_targets are orphans
    sitemap_set = {_normalize_url(u) for u in ctx.sitemap_urls}
    orphans = sitemap_set - linked_targets
    sitemap_count = len(sitemap_set)
    orphan_count = len(orphans)

    if sitemap_count < 5:
        return [CheckResult(
            check_id="C-24",
            category=Category.INTERNAL_LINKS,
            name="Orphan pages (in sitemap but unlinked)",
            verdict=Verdict.NA,
            severity=Severity.INFO,
            message=f"Sitemap has only {sitemap_count} URLs. Sample too small.",
        )]

    pct = orphan_count / sitemap_count * 100
    if pct < 10:
        return [CheckResult(
            check_id="C-24",
            category=Category.INTERNAL_LINKS,
            name="Orphan pages (in sitemap but unlinked)",
            verdict=Verdict.PASS,
            severity=Severity.P1,
            message=f"{orphan_count} of {sitemap_count} sitemap URLs not internally linked ({pct:.0f}%). Strong internal structure.",
        )]
    if pct < 30:
        ex = next(iter(orphans), "")
        return [CheckResult(
            check_id="C-24",
            category=Category.INTERNAL_LINKS,
            name="Orphan pages (in sitemap but unlinked)",
            verdict=Verdict.WARN,
            severity=Severity.P1,
            message=f"{orphan_count} of {sitemap_count} sitemap URLs are orphan (not linked from any crawled page, {pct:.0f}%). Note: citable only sampled the crawled pages, so true orphan rate may be lower if pages outside the crawl link to them.",
            fix_text=f"Investigate orphan pages. Example: {ex}. If they should be discoverable, add internal links from hub or category pages. If they should not, remove from sitemap.",
            evidence_url=ex,
            pages_affected=orphan_count,
            total_pages=sitemap_count,
        )]
    ex = next(iter(orphans), "")
    return [CheckResult(
        check_id="C-24",
        category=Category.INTERNAL_LINKS,
        name="Orphan pages (in sitemap but unlinked)",
        verdict=Verdict.FAIL,
        severity=Severity.P1,
        message=f"{orphan_count} of {sitemap_count} sitemap URLs are orphan ({pct:.0f}%). Either the sitemap is inflated or the site's internal architecture is broken.",
        fix_text=f"Decide which orphan pages are real content (link them from a hub) and which are stale (remove from sitemap). Example orphan: {ex}.",
        evidence_url=ex,
        pages_affected=orphan_count,
        total_pages=sitemap_count,
    )]


# ---------- Registry ----------

CHECK_FUNCTIONS = [
    check_robots_and_ai_bots,
    check_sitemap,
    check_render_time,
    check_canonical,
    check_og_basics,
    check_meta_description,
    check_title_length,
    check_h1,
    check_faqpage_schema,
    check_organization_schema,
    check_hsts,
    check_broken_internal_links,
    check_anchor_text_quality,
    check_orphan_pages,
]


def run_all_checks(pages: list[Page], ctx: SiteContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    for fn in CHECK_FUNCTIONS:
        try:
            results.extend(fn(pages, ctx))
        except Exception as e:  # noqa: BLE001
            results.append(CheckResult(
                check_id=fn.__name__,
                category=Category.CRAWLABILITY,
                name=fn.__name__,
                verdict=Verdict.UNVERIFIED,
                severity=Severity.INFO,
                message=f"Check raised an exception: {e}",
            ))
    return results
