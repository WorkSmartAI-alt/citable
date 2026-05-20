"""Data models for crawl pages and audit results.

Uses plain dataclasses to keep dependencies light. Pydantic is overkill for v0.1.0
since we do not accept user input as JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    """Outcome of a single check. The `unverified` and `na` states are
    the anti-false-positive shield. Never invent pass/fail when the evidence
    is ambiguous.
    """

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    NA = "na"
    UNVERIFIED = "unverified"


class Severity(str, Enum):
    """Severity of a check failure. P0 = ship blocker, INFO = nice to have."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    INFO = "INFO"


class Category(str, Enum):
    CRAWLABILITY = "Crawlability"
    ENTITY = "Entity Clarity"
    CONTENT = "Content Structure"
    SCHEMA = "Schema Markup"
    AUTHORITY = "Authority Signals"
    INTERNAL_LINKS = "Internal Linkage"
    AI_SPECIFIC = "AI-specific"


@dataclass
class Page:
    """One crawled page."""

    url: str
    status_code: int = 0
    final_url: str = ""
    render_time_ms: int = 0
    title: str = ""
    meta_description: str = ""
    h1_texts: list[str] = field(default_factory=list)
    h2_texts: list[str] = field(default_factory=list)
    canonical: str = ""
    og: dict[str, str] = field(default_factory=dict)
    hreflang: list[tuple[str, str]] = field(default_factory=list)
    html_lang: str = ""
    schema_blocks: list[dict] = field(default_factory=list)
    schema_raw_count: int = 0
    schema_rendered_count: int = 0
    image_alt_total: int = 0
    image_alt_missing: int = 0
    first_paragraph: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    error: str = ""
    fetched_via: str = "default"  # "default" or "googlebot"
    # Internal links found on this page as (url, anchor_text). Used by C-22/C-23/C-24.
    internal_links: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class CheckResult:
    """One check result against the site or a page."""

    check_id: str
    category: Category
    name: str
    verdict: Verdict
    severity: Severity
    message: str
    fix_text: str = ""
    evidence_url: str = ""
    evidence_snippet: str = ""
    pages_affected: int = 0
    total_pages: int = 0


@dataclass
class SiteContext:
    """Site-level facts gathered during crawl, used by site-level checks."""

    domain: str
    robots_txt: str = ""
    robots_status: int = 0
    sitemap_url: str = ""
    sitemap_status: int = 0
    sitemap_urls: list[str] = field(default_factory=list)
    spa_detected: bool = False
    languages_seen: set[str] = field(default_factory=set)
    homepage_headers: dict[str, str] = field(default_factory=dict)
    # Set when the audit is scoped to a path prefix. Holds the root homepage's
    # Page object so site-level checks (C-15 Organization, sameAs) can still
    # evaluate entity identity against the actual root homepage.
    root_page: "Page | None" = None
    # Map from page URL -> list of (target_url, anchor_text) found on that page.
    # Powers the Internal Linkage category (C-22, C-23, C-24).
    link_graph: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    # Status of each URL we probed for broken-link detection. URL -> status code.
    # Populated lazily by C-22.
    link_status: dict[str, int] = field(default_factory=dict)


@dataclass
class AuditReport:
    """Final audit output ready for the xlsx writer."""

    domain: str
    started_at: str
    finished_at: str
    pages: list[Page] = field(default_factory=list)
    check_results: list[CheckResult] = field(default_factory=list)
    category_scores: dict[str, float] = field(default_factory=dict)
    overall_score: float = 0.0
    letter_grade: str = "F"
    top_issue_check_id: str = ""
