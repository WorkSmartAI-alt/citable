# Changelog

## v0.2.3 (2026-05-20)

Pre-PyPI-publish prep.

### Changed

- **PyPI package name renamed from `citable` to `citable-cli`.** The `citable` name on PyPI belongs to an unrelated, abandoned (Feb 2021) Zenodo dataset loader. The CLI binary stays `citable`, the Python module stays `citable`, and the GitHub repo / brand stays `citable`. Only the PyPI distribution name changes. Install becomes `pipx install citable-cli`.

### Fixed

- Two em-dashes in README that slipped through the voice scan (lines 175 and 208). Replaced with a period and a colon respectively.

---

## v0.2.2 (2026-05-20)

Driven by a real question about scoring fairness: a 1-page H1 issue was dragging the entire Content Structure category to F. Audited the scoring math openly.

### Fixed

- **C-11 H1 check thresholds.** Was failing on ANY missing H1 (even 1 page out of 50 = 2% issue rate), while sibling checks C-09 and C-10 required >20-30% issue rate to fail. Made all three consistent: >10% to fail, 0-10% to warn, 0 to pass. Restored fairness to the Content Structure category score.

### Added

- **Score Breakdown sheet (Sheet 5)** showing the math behind every number: per-category weights, check counts, verdict tallies, score per category, contribution to overall. Auditable transparency.
- Pointer in the Action Plan sheet directing readers to Sheet 5 if they want to challenge the math.

### Calibration after fixes

- work-smart.ai: 100/A (unchanged, no Content Structure issues)
- WE Family /resources/: 58/C → 61/C (Content Structure moved F to D, more honest)
- example.com: 18/F (unchanged)

---

## v0.2.1 (2026-05-20)

Driven by a real "send this to the marketing agency" stress test. The technical sheets were unreadable for a non-developer. This release adds a first sheet designed for the agency audience and fixes a schema display bug.

### Added

- **New "Action Plan" sheet** (now first, opens by default). For each task: What to do · Who does it (Developer / DevOps / Designer / Copywriter / Marketer) · Effort estimate · Why it matters (plain English) · Pages affected. Tasks grouped into P1 "Fix this week", P2 "Fix this month", P3 "Nice to have". Plus a "What's already good" section. Plus a "How the rest of this file is organized" guide.
- `src/citable/briefing.py` with `CHECK_OWNER`, `CHECK_EFFORT`, `CHECK_WHY_AGENCY` maps. One per check ID.

### Fixed

- **Per-Page Detail "Schema Types: (none)" bug.** When a page used the WordPress / Yoast JSON-LD pattern (schemas nested in `@graph` arrays), citable was only reading top-level `@type` and missed everything. Now walks `@graph` recursively. WE Family pages now correctly display `Article, BreadcrumbList, Organization, Person, WebPage, WebSite` instead of `(none)`.
- **NA and UNVERIFIED verdicts no longer appear in Action Plan.** "No Q&A content detected" was being listed as a task to do, which made no sense. NA means "does not apply", not "todo."
- **C-10 title length now has actionable fix text.** Was empty / vague. Now: specific rewrite guidance with an example.

### Voice

- Replaced em-dashes in section titles with colons.
- Removed em-dashes from code comments for consistency with global voice rules.

---

## v0.2.0 (2026-05-20)

Two features, driven by a real WE Family audit that surfaced gaps in v0.1.3.

### Scope expansion

When you scope an audit to a path (e.g. `citable audit example.com/resources/`), citable now follows 1 hop of internal links beyond the prefix. The reason: sites often split hubs from content. WE Family Offices uses `/resources/` (plural) for the hub and `/resource/foo` (singular) for the articles. v0.1.3 audited the hub and stopped. v0.2.0 audits the hub AND the articles linked from it. The prefix becomes a starting point and a SCOPE FOR DISCOVERY, not a hard filter.

Tested on WE Family `/resources/`: v0.1.3 found 4 pages (pagination hub only). v0.2.0 finds 30 pages including the /resource/foo articles.

### New category: Internal Linkage

Three new checks under a new "Internal Linkage" category (18% weight in overall score). The link graph is built during the crawl: every internal anchor on every crawled page is captured with its anchor text.

- **C-22 Broken internal links (P0)** — probes link targets with HEAD (falling back to GET) and flags 4xx responses. Caps at 50 probes to keep audits fast. Filters out known framework patterns (`/cdn-cgi/`, `/wp-json/`, `/wp-admin/`, `/feed/`, `?_embed`, `?rsd`) that 4xx on direct fetch but are not real broken links.
- **C-23 Anchor text quality (P1/P2)** — counts generic anchors ("click here", "read more", "learn more", "view more", "continue", etc.). Fail if >15% generic, warn if 5-15%, pass under 5%. AI engines use anchor text as a topic signal.
- **C-24 Orphan pages (P1)** — compares sitemap.xml URLs against the link graph. URLs in the sitemap that nothing crawled links to are flagged as orphans. Caveat: only the crawled subset is examined, so true orphan rate may be lower if uncrawled pages link to them.

### Scoring changes

Category weights updated:

| Category | v0.1.3 | v0.2.0 |
|----------|--------|--------|
| Crawlability | 20% | 18% |
| Entity Clarity | 20% | 18% |
| Content Structure | 20% | 18% |
| Schema Markup | 20% | 18% |
| Authority Signals | 10% | 10% |
| Internal Linkage | (new) | 18% |
| AI-specific | 10% | 0% (no checks yet) |

### CLI changes

- `audit` argument renamed from `domain` to `target` (already documented in v0.1.3).
- No new flags.

### Calibration

WE Family `/resources/` (with 1-hop expansion, 30 pages crawled): 58/C. v0.1.3 was 60/C on the 4-page hub-only crawl. The new C correctly reflects the broader picture — content-level issues (H1 missing, meta description out of range) are now visible.

### Known limitations

- **Anchor text language detection.** GENERIC_ANCHORS only contains English phrases. Spanish equivalents ("haga clic", "leer más", "más información") not yet covered. v0.2.1 candidate.
- **Orphan check is crawl-bounded.** It compares sitemap against what was linked from the crawled subset. True orphan rate is best measured with `--pages 100+` on small sites or with the full sitemap dumped to disk.
- **Broken-link probe caps at 50 targets.** Sites with thousands of unique link targets won't probe all of them in v0.2.0.

---

## v0.1.3 (2026-05-20)

### Added

- **Path-prefix scoped crawling.** Pass a URL with a path to scope the audit. `citable audit example.com/blog/` audits `/blog/*` only. `citable audit example.com/resources/` audits `/resources/*` only. Useful for auditing a section of a large site without crawling the whole thing.
- **`citable doctor`** (from v0.1.1) and the new path-prefix feature work together: doctor diagnoses the environment, then run any scoped audit.

### Changed

- C-15 Organization schema now always evaluates the **root homepage** for entity identity, even when the audit is scoped to a path. Entity anchor is a site-wide concern, not a section concern. Without this, scoping to `/blog/` would falsely fail C-15 because blog pages do not carry Organization schema themselves.
- Output filename now includes a slug when scoped: `host_section-DATE.xlsx` instead of just `host-DATE.xlsx`. Audits of `/resources/` vs `/blog/` no longer overwrite each other.
- CLI argument renamed `domain` to `target` to reflect that it accepts paths now.

### New tests

- `test_normalize_target_whole_site`, `test_normalize_target_scoped`: parsing
- `test_matches_prefix_whole_site`, `test_matches_prefix_scoped`, `test_matches_prefix_handles_www_vs_apex`: filtering logic
- Total smoke tests: 18 passing.

### Operator notes

- When scoping to a path, citable reports only what is under that path. A site that organizes content under a different URL pattern (e.g. articles at `/resource/` singular but the hub at `/resources/` plural) will yield few pages on the hub-only audit. The audit output is correct — the URL was the wrong one to point at.

---

## v0.1.2 (2026-05-20)

Hotfix: three URLs in `RESOURCE_MAP` were hallucinated when the file was written without checking the live site. The audit output sent users to 404s.

### Fixed

- `/services/website-platform-build` (404) replaced with `/services/ai-foundation-build` for C-03, C-04, C-19.
- `/methodology/ai-visibility` (404) replaced with `/services/ai-visibility` for C-15.
- All 12 RESOURCE_MAP URLs verified live against work-smart.ai/sitemap.xml on 2026-05-20.

### Added

- `tests/test_live_urls.py` — pytest-marked `live` tests that fetch every URL in `RESOURCE_MAP` and assert HTTP 200. Run before every release with `pytest tests/ -m live`. This prevents the same class of bug from shipping silently again.
- Doc note at the top of `promo.py` requiring a live URL check when adding new entries.

---

## v0.1.1 (2026-05-20)

Self-audit patch. See `AUDIT-2026-05-20.md` for the full findings.

### Fixed (false positives)

- **C-13 FAQPage** no longer fires on single rhetorical-question H2s. Now requires 2+ question-style headings before treating a page as Q&A. Severity lowered P0 → P1. The work-smart.ai 90/A score was artificially low because the heuristic flagged CTAs like "Ready to go beyond the guides?" as missing FAQ schema.
- **C-15 Organization** now accepts 14 Organization subtypes (ProfessionalService, Corporation, NGO, etc.) instead of just Organization and LocalBusiness.
- **C-02 AI bot allowlist** wildcard detection now uses regex (handles `User-agent:*` with no space) and emits a P0 FAIL when wildcard blocks all crawlers without an AI bot exception (was silently UNVERIFIED).

### Fixed (crawl coverage)

- Sitemap-index handling now iterates sub-sitemaps until enough URLs are gathered (was stopping at first 5 sub-sitemaps).
- sitemap.xml.gz support: gzipped sitemaps are detected by `.gz` suffix and decompressed.
- Non-HTML URLs (PDF, image, asset files, .gz, .zip, etc.) are now filtered out of the crawl budget.
- `same_host` now treats `www.example.com` and `example.com` as the same host. Mixed www/apex linking no longer wastes the crawl budget.
- Depth-2 BFS fallback: if sitemap + homepage links yield fewer than `max_pages / 2` URLs, citable crawls hub-page links to fill the budget.
- Homepage fetch deduplication: cached Googlebot HTML and headers from `detect_spa` are reused for sitemap-fallback and HSTS capture. Reduces homepage fetches from 5 to 2 per audit.

### Fixed (scoring honesty)

- Categories with zero scorable checks no longer return a fake 100. They now display as `n/a (no checks)` in the CLI and `n/a` in the xlsx. Overall score is computed only from categories with measurements. This corrects the AI-specific category which had 0 checks in v0.1.0 but was showing 100/100 on every site.

### Calibration after fixes

- work-smart.ai 100/A (was 90/A, FP-1 was masking)
- stripe.com 74/B (was 77/B, dropped because AI-specific no longer inflates)
- example.com 18/F (was 27/F, same reason)

### Known limitations (documented for v0.2.0)

See `AUDIT-2026-05-20.md` Section "Deferred to v0.2.0" for 7 documented gaps including no JS rendering, no per-check timeout, and no soft-404 detection.

---

## v0.1.0 (2026-05-20)

Initial release.

- 11 checks across 6 AI readiness categories: Crawlability, Entity Clarity, Content Structure, Schema Markup, Authority Signals, AI-specific
- Async crawler (httpx + HTTP/2) with per-host rate limiting, dual-UA SPA detection, sitemap + homepage link discovery
- 3-sheet xlsx output: Summary, Action List, Per-Page Detail
- Verdict states `pass`, `warn`, `fail`, `na`, `unverified` (the last two are the false-positive shield)
- Letter grade A-F
- Work-Smart.ai attribution in banner, spreadsheet footer, and contextual post-audit resource recommendation
- CLI: `citable audit DOMAIN`, `citable version`

Calibration:

- work-smart.ai 90/A (expected 85-100)
- stripe.com 77/B (expected 65-80)
- example.com 27/F (expected 20-40)

Known limitations (v0.2.0 candidates):

- Only 11 of 21 planned checks shipped
- No interactive wizard yet (CLI flags only)
- Schema validity uses block-level type matching, not full pyld JSON-LD parsing
- No HTML report (xlsx only)
