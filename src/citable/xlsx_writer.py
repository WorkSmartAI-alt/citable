"""Write the audit report as a 3-sheet xlsx file.

Sheet 1: Summary (overall score, category breakdown, top 5 actions)
Sheet 2: Action List (every check with fail/warn verdict, sorted by severity)
Sheet 3: Per-Page Detail (one row per crawled page, color-coded by issue count)
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Side, Border
from openpyxl.utils import get_column_letter

from citable.briefing import (
    PRIORITY_LABEL,
    PRIORITY_ORDER,
    agency_priority,
    effort_for,
    owner_for,
    why_for,
)
from citable.models import AuditReport, Category, Severity, Verdict
from citable.promo import FOOTER_LINE, recommend_for
from citable.scoring import severity_rank

# Color palette
COLOR_PASS = "C6EFCE"
COLOR_PASS_FONT = "006100"
COLOR_WARN = "FFEB9C"
COLOR_WARN_FONT = "9C5700"
COLOR_FAIL = "FFC7CE"
COLOR_FAIL_FONT = "9C0006"
COLOR_NEUTRAL = "F2F2F2"
COLOR_HEADER = "1F2937"
COLOR_HEADER_FONT = "FFFFFF"

THIN = Side(style="thin", color="DDDDDD")
BORDER = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)


def verdict_fill(verdict: Verdict) -> PatternFill:
    if verdict == Verdict.PASS:
        return PatternFill(start_color=COLOR_PASS, end_color=COLOR_PASS, fill_type="solid")
    if verdict == Verdict.WARN:
        return PatternFill(start_color=COLOR_WARN, end_color=COLOR_WARN, fill_type="solid")
    if verdict == Verdict.FAIL:
        return PatternFill(start_color=COLOR_FAIL, end_color=COLOR_FAIL, fill_type="solid")
    return PatternFill(start_color=COLOR_NEUTRAL, end_color=COLOR_NEUTRAL, fill_type="solid")


def grade_fill(grade: str) -> PatternFill:
    if grade in ("A", "B"):
        return PatternFill(start_color=COLOR_PASS, end_color=COLOR_PASS, fill_type="solid")
    if grade == "C":
        return PatternFill(start_color=COLOR_WARN, end_color=COLOR_WARN, fill_type="solid")
    return PatternFill(start_color=COLOR_FAIL, end_color=COLOR_FAIL, fill_type="solid")


def issues_fill(count: int) -> PatternFill:
    if count == 0:
        return PatternFill(start_color=COLOR_PASS, end_color=COLOR_PASS, fill_type="solid")
    if count <= 3:
        return PatternFill(start_color=COLOR_WARN, end_color=COLOR_WARN, fill_type="solid")
    return PatternFill(start_color=COLOR_FAIL, end_color=COLOR_FAIL, fill_type="solid")


def autosize_columns(ws, max_width: int = 60) -> None:
    for col_cells in ws.columns:
        values = []
        col_letter = None
        for cell in col_cells:
            if hasattr(cell, "column_letter"):
                col_letter = cell.column_letter
            v = cell.value
            if v is None:
                continue
            values.append(len(str(v)))
        if col_letter:
            width = min(max(values + [10]), max_width)
            ws.column_dimensions[col_letter].width = width


def write_summary_sheet(ws, report: AuditReport) -> None:
    ws.title = "Summary"

    # Title
    ws["A1"] = "citable Audit Report"
    ws["A1"].font = Font(name="Calibri", size=18, bold=True)
    ws.merge_cells("A1:E1")

    ws["A2"] = f"Domain: {report.domain}"
    ws["A3"] = f"Date: {report.started_at}"
    ws["A4"] = f"Pages audited: {len(report.pages)}"
    for cell in ("A2", "A3", "A4"):
        ws[cell].font = Font(size=11)

    # Overall score block
    ws["A6"] = "Overall Score"
    ws["A6"].font = Font(size=12, bold=True)
    ws["A7"] = f"{report.overall_score:.0f} / 100"
    ws["A7"].font = Font(size=24, bold=True)
    ws["A7"].fill = grade_fill(report.letter_grade)
    ws["A7"].alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells("A7:B7")

    ws["C7"] = report.letter_grade
    ws["C7"].font = Font(size=24, bold=True)
    ws["C7"].fill = grade_fill(report.letter_grade)
    ws["C7"].alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells("C7:C7")
    ws.row_dimensions[7].height = 36

    # Category breakdown
    ws["A9"] = "Category"
    ws["B9"] = "Score"
    ws["C9"] = "Grade"
    for col in ("A", "B", "C"):
        ws[f"{col}9"].font = Font(bold=True, color=COLOR_HEADER_FONT)
        ws[f"{col}9"].fill = PatternFill(start_color=COLOR_HEADER, end_color=COLOR_HEADER, fill_type="solid")
        ws[f"{col}9"].alignment = Alignment(horizontal="left")

    from citable.scoring import letter_grade as lg

    row = 10
    for cat in Category:
        score = report.category_scores.get(cat.value, 0.0)
        ws.cell(row=row, column=1, value=cat.value)
        if score < 0:
            ws.cell(row=row, column=2, value="n/a")
            ws.cell(row=row, column=3, value="no checks")
            ws.cell(row=row, column=3).font = Font(italic=True, color="6B7280")
        else:
            ws.cell(row=row, column=2, value=f"{score:.0f}")
            gr = lg(score)
            ws.cell(row=row, column=3, value=gr)
            ws.cell(row=row, column=3).fill = grade_fill(gr)
            ws.cell(row=row, column=3).alignment = Alignment(horizontal="center")
        row += 1

    # Top 5 actions
    row += 1
    ws.cell(row=row, column=1, value="Top 5 Actions").font = Font(size=12, bold=True)
    row += 1
    headers = ["Severity", "Category", "Issue", "Pages", "Fix"]
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=col, value=h)
        c.font = Font(bold=True, color=COLOR_HEADER_FONT)
        c.fill = PatternFill(start_color=COLOR_HEADER, end_color=COLOR_HEADER, fill_type="solid")
    row += 1

    actions = [r for r in report.check_results if r.verdict in (Verdict.FAIL, Verdict.WARN)]
    actions.sort(key=lambda r: (
        severity_rank(r.severity),
        0 if r.verdict == Verdict.FAIL else 1,
        -r.pages_affected,
    ))
    for action in actions[:5]:
        ws.cell(row=row, column=1, value=action.severity.value)
        ws.cell(row=row, column=2, value=action.category.value)
        ws.cell(row=row, column=3, value=action.name)
        ws.cell(row=row, column=4, value=action.pages_affected or 0)
        ws.cell(row=row, column=5, value=action.fix_text[:300] if action.fix_text else action.message)
        ws.cell(row=row, column=1).fill = verdict_fill(action.verdict)
        ws.cell(row=row, column=5).alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[row].height = 60
        row += 1

    # Recommendation footer
    if report.top_issue_check_id:
        url, blurb = recommend_for(report.top_issue_check_id)
        row += 1
        ws.cell(row=row, column=1, value=f"Help with this: {blurb}")
        ws.cell(row=row, column=1).font = Font(italic=True)
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        row += 1
        ws.cell(row=row, column=1, value=url)
        ws.cell(row=row, column=1).font = Font(italic=True, color="2563EB", underline="single")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        row += 2

    # Always-on footer
    ws.cell(row=row, column=1, value=FOOTER_LINE)
    ws.cell(row=row, column=1).font = Font(italic=True, size=9, color="6B7280")
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)

    # Column widths
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 30
    ws.column_dimensions["D"].width = 10
    ws.column_dimensions["E"].width = 80
    ws.freeze_panes = "A2"


def write_action_sheet(ws, report: AuditReport) -> None:
    ws.title = "Action List"
    headers = ["Check ID", "Category", "Severity", "Verdict", "Issue", "Pages Affected", "Fix"]
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=col, value=h)
        c.font = Font(bold=True, color=COLOR_HEADER_FONT)
        c.fill = PatternFill(start_color=COLOR_HEADER, end_color=COLOR_HEADER, fill_type="solid")

    actions = [
        r for r in report.check_results
        if r.verdict in (Verdict.FAIL, Verdict.WARN, Verdict.PASS, Verdict.UNVERIFIED)
    ]
    actions.sort(key=lambda r: (
        severity_rank(r.severity),
        0 if r.verdict == Verdict.FAIL else (1 if r.verdict == Verdict.WARN else 2),
        r.check_id,
    ))

    for idx, a in enumerate(actions, start=2):
        ws.cell(row=idx, column=1, value=a.check_id)
        ws.cell(row=idx, column=2, value=a.category.value)
        ws.cell(row=idx, column=3, value=a.severity.value)
        c4 = ws.cell(row=idx, column=4, value=a.verdict.value)
        c4.fill = verdict_fill(a.verdict)
        ws.cell(row=idx, column=5, value=f"{a.name}: {a.message}")
        ws.cell(row=idx, column=5).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(row=idx, column=6, value=a.pages_affected or 0)
        ws.cell(row=idx, column=7, value=a.fix_text)
        ws.cell(row=idx, column=7).alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[idx].height = 45

    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 20
    ws.column_dimensions["C"].width = 10
    ws.column_dimensions["D"].width = 11
    ws.column_dimensions["E"].width = 60
    ws.column_dimensions["F"].width = 8
    ws.column_dimensions["G"].width = 80
    ws.freeze_panes = "A2"


def _issues_for_page(report: AuditReport, page_url: str) -> tuple[int, str]:
    """Count fails/warns that name this page in evidence, and pick a top issue summary."""
    issues = []
    for r in report.check_results:
        if r.verdict not in (Verdict.FAIL, Verdict.WARN):
            continue
        if r.evidence_url and r.evidence_url == page_url:
            issues.append(r)
    issues.sort(key=lambda r: severity_rank(r.severity))
    top = issues[0].name if issues else ""
    return len(issues), top


def write_pages_sheet(ws, report: AuditReport) -> None:
    ws.title = "Per-Page Detail"
    headers = [
        "URL", "Title", "Status", "Render (ms)", "Has Canonical",
        "OG Tags", "Schema Types", "Issues", "Top Issue",
    ]
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=col, value=h)
        c.font = Font(bold=True, color=COLOR_HEADER_FONT)
        c.fill = PatternFill(start_color=COLOR_HEADER, end_color=COLOR_HEADER, fill_type="solid")

    for idx, p in enumerate(report.pages, start=2):
        ws.cell(row=idx, column=1, value=p.final_url or p.url)
        ws.cell(row=idx, column=1).hyperlink = p.final_url or p.url
        ws.cell(row=idx, column=1).font = Font(color="2563EB", underline="single")
        ws.cell(row=idx, column=2, value=(p.title or "")[:120])
        ws.cell(row=idx, column=3, value=p.status_code)
        ws.cell(row=idx, column=4, value=p.render_time_ms)
        ws.cell(row=idx, column=5, value="yes" if p.canonical else "no")
        ws.cell(row=idx, column=6, value=len([k for k in ("og:title", "og:description", "og:image", "og:url") if p.og.get(k)]))
        schema_types: list[str] = []

        def _collect_types(node):
            if isinstance(node, dict):
                t = node.get("@type")
                if isinstance(t, str):
                    schema_types.append(t)
                elif isinstance(t, list):
                    schema_types.extend([str(x) for x in t if isinstance(x, str)])
                # WordPress / Yoast pattern: schemas nested in @graph
                graph = node.get("@graph")
                if isinstance(graph, list):
                    for g in graph:
                        _collect_types(g)
            elif isinstance(node, list):
                for item in node:
                    _collect_types(item)

        for b in p.schema_blocks:
            _collect_types(b)
        ws.cell(row=idx, column=7, value=", ".join(sorted(set(schema_types))[:8]) or "(none)")
        count, top = _issues_for_page(report, p.final_url or p.url)
        c8 = ws.cell(row=idx, column=8, value=count)
        c8.fill = issues_fill(count)
        c8.alignment = Alignment(horizontal="center")
        ws.cell(row=idx, column=9, value=top)

    ws.column_dimensions["A"].width = 55
    ws.column_dimensions["B"].width = 45
    ws.column_dimensions["C"].width = 8
    ws.column_dimensions["D"].width = 12
    ws.column_dimensions["E"].width = 14
    ws.column_dimensions["F"].width = 10
    ws.column_dimensions["G"].width = 35
    ws.column_dimensions["H"].width = 8
    ws.column_dimensions["I"].width = 50
    ws.freeze_panes = "A2"


def write_action_plan_sheet(ws, report: AuditReport) -> None:
    """Non-technical view designed for the website owner, in-house marketing
    team, or any external agency receiving the report. Plain English, owner
    per task (Developer / Designer / Copywriter / DevOps), effort estimate,
    priority bucket (P1 this week, P2 this month, P3 optional). First sheet
    that opens by default."""
    ws.title = "Action Plan"

    # Header
    ws["A1"] = f"Action Plan: {report.domain}"
    ws["A1"].font = Font(name="Calibri", size=18, bold=True)
    ws.merge_cells("A1:F1")

    ws["A2"] = f"Audit date: {report.started_at[:10]}  ·  Pages audited: {len(report.pages)}  ·  Overall: {report.overall_score:.0f}/100 ({report.letter_grade})"
    ws["A2"].font = Font(size=10, color="6B7280")
    ws.merge_cells("A2:F2")

    # What this is
    intro = (
        "AI search engines (ChatGPT, Claude, Perplexity, Google AI Overviews) decide which "
        "sites to cite based on machine-readable signals. This sheet lists exactly what to "
        "fix, who should fix it, and roughly how long each fix takes."
    )
    ws["A4"] = "What this is"
    ws["A4"].font = Font(size=12, bold=True)
    ws["A5"] = intro
    ws["A5"].font = Font(size=10)
    ws["A5"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells("A5:F5")
    ws.row_dimensions[5].height = 45

    # Group findings into P1/P2/P3 buckets. Skip NA and UNVERIFIED entirely:
    # those mean "does not apply" or "evidence ambiguous" — they are not actions.
    buckets: dict[str, list] = {"P1": [], "P2": [], "P3": []}
    for r in report.check_results:
        if r.verdict in (Verdict.NA, Verdict.UNVERIFIED):
            continue
        bucket = agency_priority(r.severity.value, r.verdict.value)
        if bucket == "PASS":
            continue
        if bucket in buckets:
            buckets[bucket].append(r)
    for b in buckets.values():
        b.sort(key=lambda r: (severity_rank(r.severity), r.check_id))

    row = 7
    section_titles = {
        "P1": ("Fix this week: high impact, low effort", COLOR_FAIL),
        "P2": ("Fix this month: improves discoverability", COLOR_WARN),
        "P3": ("Nice to have: incremental gains", COLOR_NEUTRAL),
    }
    for bucket in ("P1", "P2", "P3"):
        items = buckets[bucket]
        if not items:
            continue

        title, color = section_titles[bucket]
        c = ws.cell(row=row, column=1, value=title)
        c.font = Font(size=12, bold=True)
        c.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        row += 1

        # Column headers for this section
        headers = ["#", "What to do", "Who does it", "Effort", "Why it matters", "Pages affected"]
        for col, h in enumerate(headers, start=1):
            hc = ws.cell(row=row, column=col, value=h)
            hc.font = Font(bold=True, color=COLOR_HEADER_FONT)
            hc.fill = PatternFill(start_color=COLOR_HEADER, end_color=COLOR_HEADER, fill_type="solid")
        row += 1

        for idx, r in enumerate(items, start=1):
            # "What to do" — use the fix text but stripped of code snippets where possible
            what = r.fix_text or r.message
            # Replace technical jargon with plainer language. Light touch only —
            # we still want accuracy.
            ws.cell(row=row, column=1, value=idx)
            ws.cell(row=row, column=2, value=what)
            ws.cell(row=row, column=3, value=owner_for(r.check_id))
            ws.cell(row=row, column=4, value=effort_for(r.check_id))
            ws.cell(row=row, column=5, value=why_for(r.check_id))
            pages_label = ""
            if r.pages_affected > 0:
                pages_label = f"{r.pages_affected} of {r.total_pages or len(report.pages)}"
            elif r.total_pages > 0 or r.message:
                pages_label = "site-wide"
            ws.cell(row=row, column=6, value=pages_label)
            for col in (2, 5):
                ws.cell(row=row, column=col).alignment = Alignment(wrap_text=True, vertical="top")
            ws.row_dimensions[row].height = 60
            row += 1

        row += 1  # blank row between sections

    # What's already good
    passing = [r for r in report.check_results if r.verdict == Verdict.PASS]
    if passing:
        c = ws.cell(row=row, column=1, value="What's already good")
        c.font = Font(size=12, bold=True)
        c.fill = PatternFill(start_color=COLOR_PASS, end_color=COLOR_PASS, fill_type="solid")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        row += 1
        for r in passing:
            ws.cell(row=row, column=1, value="Pass")
            ws.cell(row=row, column=2, value=r.name + ": " + r.message)
            ws.cell(row=row, column=2).alignment = Alignment(wrap_text=True, vertical="top")
            ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=6)
            ws.row_dimensions[row].height = 30
            row += 1
        row += 1

    # Total effort estimate
    p1_count = len(buckets["P1"])
    p2_count = len(buckets["P2"])
    p3_count = len(buckets["P3"])
    ws.cell(row=row, column=1, value="Total scope").font = Font(size=12, bold=True)
    row += 1
    ws.cell(
        row=row, column=1,
        value=f"P1 ({p1_count} task{'s' if p1_count != 1 else ''}): rough estimate 1-2 days of agency work"
    )
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    row += 1
    ws.cell(
        row=row, column=1,
        value=f"P2 ({p2_count} task{'s' if p2_count != 1 else ''}): rough estimate 3-5 days"
    )
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    row += 1
    ws.cell(
        row=row, column=1,
        value=f"P3 ({p3_count} task{'s' if p3_count != 1 else ''}): optional polish"
    )
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    row += 2

    # How to read the other sheets
    ws.cell(row=row, column=1, value="How the rest of this file is organized").font = Font(size=12, bold=True)
    row += 1
    notes = [
        "Sheet 2 (Summary): overall score and category breakdown for the technical team or audit trail.",
        "Sheet 3 (Action List): every check with severity code (P0/P1/P2), verdict (pass/warn/fail), and the technical fix text. Good for the developer.",
        "Sheet 4 (Per-Page Detail): one row per crawled page with title, render time, schemas detected, and any issue found on that page.",
        "Sheet 5 (Score Breakdown): exactly how the overall score was calculated. Every category, every check, the weights. Auditable math.",
    ]
    for n in notes:
        ws.cell(row=row, column=1, value=n)
        ws.cell(row=row, column=1).font = Font(size=10)
        ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        ws.row_dimensions[row].height = 30
        row += 1

    row += 1
    # Pointer to the new Score Breakdown sheet
    pointer = (
        "Want to audit the math? See sheet \"Score Breakdown\" for the per-category "
        "calculation and the weights used in the overall score."
    )
    ws.cell(row=row, column=1, value=pointer)
    ws.cell(row=row, column=1).font = Font(size=10, italic=True)
    ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    ws.row_dimensions[row].height = 30
    row += 2

    # Footer
    ws.cell(row=row, column=1, value=FOOTER_LINE)
    ws.cell(row=row, column=1).font = Font(italic=True, size=9, color="6B7280")
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)

    # Column widths
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 50
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["D"].width = 18
    ws.column_dimensions["E"].width = 50
    ws.column_dimensions["F"].width = 15
    ws.freeze_panes = "A4"


def write_score_breakdown_sheet(ws, report: AuditReport) -> None:
    """Show exactly how the score was computed. Auditable math."""
    ws.title = "Score Breakdown"

    ws["A1"] = "How the score was calculated"
    ws["A1"].font = Font(size=16, bold=True)
    ws.merge_cells("A1:I1")

    intro = (
        "Each check returns one of: pass (1.0 point), warn (0.5), fail (0.0). "
        "Category score = average across all PASS+WARN+FAIL checks in that "
        "category. Overall score = weighted average across categories. "
        "NA and UNVERIFIED verdicts are excluded from the denominator (the tool "
        "refuses to guess when evidence is ambiguous)."
    )
    ws["A3"] = intro
    ws["A3"].font = Font(size=10)
    ws["A3"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells("A3:I3")
    ws.row_dimensions[3].height = 45

    headers = ["Category", "Weight", "Checks", "Pass", "Warn", "Fail", "NA/Unv", "Score", "Contribution"]
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=5, column=col, value=h)
        c.font = Font(bold=True, color=COLOR_HEADER_FONT)
        c.fill = PatternFill(start_color=COLOR_HEADER, end_color=COLOR_HEADER, fill_type="solid")

    from citable.scoring import CATEGORY_WEIGHTS
    row = 6
    total_contribution = 0.0
    weight_sum_used = 0.0
    for cat in Category:
        weight = CATEGORY_WEIGHTS.get(cat.value, 0.0)
        cat_results = [r for r in report.check_results if r.category == cat]
        passes = sum(1 for r in cat_results if r.verdict == Verdict.PASS)
        warns = sum(1 for r in cat_results if r.verdict == Verdict.WARN)
        fails = sum(1 for r in cat_results if r.verdict == Verdict.FAIL)
        na_unv = sum(1 for r in cat_results if r.verdict in (Verdict.NA, Verdict.UNVERIFIED))
        total_checks = len(cat_results)
        score = report.category_scores.get(cat.value, -1.0)
        contribution = (score * weight) if score >= 0 else 0.0
        if score >= 0:
            total_contribution += contribution
            weight_sum_used += weight

        ws.cell(row=row, column=1, value=cat.value)
        ws.cell(row=row, column=2, value=f"{weight*100:.0f}%")
        ws.cell(row=row, column=3, value=total_checks)
        ws.cell(row=row, column=4, value=passes)
        ws.cell(row=row, column=5, value=warns)
        ws.cell(row=row, column=6, value=fails)
        ws.cell(row=row, column=7, value=na_unv)
        score_cell = ws.cell(row=row, column=8, value=("n/a" if score < 0 else f"{score:.0f}"))
        if score >= 0:
            score_cell.fill = grade_fill("A" if score >= 85 else ("B" if score >= 70 else ("C" if score >= 55 else ("D" if score >= 40 else "F"))))
            score_cell.alignment = Alignment(horizontal="center")
        ws.cell(row=row, column=9, value=("excluded" if score < 0 else f"{contribution:.1f}"))
        row += 1

    # Total row
    ws.cell(row=row, column=1, value="Overall (weighted)").font = Font(bold=True)
    overall_cell = ws.cell(row=row, column=8, value=f"{report.overall_score:.0f} ({report.letter_grade})")
    overall_cell.font = Font(bold=True)
    overall_cell.fill = grade_fill(report.letter_grade)
    overall_cell.alignment = Alignment(horizontal="center")
    ws.cell(row=row, column=9, value=f"{total_contribution:.1f}").font = Font(bold=True)
    row += 2

    # Verdict guide
    ws.cell(row=row, column=1, value="Verdict guide").font = Font(size=12, bold=True)
    row += 1
    verdicts_explain = [
        ("pass", "Check is satisfied. 1.0 point."),
        ("warn", "Partially satisfied or minor issue. 0.5 point."),
        ("fail", "Real issue with measurable impact on AI visibility. 0.0 point."),
        ("na", "Check does not apply to this site (e.g. hreflang on a single-language site). Excluded from score."),
        ("unverified", "Evidence is ambiguous. citable refuses to guess. Excluded from score."),
    ]
    for verdict, explanation in verdicts_explain:
        ws.cell(row=row, column=1, value=verdict)
        ws.cell(row=row, column=1).fill = verdict_fill(Verdict(verdict))
        ws.cell(row=row, column=1).alignment = Alignment(horizontal="center")
        ws.cell(row=row, column=2, value=explanation)
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=9)
        row += 1

    row += 1
    # Audit-the-audit invitation
    audit_invite = (
        "If a category score looks wrong, the math above is the full picture. "
        "Find the check in Sheet 3 (Action List) and challenge the threshold. "
        "Every threshold is documented in the citable source code at "
        "github.com/WorkSmartAI-alt/citable/blob/main/src/citable/checks.py. "
        "This report is a starting point for a conversation, not a final verdict."
    )
    ws.cell(row=row, column=1, value=audit_invite)
    ws.cell(row=row, column=1).font = Font(size=10, italic=True, color="6B7280")
    ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=9)
    ws.row_dimensions[row].height = 60
    row += 2

    ws.cell(row=row, column=1, value=FOOTER_LINE)
    ws.cell(row=row, column=1).font = Font(italic=True, size=9, color="6B7280")
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=9)

    # Widths sized for breakdown table
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 9
    ws.column_dimensions["D"].width = 8
    ws.column_dimensions["E"].width = 8
    ws.column_dimensions["F"].width = 8
    ws.column_dimensions["G"].width = 10
    ws.column_dimensions["H"].width = 12
    ws.column_dimensions["I"].width = 15
    ws.freeze_panes = "A5"


def write_report(report: AuditReport, output_path: Path) -> Path:
    """Write the 5-sheet xlsx file. Returns the resolved output path."""
    wb = Workbook()

    # Sheet 1: Marketing-agency view (opens by default)
    action_plan = wb.active
    write_action_plan_sheet(action_plan, report)

    # Sheet 2: Technical summary
    summary = wb.create_sheet("Summary")
    write_summary_sheet(summary, report)

    # Sheet 3: Full action list
    actions = wb.create_sheet("Action List")
    write_action_sheet(actions, report)

    # Sheet 4: Per-page detail
    pages = wb.create_sheet("Per-Page Detail")
    write_pages_sheet(pages, report)

    # Sheet 5: Auditable scoring math
    breakdown = wb.create_sheet("Score Breakdown")
    write_score_breakdown_sheet(breakdown, report)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
