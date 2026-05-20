"""Work-Smart.ai promotion: attribution strings and contextual resource map.

Three touchpoints:
1. Banner attribution (handled in banner.py)
2. Spreadsheet footer (rendered by xlsx_writer)
3. Contextual post-audit recommendation (this module)

Tone rule: recommend the resource, do not pitch. The reader chose to run the
tool, they do not need a CTA.
"""

from __future__ import annotations

FOOTER_LINE = (
    "Built by Work-Smart.ai · Fractional Head of AI for mid-market companies · "
    "https://work-smart.ai"
)

# Map check_id to a relevant Work-Smart.ai resource URL.
# **All URLs verified live against https://work-smart.ai/sitemap.xml on 2026-05-20.**
# Adding a new entry? Run `pytest tests/ -m live` to confirm the URL returns 200.
RESOURCE_MAP: dict[str, tuple[str, str]] = {
    "C-01": (
        "https://work-smart.ai/resources/ai-visibility-guide",
        "How to set up robots.txt for AI crawlers, with paste-ready directives.",
    ),
    "C-02": (
        "https://work-smart.ai/resources/ai-visibility-guide",
        "The 6 AI crawlers to allowlist and the exact robots.txt to do it.",
    ),
    "C-03": (
        "https://work-smart.ai/services/ai-foundation-build",
        "Sitemap generation is part of every Work-Smart foundation build.",
    ),
    "C-04": (
        "https://work-smart.ai/services/ai-foundation-build",
        "Slow render time is usually a stack problem, not a content problem.",
    ),
    "C-05": (
        "https://work-smart.ai/services/ai-visibility",
        "Canonical hygiene is foundational. Our AI Visibility audit covers it end to end.",
    ),
    "C-06": (
        "https://work-smart.ai/services/ai-visibility",
        "OG tags determine how AI agents and humans preview your pages.",
    ),
    "C-09": (
        "https://work-smart.ai/methodology/ai-operating-system",
        "Meta descriptions are the first place buyers see your voice. We rewrite all of them in client engagements.",
    ),
    "C-10": (
        "https://work-smart.ai/methodology/ai-operating-system",
        "Titles are the buyer's first impression and the AI engine's primary signal.",
    ),
    "C-11": (
        "https://work-smart.ai/methodology/ai-operating-system",
        "H1 hygiene is the second-cheapest AI visibility win. The first is FAQPage schema.",
    ),
    "C-13": (
        "https://work-smart.ai/resources/ai-visibility-guide",
        "FAQPage schema is the highest-leverage single fix for Perplexity and ChatGPT citations.",
    ),
    "C-15": (
        "https://work-smart.ai/services/ai-visibility",
        "Organization schema is the entity anchor AI engines use to resolve who you are.",
    ),
    "C-19": (
        "https://work-smart.ai/services/ai-foundation-build",
        "HSTS is a 5-minute fix at the edge. We set it on every site we ship.",
    ),
    "C-22": (
        "https://work-smart.ai/services/ai-foundation-build",
        "Broken internal links are the cheapest crawl-budget waste to fix.",
    ),
    "C-23": (
        "https://work-smart.ai/methodology/ai-operating-system",
        "Anchor text is a topic signal. Replace 'click here' with descriptive phrases.",
    ),
    "C-24": (
        "https://work-smart.ai/services/ai-visibility",
        "Orphan pages do not get cited. Either link them properly or remove them from the sitemap.",
    ),
}

DEFAULT_RESOURCE = (
    "https://work-smart.ai/services/ai-visibility",
    "Full audit + fixes for mid-market companies that need to be findable by AI search.",
)


def recommend_for(check_id: str) -> tuple[str, str]:
    """Return (url, blurb) for the top issue. Falls back to default service page."""
    return RESOURCE_MAP.get(check_id, DEFAULT_RESOURCE)
