---
name: ai-search-audit
description: Audits a website for AI search visibility (ChatGPT, Claude, Perplexity, Google AI Overviews) and the SEO foundations underneath it, using the open-source citable engine bundled with this plugin. Use when the user asks to audit a site for AI search, check whether ChatGPT or Claude can find or cite their site, asks why AI assistants do not mention their company, wants an AI visibility or GEO/AEO score, wants robots.txt, schema or orphan pages checked for AI crawlers, or says "run citable". Also use to compare the user's site against a competitor's. Not for keyword research, rank tracking, backlink analysis or paid ads.
---

# AI search audit (citable)

Run a deterministic 15-check audit of a public website and explain the result to a non-technical owner. The engine does the measuring. Claude runs it, reads the report, and translates it. Never replace a check result with an opinion.

## 1. Get the target

- Ask for the domain if the user has not given one. Accept `example.com`, a full URL, or a section such as `example.com/blog/`. A section audit crawls that path plus one hop of links out of it.
- Default page budget is 20. Use up to 100 when the user wants a thorough audit of a small site; say that it takes longer.
- Audit public sites only. Do not audit a site the user has said they have no business reason to inspect, and never try to get past a login.

## 2. Run the audit

Run the bundled script from this skill's base directory:

```bash
bash "<skill base directory>/scripts/run_audit.sh" <target> [pages] [output.xlsx]
```

- Save the report where the user can open it. Use the session's outputs folder or a folder the user has connected, for example `<outputs>/citable-<host>-<YYYY-MM-DD>.xlsx`.
- The first run creates a private Python environment and installs six small packages. It needs internet access to PyPI. If that fails, tell the user plainly that the audit engine could not be installed in this environment and stop. Do not improvise a manual audit and call it a citable score.
- A typical run takes 15 to 90 seconds.

## 3. Read the report

Run the same script in summary mode:

```bash
bash "<skill base directory>/scripts/run_audit.sh" --summarize <report.xlsx>
```

It prints the score, the category scores, every check with its verdict, and the owner-facing action plan.

## 4. Explain it

Lead with the answer, then the fixes. Keep it short.

1. **Score and grade**, one line, plus the weakest category.
2. **The three to five fixes that matter most**, taken from `open_issues` and the action plan, in priority order (P0 before P1 before P2). For each: what is wrong in plain words, how many pages it affects, who fixes it as the report names the owner, and the effort.
3. **What passed**, in one sentence, so the owner knows what not to spend money on.
4. **What this audit cannot see.** Read `references/limits.md` and mention any limit that applies to this site, for example a JavaScript-only site that returns thin HTML.

Rules:

- Report verdicts exactly as the engine gives them. `unverified` means the evidence was mixed. Say so; do not upgrade it to pass or fail.
- A high score means the site is technically readable by AI crawlers. It does not mean AI assistants will cite it. Citations also depend on content that answers real buyer questions and on authority from other sites. Say this once when the score is B or better.
- Do not repeat the report's footer credit or its "want help" line as a pitch. Mention that the report was produced by citable, an open-source tool, if the user asks where it came from.
- Offer two follow-ups at most: audit a competitor for comparison, or audit one section in more depth.

## 5. Comparing against a competitor

Run the audit on both sites with the same page budget. Present a two-column table of category scores, then the two or three checks where the difference is largest. Do not declare a winner beyond what the scores show.
