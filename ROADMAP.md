# citable — Roadmap

Honest list of what is shipped, what is next, and what is being deferred until users actually ask. No release-date promises.

## Shipped (v0.2.x)

15 checks, 5-sheet xlsx, path-scoped audits, score breakdown, dual-UA SPA detection, sitemap-index recursion, 1-hop link expansion, broken-link probing with framework-pattern filters, anchor text quality, orphan detection.

## v0.3.0 confirmed scope

- [#1 Soften C-02 AI bot allowlist severity](https://github.com/WorkSmartAI-alt/citable/issues/1) — per r/coolgithubprojects feedback. Robots.txt is opt-out; absence of explicit allow doesn't block AI bots. Soften severity, re-weight category math.
- [#2 Add firewall blocking detection (C-26)](https://github.com/WorkSmartAI-alt/citable/issues/2) — per r/coolgithubprojects feedback. Cloudflare/WAF can block AI bot UAs before robots.txt is even read. New P0 check.
- [#3 Add soft-404 detection (C-25)](https://github.com/WorkSmartAI-alt/citable/issues/3) — validated by real Bing report on work-smart.ai 2026-05-21. SPA catch-all returns 200 + empty shell for unknown routes. New P0 check.

## v0.4.0 candidates

- **GitHub Action wrapper.** `uses: WorkSmartAI-alt/citable-action@v1` to run citable in CI and fail builds if score drops below a threshold. High-value distribution but only ship after 200+ stars validates demand.
- **Multi-site batch mode.** Audit N sites in parallel from a file of URLs.
- **Auto-open xlsx after run (`--open` flag).** macOS-specific, complicates cross-platform support.
- **Webhook on completion (`--webhook`).** Push the score to Slack / Discord / a custom endpoint.

## Explicit non-goals

- **No SaaS version.** citable stays a CLI. Hosted demos are out of scope.
- **No telemetry.** No phone-home, no opt-in analytics. Open source = trustworthy = no surveillance.
- **No Pro tier.** Everything free, MIT.
- **No VS Code extension.** Out of scope for a CLI tool.
- **No web UI.** Out of scope.

## How to influence the roadmap

File an issue using the [Feature request template](.github/ISSUE_TEMPLATE/feature_request.md). The more concrete the use case, the higher the priority.

A feature that 3+ users have asked for moves to the top.
