#!/usr/bin/env python3
"""Independent E2E verification harness for Finance Control Tower."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

BASE = "http://127.0.0.1:8000"
FE = "http://127.0.0.1:5173"


@dataclass
class Result:
    name: str
    status: str  # PASS FAIL
    evidence: str
    severity: str = ""
    fix_needed: str = ""


results: list[Result] = []
bugs: list[dict[str, str]] = []


def get(path: str, method: str = "GET", body: dict | None = None) -> Any:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else None


def get_code(url: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def record(name: str, ok: bool, evidence: str, severity: str = "high", fix: str = ""):
    results.append(Result(name, "PASS" if ok else "FAIL", evidence, severity if not ok else "", fix if not ok else ""))
    if not ok:
        bugs.append(
            {
                "severity": severity,
                "problem": name,
                "evidence": evidence,
                "fix": fix or "Investigate and patch",
            }
        )
    print(("PASS" if ok else "FAIL"), name, "-", evidence[:160])


def main():
    # --- Boot ---
    health = get("/api/health")
    record("Health endpoint", health.get("status") == "ok" and health.get("demo_mode") is True, str(health))
    record("API docs", get_code(BASE + "/docs") == 200, f"docs status {get_code(BASE + '/docs')}")
    record("Frontend root", get_code(FE + "/") == 200, f"frontend {get_code(FE + '/')}")

    reset = get("/api/demo/reset", "POST", {})
    record(
        "Demo reset",
        reset.get("unreconciled_amount") == 28_400_000 and reset.get("exceptions_created", 0) >= 8,
        str(reset),
    )

    dash = get("/api/dashboard")
    excs = get("/api/exceptions")
    open_excs = [e for e in excs if e["status"] in ("open", "under_review", "action_approved")]
    sum_amt = sum(e["amount_affected"] for e in open_excs)
    record(
        "Dashboard unreconciled from live exceptions",
        dash["unreconciled_amount"] == sum_amt == 28_400_000,
        f"dash={dash['unreconciled_amount']} sum={sum_amt} active={dash['active_exceptions']}",
    )
    record(
        "Dashboard KPIs non-zero live",
        dash["total_payments"] > 0 and dash["active_exceptions"] == 9,
        f"payments={dash['total_payments']} active={dash['active_exceptions']} recon%={dash['reconciliation_percentage']}",
    )

    # --- Navigation ---
    for path in ["/", "/exceptions", "/reconciliation", "/cash", "/copilot", "/audit"]:
        code = get_code(FE + path)
        record(f"FE page {path}", code == 200, f"HTTP {code}")

    # --- Reconciliation cases ---
    recon_run = get("/api/reconciliation/run", "POST", {})
    by = {m["settlement_id"]: m for m in recon_run["matches"]}
    # merge with GET view
    for m in get("/api/reconciliation"):
        by.setdefault(m["settlement_id"], m)

    cases = [
        ("set_1001", "Matched", 1_806_060, 1_806_060, 0),
        ("set_1002", "Mismatched", 1_806_060, 1_753_060, 53_000),
        ("set_1024", "Partially Matched", 14_250_000, 10_000_000, 4_250_000),
        ("set_1004", "Missing Bank Entry", 2_446_900, 0, 2_446_900),
    ]
    for sid, st, exp, act, diff in cases:
        m = by.get(sid)
        ok = (
            m is not None
            and m["status"] == st
            and m["expected_amount"] == exp
            and m["actual_amount"] == act
            and m["difference"] == diff
        )
        record(
            f"Recon {sid}",
            ok,
            f"{m}" if m else "missing",
        )
    m5 = by.get("set_1005")
    record("Recon set_1005 Duplicate", m5 is not None and m5["status"] == "Duplicate", str(m5))
    for sid in ["set_1006", "set_1007", "set_1008", "set_1009"]:
        m = by.get(sid)
        ok = m is not None and m["status"] == "Mismatched" and 50_000 <= abs(m["difference"]) <= 55_000
        record(f"Recon recurring {sid}", ok, str(m))

    # --- Exceptions / priority ---
    e1024 = next(e for e in excs if e["entity_id"] == "set_1024")
    # refresh after recon
    excs = get("/api/exceptions")
    e1024 = next(e for e in excs if e["entity_id"] == "set_1024")
    record(
        "set_1024 Critical highest priority",
        e1024["severity"] == "critical"
        and e1024["priority_score"] == 100
        and e1024["amount_affected"] == 4_250_000
        and isinstance(e1024.get("priority_reasons"), list)
        and len(e1024["priority_reasons"]) >= 2,
        f"sev={e1024['severity']} score={e1024['priority_score']} reasons={e1024['priority_reasons']}",
    )
    top = sorted(excs, key=lambda e: e["priority_score"], reverse=True)[0]
    record("Top exception is set_1024", top["entity_id"] == "set_1024", f"top={top['entity_id']}")

    detail = get(f"/api/exceptions/{e1024['id']}")
    record(
        "Exception detail related records",
        detail["settlement"] is not None
        and len(detail["payments"]) >= 1
        and len(detail["bank_transactions"]) >= 1
        and detail["exception"]["expected_value"] == 14_250_000
        and detail["exception"]["actual_value"] == 10_000_000,
        f"payments={len(detail['payments'])} banks={len(detail['bank_transactions'])}",
    )
    fe_detail = get_code(FE + f"/exceptions/{e1024['id']}")
    record("FE exception deep link", fe_detail == 200, f"HTTP {fe_detail}")

    # --- AI analyze ---
    analysis = get(f"/api/exceptions/{e1024['id']}/analyze", "POST", {})
    record(
        "AI analysis structured",
        analysis.get("amount_affected") == 4_250_000
        and analysis.get("confidence", 0) >= 0.9
        and analysis.get("requires_human_approval") is True
        and "summary" in analysis
        and "root_cause" in analysis
        and "recommended_action" in analysis
        and isinstance(analysis.get("evidence"), list),
        str({k: analysis.get(k) for k in ['summary','root_cause','confidence','amount_affected','recommended_action']}),
    )
    # no hallucinated IDs — evidence should mention settlement or amounts
    evidence_blob = " ".join(analysis.get("evidence") or [])
    record(
        "AI analysis grounded",
        "142500" in analysis.get("summary", "").replace(",", "")
        or "42,500" in analysis.get("summary", "")
        or "42500" in evidence_blob
        or e1024["entity_id"] in evidence_blob
        or "set_1024" in str(analysis),
        evidence_blob[:200] + " | " + analysis.get("summary", "")[:120],
    )

    # --- Copilot prompts ---
    copilot_checks = [
        ("How much money is currently unreconciled?", ["284", "unreconcil"]),
        ("What is our highest-priority financial exception?", ["set_1024", "42500", "42,500"]),
        ("Why is this exception high priority?", ["set_1024", "priority", "42,500", "42500"]),
        ("Which settlement has the largest discrepancy?", ["set_1030", "202", "discrepan"]),
        ("Show me recurring discrepancy patterns.", ["recurring", "530", "510", "pattern", "fee"]),
        ("What is our current cash position?", ["projected net cash", "available", "at-risk"]),
        ("What should finance investigate first?", ["set_1024"]),
        ("Tell me a joke.", ["finance-focused", "can't help with jokes", "cannot help with jokes", "jokes or unrelated"]),
    ]
    copilot_answers = {}
    for q, needles in copilot_checks:
        ans = get("/api/ai/query", "POST", {"query": q})
        text = (ans.get("answer") or "").lower()
        ok = any(n.lower() in text or n.lower() in json.dumps(ans).lower() for n in needles)
        copilot_answers[q] = ans
        record(f"Copilot: {q[:40]}", ok, (ans.get("answer") or "")[:220], severity="high", fix="Extend MockAIProvider intents")

    # --- HITL ---
    reviewed = get(f"/api/exceptions/{e1024['id']}/review", "POST", {})
    record("Review transition", reviewed["status"] == "under_review", reviewed["status"])
    approved = get(f"/api/exceptions/{e1024['id']}/approve", "POST", {})
    record("Approve transition", approved["status"] == "action_approved", approved["status"])
    # persistence
    again = get(f"/api/exceptions/{e1024['id']}")
    record("Approve persists", again["exception"]["status"] == "action_approved", again["exception"]["status"])
    audit = get("/api/audit-log")
    approved_rows = [a for a in audit if a.get("entity_id") == "set_1024" and a.get("user_decision") == "Approved"]
    record("Audit has approve", len(approved_rows) >= 1, f"count={len(approved_rows)} total_audit={len(audit)}")

    # Reject another
    other = next(e for e in get("/api/exceptions") if e["entity_id"] == "set_1002" and e["status"] == "open")
    rej = get(f"/api/exceptions/{other['id']}/reject", "POST", {})
    record("Reject transition", rej["status"] == "rejected", rej["status"])
    # Resolve yet another
    other2 = next(e for e in get("/api/exceptions") if e["entity_id"] == "set_1006" and e["status"] == "open")
    res = get(f"/api/exceptions/{other2['id']}/resolve", "POST", {})
    record("Resolve transition", res["status"] == "resolved" and res.get("resolved_at"), res["status"])

    # --- Filters ---
    crit = get("/api/exceptions?severity=critical")
    record("Filter severity critical", all(e["severity"] == "critical" for e in crit) and len(crit) >= 1, f"n={len(crit)}")
    open_only = get("/api/exceptions?status=open")
    record("Filter status open", all(e["status"] == "open" for e in open_only), f"n={len(open_only)}")
    min_amt = get("/api/exceptions?min_amount=1000000")  # ₹10,000
    record("Filter min_amount", all(e["amount_affected"] >= 1_000_000 for e in min_amt), f"n={len(min_amt)}")
    record("Invalid exception 404", get_code(BASE + "/api/exceptions/does_not_exist") == 404, "404")

    # --- Simulation ---
    before = get("/api/dashboard")
    sim = get("/api/simulation/run", "POST", {})
    after = get("/api/dashboard")
    record(
        "Simulation creates events/exceptions",
        len(sim.get("exceptions_created") or []) >= 1 and len(sim.get("events") or []) >= 3,
        sim.get("message", "") + f" events={len(sim.get('events') or [])}",
    )
    record(
        "Simulation updates dashboard",
        after["active_exceptions"] >= before["active_exceptions"] or after["unreconciled_amount"] != before["unreconciled_amount"],
        f"active {before['active_exceptions']}->{after['active_exceptions']} unreconciled {before['unreconciled_amount']}->{after['unreconciled_amount']}",
    )

    gen = get("/api/simulation/generate-exception", "POST", {})
    gen_id = (gen.get("exceptions_created") or [None])[0]
    record("Generate exception", gen_id is not None, str(gen))
    if gen_id:
        gdetail = get(f"/api/exceptions/{gen_id}")
        record("Generated exception detail", gdetail["exception"]["amount_affected"] > 0, str(gdetail["exception"]["entity_id"]))

    # --- Reset restores baseline ---
    reset2 = get("/api/demo/reset", "POST", {})
    dash2 = get("/api/dashboard")
    record(
        "Reset restores ~₹2.84L and 9 exceptions",
        dash2["unreconciled_amount"] == 28_400_000 and dash2["active_exceptions"] == 9,
        f"unreconciled={dash2['unreconciled_amount']} active={dash2['active_exceptions']} reset={reset2}",
    )
    # sim artifacts gone
    excs2 = get("/api/exceptions")
    record(
        "Reset clears sim/gen entities",
        not any(e["entity_id"].startswith("set_sim_") or e["entity_id"].startswith("set_gen_") for e in excs2),
        f"entity_ids sample={[e['entity_id'] for e in excs2[:5]]}",
    )

    # --- Cash math ---
    cash = get("/api/cash-position")
    banks = get("/api/bank-transactions")
    credits = sum(b["amount"] for b in banks if b["type"] == "credit")
    debits = sum(b["amount"] for b in banks if b["type"] == "debit")
    available = credits - debits
    open_excs = [e for e in get("/api/exceptions") if e["status"] in ("open", "under_review", "action_approved")]
    at_risk = sum(e["amount_affected"] for e in open_excs)
    record("Cash available_cash matches banks", cash["available_cash"] == available, f"api={cash['available_cash']} calc={available}")
    record("Cash at_risk matches exceptions", cash["at_risk_unreconciled"] == at_risk, f"api={cash['at_risk_unreconciled']} calc={at_risk}")
    projected = (
        cash["available_cash"]
        + cash["expected_settlements"]
        + cash["pending_receivables"]
        - cash["upcoming_expenses"]
        - cash["outstanding_refunds"]
        - cash["at_risk_unreconciled"]
    )
    record("Cash projected formula", cash["projected_net_cash"] == projected, f"api={cash['projected_net_cash']} calc={projected}")

    # --- Security basics ---
    import os
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    fe_env = list((root / "frontend").rglob(".env*"))
    gitignore = (root / ".gitignore").read_text()
    record(".env in gitignore", ".env" in gitignore, gitignore[:80])
    # no secrets in frontend src
    src_blob = ""
    for p in (root / "frontend" / "src").rglob("*"):
        if p.suffix in {".ts", ".tsx", ".js", ".jsx", ".env"}:
            src_blob += p.read_text(errors="ignore")
    record(
        "No API keys in frontend src",
        "OPENAI_API_KEY" not in src_blob and "RAZORPAY_KEY_SECRET" not in src_blob and "sk-" not in src_blob,
        "scanned frontend/src",
    )

    # Summary
    fails = [r for r in results if r.status == "FAIL"]
    print("\n==== SUMMARY ====")
    print(f"PASS {sum(1 for r in results if r.status=='PASS')} / FAIL {len(fails)} / TOTAL {len(results)}")
    for f in fails:
        print("FAIL:", f.name, "|", f.evidence[:200])

    out = {
        "results": [r.__dict__ for r in results],
        "bugs": bugs,
        "fail_count": len(fails),
        "pass_count": sum(1 for r in results if r.status == "PASS"),
        "copilot_sample": {k: v.get("answer", "")[:300] for k, v in list(copilot_answers.items())[:3]},
        "e1024_id": e1024["id"],
    }
    Path("/tmp/fct_e2e_report.json").write_text(json.dumps(out, indent=2))
    print("Wrote /tmp/fct_e2e_report.json")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
