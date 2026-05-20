"""Smoke tests. No live network calls — use fixtures or unit-level checks."""

from __future__ import annotations

from citable.banner import render_banner
from citable.crawler import canonicalize_url, matches_prefix, normalize_domain, normalize_target
from citable.models import (
    AuditReport,
    Category,
    CheckResult,
    Page,
    Severity,
    SiteContext,
    Verdict,
)
from citable.promo import RESOURCE_MAP, recommend_for
from citable.scoring import compute_overall_score, finalize, letter_grade


def test_banner_renders():
    out = render_banner()
    # Banner spells "citable" in ASCII art so we check for substrings we know
    from citable import __version__
    assert "Work-Smart.ai" in out
    assert __version__ in out
    assert "ChatGPT" in out


def test_normalize_domain():
    assert normalize_domain("example.com") == "https://example.com"
    assert normalize_domain("https://example.com/") == "https://example.com"
    assert normalize_domain("https://example.com/blog") == "https://example.com"
    assert normalize_domain("  example.com  ") == "https://example.com"


def test_canonicalize_url():
    assert canonicalize_url("https://example.com") == "https://example.com/"
    assert canonicalize_url("https://example.com/") == "https://example.com/"
    assert canonicalize_url("https://example.com/page") == "https://example.com/page"
    assert canonicalize_url("https://example.com/page/") == "https://example.com/page"
    assert canonicalize_url("https://EXAMPLE.com/page") == "https://example.com/page"
    assert canonicalize_url("https://example.com/page#top") == "https://example.com/page"


def test_normalize_target_whole_site():
    assert normalize_target("example.com") == ("https://example.com", "")
    assert normalize_target("https://example.com/") == ("https://example.com", "")
    assert normalize_target("https://example.com") == ("https://example.com", "")


def test_normalize_target_scoped():
    assert normalize_target("example.com/resources") == ("https://example.com", "/resources")
    assert normalize_target("example.com/resources/") == ("https://example.com", "/resources")
    assert normalize_target("https://www.example.com/blog/category/") == (
        "https://www.example.com", "/blog/category",
    )
    assert normalize_target("https://example.com/a/b/c") == ("https://example.com", "/a/b/c")


def test_matches_prefix_whole_site():
    # Empty prefix matches everything on same host
    assert matches_prefix("https://example.com/anything", "https://example.com", "")
    assert matches_prefix("https://example.com/", "https://example.com", "")


def test_matches_prefix_scoped():
    root = "https://example.com"
    prefix = "/resources"
    assert matches_prefix("https://example.com/resources", root, prefix)
    assert matches_prefix("https://example.com/resources/", root, prefix)
    assert matches_prefix("https://example.com/resources/article", root, prefix)
    assert matches_prefix("https://example.com/resources/article/", root, prefix)
    # Must NOT match similar but distinct paths
    assert not matches_prefix("https://example.com/resources-blog", root, prefix)
    assert not matches_prefix("https://example.com/about", root, prefix)
    assert not matches_prefix("https://example.com/", root, prefix)
    # Different host rejected
    assert not matches_prefix("https://other.com/resources/x", root, prefix)


def test_matches_prefix_handles_www_vs_apex():
    # Same _bare_host logic: www and apex treated as same host
    assert matches_prefix("https://www.example.com/resources/x", "https://example.com", "/resources")
    assert matches_prefix("https://example.com/resources/x", "https://www.example.com", "/resources")


def test_letter_grade():
    assert letter_grade(95) == "A"
    assert letter_grade(85) == "A"
    assert letter_grade(70) == "B"
    assert letter_grade(55) == "C"
    assert letter_grade(40) == "D"
    assert letter_grade(0) == "F"


def test_compute_overall_score_weighted():
    # v0.2.0 weights: Crawlability/Entity/Content/Schema/InternalLinks each 18%,
    # Authority 10%, AI-specific 0%
    scores = {
        Category.CRAWLABILITY.value: 100,
        Category.ENTITY.value: 100,
        Category.CONTENT.value: 100,
        Category.SCHEMA.value: 0,
        Category.AUTHORITY.value: 100,
        Category.INTERNAL_LINKS.value: 100,
    }
    # Schema=0 (18%), everything else = 100. Effective:
    # (100*0.18 + 100*0.18 + 100*0.18 + 0*0.18 + 100*0.10 + 100*0.18) / sum(weights)
    # = (18+18+18+0+10+18) / 1.0 = 82.0
    result = compute_overall_score(scores)
    assert abs(result - 82.0) < 0.5, f"got {result}"


def test_finalize_picks_top_issue():
    report = AuditReport(domain="https://example.com", started_at="now", finished_at="now")
    report.check_results = [
        CheckResult(
            check_id="C-13",
            category=Category.SCHEMA,
            name="FAQPage schema",
            verdict=Verdict.FAIL,
            severity=Severity.P0,
            message="missing",
            pages_affected=5,
        ),
        CheckResult(
            check_id="C-05",
            category=Category.ENTITY,
            name="Canonical",
            verdict=Verdict.WARN,
            severity=Severity.P1,
            message="warn",
            pages_affected=1,
        ),
    ]
    finalize(report)
    assert report.top_issue_check_id == "C-13"


def test_recommend_for_known_check():
    url, blurb = recommend_for("C-13")
    assert "work-smart.ai" in url
    assert blurb


def test_recommend_for_unknown_check_falls_back():
    url, blurb = recommend_for("C-999")
    assert "work-smart.ai" in url
    assert blurb


def test_resource_map_covers_all_shipped_checks():
    shipped = {
        "C-01", "C-02", "C-03", "C-04", "C-05", "C-06",
        "C-09", "C-10", "C-11", "C-13", "C-15", "C-19",
        "C-22", "C-23", "C-24",
    }
    for check_id in shipped:
        assert check_id in RESOURCE_MAP, f"{check_id} missing from RESOURCE_MAP"


def test_no_em_dashes_in_user_facing_strings():
    """Voice guardrail: no em-dashes in any string we print to the user."""
    from citable import banner, promo

    sources = [banner.BANNER, banner.TAGLINE, banner.ATTRIBUTION, promo.FOOTER_LINE]
    for url, blurb in promo.RESOURCE_MAP.values():
        sources.append(blurb)
    for s in sources:
        assert "—" not in s, f"em-dash found in: {s[:50]}"
        assert "–" not in s, f"en-dash found in: {s[:50]}"


def test_no_exclamation_marks_in_promo():
    from citable import banner, promo

    sources = [banner.TAGLINE, banner.ATTRIBUTION, promo.FOOTER_LINE]
    for _, blurb in promo.RESOURCE_MAP.values():
        sources.append(blurb)
    for s in sources:
        assert "!" not in s, f"exclamation found in: {s[:50]}"
