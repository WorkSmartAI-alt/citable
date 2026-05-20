"""Compute category scores, overall score, letter grade."""

from __future__ import annotations

from citable.models import AuditReport, Category, CheckResult, Severity, Verdict

# Category weights (must sum to 1.0).
# AI_SPECIFIC drops to 0 because v0.2.0 still ships no checks in that category;
# weight is redistributed when actual AI-specific checks land (Speakable, etc.).
CATEGORY_WEIGHTS = {
    Category.CRAWLABILITY.value: 0.18,
    Category.ENTITY.value: 0.18,
    Category.CONTENT.value: 0.18,
    Category.SCHEMA.value: 0.18,
    Category.AUTHORITY.value: 0.10,
    Category.INTERNAL_LINKS.value: 0.18,
    Category.AI_SPECIFIC.value: 0.0,
}

# Verdict scoring (per check, before category roll-up)
VERDICT_POINTS = {
    Verdict.PASS: 1.0,
    Verdict.WARN: 0.5,
    Verdict.FAIL: 0.0,
}


def letter_grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def severity_rank(s: Severity) -> int:
    return {Severity.P0: 0, Severity.P1: 1, Severity.P2: 2, Severity.INFO: 3}[s]


def compute_category_score(results: list[CheckResult], category: Category) -> tuple[float | None, int, int, int]:
    """Returns (score 0-100 or None, pass_count, warn_count, fail_count).
    NA and UNVERIFIED verdicts are excluded from the denominator. Categories
    with zero scorable checks return None so they do not contribute a fake
    100 to the overall score.
    """
    relevant = [
        r for r in results
        if r.category == category and r.verdict in (Verdict.PASS, Verdict.WARN, Verdict.FAIL)
    ]
    if not relevant:
        return None, 0, 0, 0
    total_points = sum(VERDICT_POINTS[r.verdict] for r in relevant)
    score = (total_points / len(relevant)) * 100
    passes = sum(1 for r in relevant if r.verdict == Verdict.PASS)
    warns = sum(1 for r in relevant if r.verdict == Verdict.WARN)
    fails = sum(1 for r in relevant if r.verdict == Verdict.FAIL)
    return round(score, 1), passes, warns, fails


def compute_overall_score(category_scores: dict[str, float]) -> float:
    """Weighted average across categories."""
    total = 0.0
    weight_sum = 0.0
    for cat_name, weight in CATEGORY_WEIGHTS.items():
        score = category_scores.get(cat_name)
        if score is None:
            continue
        total += score * weight
        weight_sum += weight
    if weight_sum == 0:
        return 0.0
    return round(total / weight_sum, 1)


def top_issue(results: list[CheckResult]) -> CheckResult | None:
    """Highest-severity fail or warn. Used to pick the contextual work-smart.ai resource."""
    candidates = [
        r for r in results
        if r.verdict in (Verdict.FAIL, Verdict.WARN)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda r: (
        severity_rank(r.severity),
        0 if r.verdict == Verdict.FAIL else 1,
        -r.pages_affected,
    ))
    return candidates[0]


def finalize(report: AuditReport) -> AuditReport:
    """Mutates report in place: sets category_scores, overall_score, letter_grade, top_issue_check_id.

    Categories with no scorable checks are stored as -1.0 (sentinel for "not measured").
    The xlsx writer and CLI render -1.0 as "n/a" rather than "100".
    """
    scores: dict[str, float] = {}
    for cat in Category:
        s, _, _, _ = compute_category_score(report.check_results, cat)
        scores[cat.value] = s if s is not None else -1.0
    report.category_scores = scores
    # Strip -1.0 sentinel values before computing overall
    measurable = {k: v for k, v in scores.items() if v >= 0}
    report.overall_score = compute_overall_score(measurable)
    report.letter_grade = letter_grade(report.overall_score)
    top = top_issue(report.check_results)
    report.top_issue_check_id = top.check_id if top else ""
    return report
