# Contributing to citable

Thanks for considering a contribution. citable stays useful by accepting feedback and PRs from real users.

## Before opening a PR

Open an issue first for anything beyond a typo. We want to align on scope before you write code, so neither of us wastes time on something that doesn't land.

## Issue triage

We aim to respond to every issue within 48 hours during the week. We may not always have a fix the same week, but you'll get a real reply.

Three issue templates exist:

- **Bug report** — citable produced a wrong verdict, false positive, or false negative
- **Feature request** — you'd like citable to check something it doesn't, or output something differently
- **Question** — how do I do X with citable

## Development setup

```bash
git clone https://github.com/WorkSmartAI-alt/citable.git
cd citable
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

## Running tests

```bash
pytest tests/                 # smoke tests, no network
pytest tests/ -m live         # hits work-smart.ai sitemap. Run before releases.
```

18 smoke tests + 2 live URL tests should pass on a clean install.

## Code style

- Python 3.10+
- Format with ruff: `ruff format src tests`
- Lint with ruff: `ruff check src tests`
- Match existing patterns. The codebase is small enough to read in one sitting.

## Voice rules (apply to README, CLI strings, log messages, error messages)

These are non-negotiable. PRs that violate them will be asked to rework.

- No em-dashes (—) or en-dashes (–). Use commas, colons, or "to" for ranges.
- No exclamation points.
- No emoji unless explicitly required.
- Direct, declarative, operator tone. Not consultant-speak. Not SaaS marketing hype.
- Buyer's language first. Never "transform", "leverage" as a verb, "unlock", "synergy", "robust", "seamless", "innovative", "empower", "best-in-class", "world-class", "paradigm", "delve."
- Short paragraphs. Concrete numbers over abstractions.

## Adding a new check

If you want to add a new check (call it `C-XX`):

1. Read [src/citable/checks.py](src/citable/checks.py) to see the existing 15 checks
2. Pick a category (Crawlability / Entity / Content / Schema / Authority / Internal Linkage / AI-specific)
3. Write the check function returning a `list[CheckResult]`. Use `unverified` or `na` rather than guessing when evidence is mixed.
4. Add specific, paste-ready `fix_text` (not generic "add schema markup")
5. Add the check to `CHECK_FUNCTIONS` registry at the bottom of checks.py
6. Add the check to `src/citable/briefing.py` `CHECK_OWNER`, `CHECK_EFFORT`, `CHECK_WHY_AGENCY` maps
7. Add the check to `src/citable/promo.py` `RESOURCE_MAP` with a verified live URL
8. Run `pytest tests/` to confirm `test_resource_map_covers_all_shipped_checks` passes
9. Run `pytest tests/ -m live` to verify any new URLs are reachable
10. Update CHANGELOG.md

## Adding a new RESOURCE_MAP URL

Always verify the URL is live against the relevant site's sitemap before adding. The pytest live test enforces this — if the URL returns a non-200, the test fails.

## Releases

We do not promise a release schedule. Releases happen when the work is ready, not on a calendar.

## License

By contributing, you agree your contribution is licensed under MIT (the same license as the project).
