---
name: Bug report
about: citable produced a wrong verdict, false positive, or false negative
title: '[BUG] '
labels: bug
assignees: ''
---

## What happened

Describe what citable did that was wrong. Include the check ID if known (e.g. C-11, C-22).

## What you expected

What should citable have reported?

## The audited URL

If the bug is reproducible against a public URL, share it. We need to be able to reproduce.

## Steps to reproduce

```bash
citable audit example.com --pages 20
```

## Audit output

Paste the relevant rows from the Action List sheet (or the CLI summary). Screenshots are fine too.

## Environment

- citable version: `citable version`
- Python version: `python --version`
- OS: macOS / Linux / Windows
- Install method: pipx / pip / clone+pip install -e .

## Additional context

Anything else that would help us debug. Was the site behind Cloudflare? WordPress? Custom CMS? SPA without SSR?
