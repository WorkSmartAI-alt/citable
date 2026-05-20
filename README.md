# citable

> Open-source CLI that scores your site for AI search (ChatGPT, Claude, Perplexity) and SEO foundations. 15 checks across crawlability, schema, internal links, content. Free.

[![PyPI version](https://img.shields.io/pypi/v/citable-cli.svg)](https://pypi.org/project/citable-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/WorkSmartAI-alt/citable/workflows/ci/badge.svg)](https://github.com/WorkSmartAI-alt/citable/actions)

Most websites are invisible to ChatGPT, Claude, and Perplexity. Most teams do not know why. Their classic SEO is usually solid; their AI search signals are not.

`citable` is a command-line tool that audits both. 15 checks across 6 categories cover the AI search basics (AI bot allowlist, FAQPage schema, Organization schema for entity recognition, render time for crawlers) AND the SEO foundations that overlap (robots.txt, sitemap.xml, canonical URLs, meta descriptions, titles, H1 hygiene, OG tags, HSTS, internal link audit, anchor text quality, orphan pages). Output is a multi-sheet xlsx with the exact fixes ranked by impact, owner, and effort.

```bash
pipx install citable-cli
citable audit example.com
```

That's it. A real audit runs in 30 to 90 seconds and produces a report your marketing agency can actually action.

## What you get

Five-sheet xlsx report:

| Sheet | For | What's in it |
|---|---|---|
| **Action Plan** | Your marketing agency | Plain-English tasks bucketed P1 / P2 / P3, with owner (Developer / Designer / Copywriter / DevOps) and effort estimate per task |
| **Summary** | Executive / audit trail | Overall score, category breakdown, top 5 actions |
| **Action List** | Your developer | Every check with verdict, severity, and technical fix text |
| **Per-Page Detail** | Anyone debugging | One row per crawled page: title, render time, OG tags, schemas detected, top issue |
| **Score Breakdown** | Anyone challenging the math | Exactly how each category was calculated. Auditable. |

[See a real example: examples/work-smart-ai-report.xlsx](examples/work-smart-ai-report.xlsx)

## Why citable

Because the alternative is paying $300/month for a SaaS that hides its math, or running a Lighthouse audit that does not check anything specific to AI search.

|  | citable | Profound | Scrunch | Lighthouse |
|---|---|---|---|---|
| Price | Free | $$$ | $$$ | Free |
| AI search visibility checks | Yes | Yes | Yes | No |
| Open source | Yes | No | No | Yes |
| Runs locally (no data sent to a server) | Yes | No | No | Yes |
| Marketing-agency action plan | Yes | Limited | Limited | No |
| Auditable scoring math | Yes | No | No | Yes |
| Internal link audit | Yes | No | Some | Some |
| Path-scoped section audits | Yes | No | No | No |

citable will not be the most feature-rich AI visibility tool on the market. The defensible moat is honesty: it shows its math, names its thresholds in the source code, and tells you what it cannot check.

## What citable checks

15 checks across 6 categories:

**Crawlability**
- robots.txt present and parseable
- AI bot allowlist (GPTBot, ClaudeBot, PerplexityBot, OAI-SearchBot, Google-Extended, Applebot-Extended)
- sitemap.xml exists and contains URLs
- Render time via Googlebot user agent

**Entity Clarity**
- Canonical URLs present and self-referential
- Open Graph basics (og:title, og:description, og:image, og:url)

**Content Structure**
- Meta descriptions present and in the 80 to 160 char range
- Title length in the 30 to 65 char range
- H1 present and unique per page

**Schema Markup**
- FAQPage schema on pages with Q&A content
- Organization schema on the root homepage with name, url, logo, sameAs (accepts 14 schema.org Organization subtypes)

**Authority Signals**
- HSTS header (Strict-Transport-Security)

**Internal Linkage**
- Broken internal links (HEAD-probes up to 50 link targets, filters known framework patterns like `/cdn-cgi/`)
- Anchor text quality (flags generic anchors like "click here" and "read more")
- Orphan pages (sitemap URLs that no crawled page links to)

Each check returns one of five verdicts: `pass`, `warn`, `fail`, `na` (does not apply), or `unverified` (evidence ambiguous). citable refuses to guess when evidence is mixed.

## Install

The clean way: [pipx](https://pipx.pypa.io) installs each Python CLI into its own isolated environment.

```bash
brew install pipx              # macOS, one-time
pipx ensurepath                # adds pipx CLIs to your PATH
pipx install citable-cli
```

The package is published on PyPI as `citable-cli` (the `citable` name on PyPI belongs to an unrelated 2021 Zenodo loader). The CLI binary is still `citable`. To import in Python: `import citable`.

For development or hacking on the code:

```bash
git clone https://github.com/WorkSmartAI-alt/citable.git
cd citable
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"        # includes pytest
```

Requires Python 3.10 or newer.

After install, verify with `citable doctor`. It checks Python version, dependencies, and venv status.

## Quick start

Audit a whole site (default 20 pages):

```bash
citable audit example.com
```

Audit just one section. Crawls the section page AND follows links 1 hop, so `/blog/` audits include the article pages linked from the hub:

```bash
citable audit example.com/blog/ --pages 50
```

CI usage (no banner, no progress, just the path to the report):

```bash
citable audit example.com --quiet
```

All options:

```bash
citable audit example.com \
  --pages 50 \
  --output ~/Desktop/report.xlsx \
  --no-googlebot \
  --quiet \
  --no-banner
```

## How the score works

Each check returns 1.0 (pass), 0.5 (warn), or 0.0 (fail). Category score = average across the category's checks. Overall score = weighted average of categories. `na` and `unverified` verdicts are excluded from the denominator.

| Category | Weight |
|---|---|
| Crawlability | 18% |
| Entity Clarity | 18% |
| Content Structure | 18% |
| Schema Markup | 18% |
| Authority Signals | 10% |
| Internal Linkage | 18% |

Letter grade: A (85-100), B (70-84), C (55-69), D (40-54), F (0-39).

Every audit's Score Breakdown sheet shows the math line by line. If you disagree with a category score, that sheet tells you exactly which check moved which number. Every threshold is also documented in [src/citable/checks.py](src/citable/checks.py) so you can challenge any value at the source.

## False-positive guardrails

Why most "AI visibility" tools cry wolf and lose trust:

- They flag missing hreflang on monolingual sites
- They compare canonical URLs without following redirects, then call self-referential canonicals broken
- They use max render time across all pages, so one slow image fails the site
- They mark wildcard `User-agent: *` rules as "AI bots allowed" without confirming intent
- They count decorative images as missing alt text
- They flag `/cdn-cgi/l/email-protection` as a broken link (it's a Cloudflare runtime pattern)

citable refuses to do this. When evidence is mixed, it marks the check `unverified` and tells you what would resolve the ambiguity. When the check does not apply, it marks `na` and excludes from the score.

## Known limitations (and why)

Honesty is the moat. Here is what citable does NOT do in v0.2.x:

1. **No JavaScript rendering.** SPA sites without server-side rendering will look empty. Adding Playwright is a v0.3.0 candidate. It adds 5-10x latency and a Chromium dependency.
2. **Read-only.** citable audits. It does not write to your site. Fixing the findings is on you (or your agency).
3. **No login required, so no authenticated pages.** Pages behind a login are not crawled.
4. **Single host.** Audits one site per run. No multi-site batch yet.
5. **English-only anchor analysis.** Generic anchor detection ("click here", "read more") is English-only. Spanish equivalents not yet covered. Coming in v0.2.x.
6. **No soft-404 detection.** A page that returns HTTP 200 with a 404 body is treated as a success. Adding heuristics is a v0.3.0 candidate.
7. **Broken-link probe caps at 50 targets.** Sites with thousands of unique link targets won't probe all of them.

If any of these matters for your use case, file an issue and tell us. Prioritization is driven by real demand.

## Who built this

Built by [Ignacio Lopez](https://www.linkedin.com/in/ignaciolopez2017/), founder of [Work-Smart.ai](https://work-smart.ai). Work-Smart.ai is a fractional Head of AI consultancy for mid-market companies ($10M to $1B revenue) in Miami and Latin America.

If you want this fixed instead of audited, that is what I do for a living: [work-smart.ai/services/ai-visibility](https://work-smart.ai/services/ai-visibility).

## Related tools

[ai-visibility-monitor (AVM)](https://github.com/WorkSmartAI-alt/ai-visibility-monitor) is the companion tool that tests how your brand shows up in AI engine responses. citable audits the site. AVM tests the queries. Together they form a 2-tool open-source GEO toolkit.

## License

MIT. See [LICENSE](LICENSE).

## Contributing

Issues and pull requests welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

For anything beyond a typo fix, open an issue first so we can align on scope.

## FAQ

**Does citable send data to a server?**
No. Everything runs on your machine. Read [src/citable/crawler.py](src/citable/crawler.py): the only outbound traffic is to the site you're auditing.

**Does it need an API key?**
No.

**Does it work on Cloudflare / Vercel / WordPress?**
Yes. Filters out known framework patterns (Cloudflare email protection, WordPress wp-json endpoints) to avoid false positives.

**Does it work on JavaScript SPAs?**
Limited. citable uses Googlebot's user agent so server-side rendered SPAs work fine. Client-side-only SPAs without SSR may appear empty. Playwright integration is a v0.3.0 candidate.

**Why is the score for my site so low?**
Open the Score Breakdown sheet in the xlsx. Every category is itemized. Then open Sheet 2 or Sheet 4 to find the specific failing checks.

**Can I run citable in CI?**
Yes. Use `--quiet` for clean output, `--no-banner` to suppress the ASCII art. Set thresholds in your CI script based on the score in the xlsx (or, when v0.3.0 ships, `--json` output for direct parsing).

**Is this an alternative to Profound / Scrunch / Otterly?**
For the basics, yes. For specialized features like AI engine query simulation, see [ai-visibility-monitor](https://github.com/WorkSmartAI-alt/ai-visibility-monitor) (citable's companion tool) or the paid alternatives.

**Why is it called citable?**
Because that is what AI engines do to your content: cite it, or not. citable tells you which.
