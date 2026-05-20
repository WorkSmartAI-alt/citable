# citable — Roadmap

Honest list of what is shipped, what is next, and what is being deferred until users actually ask. No release-date promises.

## Shipped (v0.2.x)

15 checks, 5-sheet xlsx, path-scoped audits, score breakdown, dual-UA SPA detection, sitemap-index recursion, 1-hop link expansion, broken-link probing with framework-pattern filters, anchor text quality, orphan detection.

## v0.3.0 candidates (driven by user feedback)

These will ship in order of how many issues request them, not by author priority.

- **JavaScript rendering (`--render` flag, Playwright opt-in).** For SPAs without server-side rendering. Adds 5-10x latency + Chromium dependency. Probably the most-requested feature post-launch.
- **`--json` output flag.** Machine-readable JSON sidecar alongside the xlsx. Useful for CI pipelines that want to gate on score.
- **`citable diff old.xlsx new.xlsx`.** Compare two audit runs and show what improved or regressed. Powers weekly-audit workflows.
- **Soft-404 detection.** Pages that return HTTP 200 but have a 404-style body. Heuristic: title contains "not found", H1 says "page does not exist", etc. Could go wrong; needs careful threshold.
- **Spanish anchor text generics.** "Haga clic", "leer más", "más información". For LatAm sites. Author's primary market — likely v0.3.0.
- **Article schema completeness check (new C-25).** Author, datePublished, dateModified, headline. Currently checked via @graph type only.
- **Speakable schema check (new C-26).** Pages with Speakable get featured in voice-assistant answers.
- **Image alt text coverage (new C-27).** Already designed (C-20 in original spec) but deferred from v0.1.0.

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
