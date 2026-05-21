"""Non-technical translation layer for the Action Plan xlsx sheet.

The Action Plan needs three things per check that the technical sheets do not:

- OWNER: which role picks this up (Developer / Designer / Copywriter / DevOps /
  Marketer). Tells the website owner who to assign the task to, whether the
  team is in-house or external.
- EFFORT: rough time-box so the owner or their team can sprint-plan
- WHY: plain-English business reason tied to outcomes (citations,
  click-throughs, entity recognition)

These maps are the source of truth. Keep messages free of jargon.
"""

from __future__ import annotations

# Owner per check. Multiple owners separated by " + " mean the work needs
# coordination between two roles.
CHECK_OWNER: dict[str, str] = {
    "C-01": "Developer",
    "C-02": "Developer",
    "C-03": "Developer",
    "C-04": "DevOps",
    "C-05": "Developer",
    "C-06": "Designer + Developer",
    "C-09": "Copywriter",
    "C-10": "Copywriter",
    "C-11": "Developer + Copywriter",
    "C-13": "Developer + Copywriter",
    "C-15": "Developer",
    "C-19": "DevOps",
    "C-22": "Developer",
    "C-23": "Copywriter",
    "C-24": "Marketer + Developer",
}

# Rough time-box per fix. Tailored to a typical agency that knows the CMS.
CHECK_EFFORT: dict[str, str] = {
    "C-01": "15 min",
    "C-02": "15 min",
    "C-03": "30 min",
    "C-04": "variable",
    "C-05": "1-4 hours",
    "C-06": "1 day (graphics + dev)",
    "C-09": "2-4 hours per 10 pages",
    "C-10": "1 hour per 10 pages",
    "C-11": "30 min per page",
    "C-13": "2-4 hours per content type",
    "C-15": "30 min",
    "C-19": "15 min",
    "C-22": "variable",
    "C-23": "2-4 hours",
    "C-24": "variable",
}

# Plain-English why-this-matters. No jargon. No em-dashes. Tied to outcomes a
# marketer cares about (citations, click-throughs, trust).
CHECK_WHY_AGENCY: dict[str, str] = {
    "C-01": "robots.txt is the first thing AI crawlers check. Missing or broken = lower confidence in your site.",
    "C-02": "Explicit allow-listing for GPTBot, ClaudeBot, PerplexityBot tells AI search engines that you welcome them. Without it, you rely on default permissions.",
    "C-03": "A working sitemap helps AI crawlers discover all your articles. Without it, they only find what's linked from your hub pages.",
    "C-04": "Pages slower than 2 seconds reduce how many pages AI crawlers ingest per visit. Slow = fewer articles indexed = fewer citations.",
    "C-05": "Canonical URLs tell AI engines which version of a page is the master copy. Mismatches dilute your ranking signal across duplicates.",
    "C-06": "OG tags (og:title, og:description, og:image) generate the rich preview cards your articles show in LinkedIn, X, Slack, and inside AI assistant responses. Missing og:image = no preview card = lower click-through.",
    "C-09": "Meta descriptions are the snippet AI engines and Google use to summarize each page. Missing or off-length descriptions get auto-generated, often poorly.",
    "C-10": "Page titles are what humans and AI engines see first. Too long get cut off; too short lose context. The 30-65 char range is the sweet spot for both.",
    "C-11": "Every page should have exactly one H1 stating what the page is about. Missing or duplicate H1s confuse AI engines about the page topic.",
    "C-13": "FAQPage schema is the single highest-impact AI visibility win. Pages with FAQ schema get cited roughly 8x more often by Perplexity and ChatGPT.",
    "C-15": "Organization schema is the entity card AI engines use to recognize your firm. Missing fields like 'logo' break entity recognition.",
    "C-19": "HSTS tells browsers and crawlers your site is HTTPS-only. Without it, you signal lower trust to security-aware AI crawlers.",
    "C-22": "Internal links pointing at dead URLs waste crawler budget and signal poor site maintenance.",
    "C-23": "Generic anchor text like 'click here' or 'read more' wastes a topic signal. AI engines use anchor text to learn what the linked page is about.",
    "C-24": "Orphan pages exist in your sitemap but no other page links to them. AI engines do not cite content they cannot reach through links.",
}

# When deciding priority for the agency view, map verdict + severity into a
# user-friendly bucket. The technical sheets keep their P0/P1/P2/INFO codes.
def agency_priority(severity: str, verdict: str) -> str:
    """Return P1 (this week), P2 (this month), P3 (optional), or PASS."""
    if verdict == "pass":
        return "PASS"
    if verdict == "fail" and severity in ("P0", "P1"):
        return "P1"
    if verdict == "warn" and severity in ("P0", "P1"):
        return "P2"
    if severity == "P2":
        return "P3"
    return "P3"


PRIORITY_LABEL = {
    "P1": "Fix this week",
    "P2": "Fix this month",
    "P3": "Nice to have",
    "PASS": "Already done",
}

PRIORITY_ORDER = {"P1": 0, "P2": 1, "P3": 2, "PASS": 3}


def owner_for(check_id: str) -> str:
    return CHECK_OWNER.get(check_id, "Developer")


def effort_for(check_id: str) -> str:
    return CHECK_EFFORT.get(check_id, "variable")


def why_for(check_id: str) -> str:
    return CHECK_WHY_AGENCY.get(check_id, "Improves how AI search engines understand your site.")
