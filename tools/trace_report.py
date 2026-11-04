"""Generate the traceability matrix and verification report.

Inputs : docs/software_requirements.yaml, docs/risk_analysis.yaml, reports/results.json
Outputs: reports/traceability.md, reports/verification_report.html
Exit 1 if any requirement is uncovered or has a failing test (CI gate).
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def load():
    srs = yaml.safe_load((ROOT / "docs/software_requirements.yaml").read_text())
    rmf = yaml.safe_load((ROOT / "docs/risk_analysis.yaml").read_text())
    run = json.loads((REPORTS / "results.json").read_text())
    return srs, rmf, run


def evaluate(srs, run):
    rows = []
    for req in srs["requirements"]:
        tests = [r for r in run["results"] if req["id"] in r["requirements"]]
        if not tests:
            status = "NOT COVERED"
        elif any(t["outcome"] != "passed" for t in tests):
            status = "FAIL"
        else:
            status = "PASS"
        rows.append({**req, "tests": tests, "status": status})
    return rows


def risk_rows(rmf, req_rows):
    by_rc: dict[str, list[dict]] = {}
    for r in req_rows:
        for rc in r["risk_controls"]:
            by_rc.setdefault(rc, []).append(r)
    rows = []
    for rc in rmf["risk_controls"]:
        hazards = [h["id"] for h in rmf["hazards"] if rc["id"] in h["risk_controls"]]
        reqs = by_rc.get(rc["id"], [])
        if not reqs:
            status = "NOT COVERED"
        elif any(r["status"] != "PASS" for r in reqs):
            status = "FAIL" if any(r["status"] == "FAIL" for r in reqs) else "NOT COVERED"
        else:
            status = "PASS"
        rows.append({**rc, "hazards": hazards, "reqs": [r["id"] for r in reqs], "status": status})
    return rows


def short(test_id: str) -> str:
    return test_id.split("::", 1)[1]


def write_markdown(run, req_rows, rc_rows):
    lines = [
        "# Traceability matrix - SP-100",
        "",
        f"Run: {run['run_utc']} | Commit: {run['commit']} | Injected defect: {run['injected_defect'] or 'none'}",
        "",
        "## Requirements to tests",
        "",
        "| Requirement | Title | Class | Risk controls | Tests | Result |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in req_rows:
        tests = "<br>".join(f"{t['title'].split(' ')[0]} ({t['outcome']})" for t in r["tests"]) or "-"
        lines.append(f"| {r['id']} | {r['title']} | {r['safety_class']} | {', '.join(r['risk_controls']) or '-'} | {tests} | **{r['status']}** |")
    lines += ["", "## Risk controls to verification", "",
              "| Risk control | Measure | Hazards | Requirements | Result |", "| --- | --- | --- | --- | --- |"]
    for rc in rc_rows:
        lines.append(f"| {rc['id']} | {rc['measure']} | {', '.join(rc['hazards'])} | {', '.join(rc['reqs']) or '-'} | **{rc['status']}** |")
    (REPORTS / "traceability.md").write_text("\n".join(lines) + "\n")


CSS = """
:root{--bg:#fff;--fg:#1d1d1f;--muted:#6b6b70;--line:#e3e3e6;--pass:#1f7a3a;--passbg:#e8f5ec;--fail:#b3261e;--failbg:#fdecea;--warn:#8a5a00;--warnbg:#fff4dc}
@media (prefers-color-scheme:dark){:root{--bg:#18181a;--fg:#ececee;--muted:#a0a0a6;--line:#333338;--pass:#6fd08c;--passbg:#1e3326;--fail:#ff8a80;--failbg:#3a1f1d;--warn:#f0c060;--warnbg:#3a2f14}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1080px;margin:0 auto;padding:32px 16px}h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 8px}
.meta{color:var(--muted);font-size:13px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}
.card{border:1px solid var(--line);border-radius:10px;padding:12px 14px}.card b{display:block;font-size:24px}.card span{color:var(--muted);font-size:13px}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13.5px}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600}.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-weight:600;font-size:12px;white-space:nowrap}
.PASS,.passed{color:var(--pass);background:var(--passbg)}.FAIL,.failed{color:var(--fail);background:var(--failbg)}.NOT{color:var(--warn);background:var(--warnbg)}
code{font-size:12.5px}.msg{color:var(--fail);font-size:12.5px}
"""


def tag(status: str) -> str:
    cls = status.split(" ")[0]
    return f'<span class="tag {cls}">{html.escape(status)}</span>'


def write_html(run, req_rows, rc_rows):
    results = run["results"]
    passed = sum(r["outcome"] == "passed" for r in results)
    covered = sum(r["status"] != "NOT COVERED" for r in req_rows)
    verdict = "PASS" if all(r["status"] == "PASS" for r in req_rows) else "FAIL"
    req_html = "".join(
        f"<tr><td><b>{r['id']}</b></td><td>{html.escape(r['title'])}<br><span class='meta'>{html.escape(r['text'])}</span></td>"
        f"<td>{r['safety_class']}</td><td>{', '.join(r['risk_controls']) or '-'}</td>"
        f"<td>{'<br>'.join(html.escape(t['title']) for t in r['tests']) or '-'}</td><td>{tag(r['status'])}</td></tr>"
        for r in req_rows)
    rc_html = "".join(
        f"<tr><td><b>{rc['id']}</b></td><td>{html.escape(rc['measure'])}</td><td>{', '.join(rc['hazards'])}</td>"
        f"<td>{', '.join(rc['reqs']) or '-'}</td><td>{tag(rc['status'])}</td></tr>" for rc in rc_rows)
    test_html = "".join(
        f"<tr><td><code>{html.escape(short(t['test']))}</code><br><span class='meta'>{html.escape(t['title'])}</span>"
        + (f"<br><span class='msg'>{html.escape(t['message'])}</span>" if t["message"] else "")
        + f"</td><td>{', '.join(t['requirements'])}</td><td>{t['duration_s']} s</td><td>{tag(t['outcome'])}</td></tr>"
        for t in results)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SP-100 Verification Report</title><style>{CSS}</style></head><body><main>
<h1>SP-100 Syringe Pump - Software Verification Report</h1>
<div class="meta">VR-SP100 · Run {run['run_utc']} · Commit {run['commit']} · Injected defect: {run['injected_defect'] or 'none'} · IEC 62304 class B · Fictional device for a portfolio</div>
<div class="cards">
<div class="card"><b>{tag(verdict)}</b><span>Overall verdict</span></div>
<div class="card"><b>{passed}/{len(results)}</b><span>Test cases passed</span></div>
<div class="card"><b>{covered}/{len(req_rows)}</b><span>Requirements covered</span></div>
<div class="card"><b>{sum(rc['status'] == 'PASS' for rc in rc_rows)}/{len(rc_rows)}</b><span>Risk controls verified</span></div>
</div>
<h2>Requirements traceability</h2><div class="wrap"><table><tr><th>ID</th><th>Requirement</th><th>Class</th><th>Risk controls</th><th>Verified by</th><th>Result</th></tr>{req_html}</table></div>
<h2>Risk control verification (ISO 14971)</h2><div class="wrap"><table><tr><th>ID</th><th>Measure</th><th>Hazards</th><th>Requirements</th><th>Result</th></tr>{rc_html}</table></div>
<h2>Test case results</h2><div class="wrap"><table><tr><th>Test case</th><th>Verifies</th><th>Duration</th><th>Result</th></tr>{test_html}</table></div>
<p class="meta">CAN traces for every test case are stored in reports/traces/*.asc (Vector ASC format).</p>
</main></body></html>"""
    (REPORTS / "verification_report.html").write_text(page)
    return verdict


def main() -> int:
    srs, rmf, run = load()
    req_rows = evaluate(srs, run)
    rc_rows = risk_rows(rmf, req_rows)
    write_markdown(run, req_rows, rc_rows)
    verdict = write_html(run, req_rows, rc_rows)
    for r in req_rows:
        print(f"{r['id']:8} {r['status']:12} {len(r['tests'])} test(s)  {r['title']}")
    print(f"Verdict: {verdict}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
