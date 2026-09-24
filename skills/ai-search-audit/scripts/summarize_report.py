"""Print a citable xlsx report as compact JSON so Claude can explain it.

Usage: python summarize_report.py <report.xlsx>
Run it with the plugin venv's python (it needs openpyxl).
"""
import json
import sys

import openpyxl


def rows(ws):
    for row in ws.iter_rows(values_only=True):
        yield ["" if c is None else str(c).strip() for c in row]


def main(path: str) -> None:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = {"report": path}

    summary = [r for r in rows(wb["Summary"]) if any(r)]
    out["summary_lines"] = [" | ".join(c for c in r if c) for r in summary[:25]]

    checks = []
    action_rows = list(rows(wb["Action List"]))
    header = action_rows[0]
    for r in action_rows[1:]:
        if not any(r):
            continue
        rec = dict(zip(header, r))
        checks.append(rec)
    out["checks"] = checks
    out["open_issues"] = [c for c in checks if c.get("Verdict") in ("fail", "warn", "unverified")]

    plan = [" | ".join(c for c in r if c) for r in rows(wb["Action Plan"]) if any(r)]
    out["action_plan_lines"] = plan[:60]

    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: summarize_report.py <report.xlsx>")
    main(sys.argv[1])
