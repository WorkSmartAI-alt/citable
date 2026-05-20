## What this changes

One paragraph.

## Why

Link the issue this PR closes. Or describe the problem if it's a typo fix and no issue exists.

## Voice check

I've reviewed the changes for the voice rules in CONTRIBUTING.md:

- [ ] No em-dashes or en-dashes
- [ ] No exclamation points
- [ ] No banned filler ("transform", "leverage", "unlock", etc.)

## Tests

- [ ] `pytest tests/` passes (18 smoke tests)
- [ ] `pytest tests/ -m live` passes (2 live URL tests) — only required if I added a RESOURCE_MAP URL

## Calibration

If this changes a check threshold or scoring weight, I've re-run audits on the 3 calibration sites and confirmed they land in expected range:

- [ ] work-smart.ai: expected 90-100 (A)
- [ ] stripe.com: expected 65-80 (B-C)
- [ ] example.com: expected 0-40 (F)

## Anything else

Anything reviewers should know.
