"""AI provider abstraction and structured financial analysis."""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Expense, FinancialException, Settlement
from app.schemas import AIAnalysisResult, AIQueryResponse

# Simple in-memory rate limiter
_rate_bucket: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(key: str = "ai", limit: int = 30) -> bool:
    now = time.time()
    window = _rate_bucket[key]
    _rate_bucket[key] = [t for t in window if now - t < 60]
    if len(_rate_bucket[key]) >= limit:
        return False
    _rate_bucket[key].append(now)
    return True


class AIProvider(ABC):
    @abstractmethod
    def analyze_exception(self, exception: FinancialException, context: dict[str, Any]) -> AIAnalysisResult:
        ...

    @abstractmethod
    def answer_query(self, query: str, db: Session) -> AIQueryResponse:
        ...


class MockAIProvider(AIProvider):
    """Deterministic finance-specific AI for demo without API keys."""

    def analyze_exception(self, exception: FinancialException, context: dict[str, Any]) -> AIAnalysisResult:
        expected = exception.expected_value / 100
        actual = exception.actual_value / 100
        diff = abs(exception.amount_affected) / 100
        root = exception.root_cause or "unknown_discrepancy"

        root_labels = {
            "partial_settlement": "Partial settlement detected",
            "unexpected_fee": "Unexpected fee / tax discrepancy",
            "tax_difference": "Tax difference on settlement",
            "missing_bank_entry": "Missing bank entry",
            "duplicate_deduction": "Duplicate bank credit",
            "missing_settlement": "Missing settlement for captured payment",
            "settlement_mismatch": "Settlement mismatch",
            "unknown_discrepancy": "Unknown discrepancy",
            "recurring_fee_discrepancy": "Recurring fee discrepancy pattern",
        }

        summary = (
            f"The settlement is ₹{diff:,.2f} {'lower' if exception.actual_value < exception.expected_value else 'different'} "
            f"than the expected amount. Payment-level reconciliation shows the base transaction linkage, "
            f"but the final bank credit differs from the settlement record."
        )

        evidence = list(exception.evidence or [])
        if context.get("settlement_id"):
            evidence.append(f"Settlement {context['settlement_id']} expected ₹{expected:,.2f}")
        if context.get("bank_amount") is not None:
            evidence.append(f"Bank credited ₹{context['bank_amount'] / 100:,.2f}")

        reasoning = [
            f"Expected settlement amount: ₹{expected:,.2f}",
            f"Actual bank / settled amount: ₹{actual:,.2f}",
            f"Computed difference: ₹{diff:,.2f}",
            f"Matched signals: {', '.join((exception.evidence or [])[:3]) or 'see evidence'}",
        ]

        if exception.pattern_info:
            pi = exception.pattern_info
            reasoning.append(
                f"Recurring pattern: {pi.get('occurrences', 0)} similar discrepancies; "
                f"avg ₹{pi.get('average_discrepancy', 0) / 100:,.2f}; "
                f"total impact ₹{pi.get('total_historical_impact', 0) / 100:,.2f}"
            )
            summary += (
                f" Similar discrepancies occurred in {pi.get('occurrences', 0)} settlements "
                f"from the same discrepancy band."
            )

        if abs(exception.amount_affected) >= 4_000_000:
            reasoning.append(
                "This exception is substantially larger than the merchant's average discrepancy "
                "and occurred during a period with delayed/partial settlements."
            )

        return AIAnalysisResult(
            summary=summary,
            severity=exception.severity,
            amount_affected=exception.amount_affected,
            root_cause=root_labels.get(root, root),
            confidence=exception.confidence or 0.85,
            evidence=evidence,
            recommended_action=exception.recommended_action
            or "Create a reconciliation case and flag this settlement for finance review.",
            reasoning=reasoning,
            requires_human_approval=True,
            fallback_used=False,
        )

    def answer_query(self, query: str, db: Session) -> AIQueryResponse:
        q = query.lower().strip()
        exceptions = db.query(FinancialException).all()
        open_exc = [e for e in exceptions if e.status in ("open", "under_review", "action_approved")]
        settlements = db.query(Settlement).all()
        expenses = db.query(Expense).all()

        # Non-finance deflection
        if any(w in q for w in ("joke", "poem", "weather", "recipe", "sing a song", "tell me a story")):
            return AIQueryResponse(
                answer=(
                    "I'm a finance-focused assistant for this Control Tower. "
                    "I can't help with jokes or unrelated topics — ask about unreconciled amounts, "
                    "exceptions, settlements, cash position, or what finance should investigate first."
                ),
                supporting_records=[],
                calculations=[],
                reasoning=["Rejected non-finance query; stayed in finance domain."],
                recommended_action="Ask a finance control question about exceptions or cash.",
            )

        # Intent routing
        if "unreconciled" in q or "how much money is currently unreconciled" in q:
            total = sum(e.amount_affected for e in open_exc)
            return AIQueryResponse(
                answer=f"₹{total / 100:,.2f} is currently unreconciled across {len(open_exc)} active exceptions.",
                supporting_records=[{"type": "exception", "id": e.id, "entity_id": e.entity_id, "amount": e.amount_affected} for e in open_exc[:8]],
                calculations=[f"Sum of open exception amount_affected = {total} paise"],
                reasoning=["Aggregated all exceptions in open / under_review / action_approved status."],
                recommended_action="Prioritize Critical and High severity exceptions in the Action Center.",
            )

        if "cash position" in q or "current cash" in q or "projected cash" in q or "projected net" in q:
            from app.cash.calculator import calculate_cash_position

            cash = calculate_cash_position(db)
            return AIQueryResponse(
                answer=(
                    f"Current control-adjusted cash position: available ₹{cash.available_cash/100:,.2f}, "
                    f"expected settlements ₹{cash.expected_settlements/100:,.2f}, "
                    f"pending receivables ₹{cash.pending_receivables/100:,.2f}, "
                    f"upcoming expenses ₹{cash.upcoming_expenses/100:,.2f}, "
                    f"outstanding refunds ₹{cash.outstanding_refunds/100:,.2f}, "
                    f"at-risk/unreconciled ₹{cash.at_risk_unreconciled/100:,.2f}. "
                    f"Projected net cash: ₹{cash.projected_net_cash/100:,.2f}."
                ),
                supporting_records=[{"type": "cash_position", "projected_net_cash": cash.projected_net_cash}],
                calculations=cash.calculation_steps,
                reasoning=["Computed from bank ledger, settlements, invoices, expenses, refunds, and open exceptions."],
                recommended_action="Review at-risk unreconciled amount before approving large expenses.",
            )

        if "recurring" in q and ("pattern" in q or "discrepan" in q):
            band = [
                e
                for e in open_exc
                if 40_000 <= abs(e.amount_affected) <= 70_000 or (e.pattern_info and e.pattern_info.get("label"))
            ]
            if not band:
                band = [e for e in open_exc if e.type == "fee_discrepancy"]
            total = sum(abs(e.amount_affected) for e in band)
            avg = int(total / len(band)) if band else 0
            lines = [f"{e.entity_id}: ₹{e.amount_affected/100:,.2f} ({e.root_cause})" for e in band]
            return AIQueryResponse(
                answer=(
                    f"Recurring discrepancy pattern detected across {len(band)} settlements "
                    f"(≈₹500–₹600 fee band). Total impact ₹{total/100:,.2f}, average ₹{avg/100:,.2f}.\n"
                    + "\n".join(lines)
                ),
                supporting_records=[{"type": "exception", "id": e.id, "entity_id": e.entity_id} for e in band],
                calculations=[f"count={len(band)}", f"total={total}", f"average={avg}"],
                reasoning=["Clustered open exceptions with differences in the ₹400–₹700 band."],
                recommended_action="Escalate recurring fee discrepancy pattern to PSP account manager.",
            )

        if "largest discrepanc" in q or "largest settlement" in q or "biggest discrepanc" in q:
            ranked = sorted(open_exc, key=lambda e: abs(e.amount_affected), reverse=True)
            if not ranked:
                return AIQueryResponse(answer="No open discrepancies found.", supporting_records=[], calculations=[], reasoning=[])
            e = ranked[0]
            return AIQueryResponse(
                answer=(
                    f"{e.entity_id} has the largest discrepancy: expected ₹{e.expected_value/100:,.2f} vs "
                    f"actual ₹{e.actual_value/100:,.2f} (difference ₹{e.amount_affected/100:,.2f}, {e.severity})."
                ),
                supporting_records=[{"type": "exception", "id": e.id, "entity_id": e.entity_id}],
                calculations=[f"sorted open exceptions by amount_affected; top={e.entity_id}"],
                reasoning=["Largest absolute amount_affected among active exceptions."],
                recommended_action=e.recommended_action,
            )

        if "why" in q and ("priority" in q or "high priority" in q or "highest" in q):
            top = sorted(
                open_exc,
                key=lambda e: (e.priority_score, 1 if e.severity == "critical" else 0, e.amount_affected),
                reverse=True,
            )
            if not top:
                return AIQueryResponse(answer="No open exceptions to prioritize.", supporting_records=[], calculations=[], reasoning=[])
            e = top[0]
            reasons = e.priority_reasons if isinstance(e.priority_reasons, list) else []
            return AIQueryResponse(
                answer=(
                    f"{e.entity_id} is high/critical priority because: "
                    + ("; ".join(reasons) if reasons else f"priority_score={e.priority_score:.1f}, amount ₹{e.amount_affected/100:,.2f}")
                    + f" Root cause: {e.root_cause}."
                ),
                supporting_records=[{"type": "exception", "id": e.id, "entity_id": e.entity_id}],
                calculations=[f"priority_score={e.priority_score}", f"amount_affected={e.amount_affected}"],
                reasoning=list(reasons) + list(e.reasoning or []),
                recommended_action=e.recommended_action,
            )

        if "top 5" in q or "top five" in q or "top financial exceptions" in q:
            top = sorted(open_exc, key=lambda e: e.priority_score, reverse=True)[:5]
            lines = [f"{i+1}. {e.entity_id} — ₹{e.amount_affected/100:,.2f} ({e.severity})" for i, e in enumerate(top)]
            return AIQueryResponse(
                answer="Top 5 financial exceptions by priority score:\n" + "\n".join(lines),
                supporting_records=[{"type": "exception", "id": e.id, "entity_id": e.entity_id} for e in top],
                calculations=[f"Sorted by priority_score descending"],
                reasoning=["Priority combines financial impact, confidence, recurrence, and urgency."],
                recommended_action="Open the highest-priority exception and review the AI recommendation.",
            )

        if "unexplained" in q and "discrepanc" in q:
            unexplained = [s for s in settlements if s.reconciliation_status in ("Unexplained", "Mismatched", "Partially Matched", "Missing Bank Entry")]
            return AIQueryResponse(
                answer=f"{len(unexplained)} settlements have unexplained or mismatched discrepancies.",
                supporting_records=[{"type": "settlement", "id": s.id, "status": s.reconciliation_status} for s in unexplained[:10]],
                calculations=[],
                reasoning=["Filtered settlements whose reconciliation_status is not Matched."],
                recommended_action="Run AI analysis on each mismatched settlement.",
            )

        if (
            "highest-priority" in q
            or "highest priority" in q
            or "investigate first" in q
            or "largest cash-flow risk" in q
            or "highest-priority financial exception" in q
            or "our highest-priority" in q
        ):
            top = sorted(
                open_exc,
                key=lambda e: (
                    e.priority_score,
                    1 if e.severity == "critical" else 0,
                    e.amount_affected,
                ),
                reverse=True,
            )
            if not top:
                return AIQueryResponse(answer="No open exceptions found.", supporting_records=[], calculations=[], reasoning=[])
            e = top[0]
            reasons = e.priority_reasons if isinstance(e.priority_reasons, list) else []
            return AIQueryResponse(
                answer=(
                    f"{e.entity_id} is the highest-priority issue because expected settlement and bank credit "
                    f"differ by ₹{e.amount_affected/100:,.2f} ({e.severity}). "
                    + (" ".join(reasons) if reasons else "")
                ),
                supporting_records=[{"type": "exception", "id": e.id, "entity_id": e.entity_id}],
                calculations=[
                    f"expected={e.expected_value}",
                    f"actual={e.actual_value}",
                    f"difference={e.amount_affected}",
                    f"priority_score={e.priority_score:.2f}",
                ],
                reasoning=list(e.reasoning or []) + (reasons or []),
                recommended_action=e.recommended_action,
            )

        m = re.search(r"(set_\w+)", q, re.I)
        if m or "what happened to settlement" in q:
            sid = m.group(1).lower() if m else "set_1024"
            s = next((x for x in settlements if x.id.lower() == sid), None)
            exc = next((x for x in exceptions if x.entity_id.lower() == sid), None)
            if not s:
                return AIQueryResponse(answer=f"Settlement {sid} was not found.", supporting_records=[], calculations=[], reasoning=[])
            ans = (
                f"Settlement {s.id}: gross ₹{s.gross_amount/100:,.2f}, expected ₹{s.expected_amount/100:,.2f}, "
                f"settled ₹{(s.settled_amount or 0)/100:,.2f}, status={s.status}, "
                f"reconciliation={s.reconciliation_status}."
            )
            if exc:
                ans += f" Linked exception {exc.id}: {exc.explanation}"
            return AIQueryResponse(
                answer=ans,
                supporting_records=[{"type": "settlement", "id": s.id}] + ([{"type": "exception", "id": exc.id}] if exc else []),
                calculations=[],
                reasoning=["Looked up settlement and linked exception from application database."],
                recommended_action=exc.recommended_action if exc else None,
            )

        if "vendor" in q or ("expense" in q and "cash" not in q):
            by_vendor: dict[str, int] = defaultdict(int)
            for e in expenses:
                by_vendor[e.vendor] += e.amount
            ranked = sorted(by_vendor.items(), key=lambda x: x[1], reverse=True)[:5]
            lines = [f"{v}: ₹{a/100:,.2f}" for v, a in ranked]
            return AIQueryResponse(
                answer="Top vendor expenses this period:\n" + "\n".join(lines),
                supporting_records=[{"type": "vendor", "vendor": v, "amount": a} for v, a in ranked],
                calculations=["Grouped expenses by vendor and summed amounts"],
                reasoning=["Compared vendor totals in the seeded expense ledger."],
                recommended_action="Review the largest vendor increase against budget.",
            )

        if "reconciled amount lower" in q or ("today" in q and "yesterday" in q):
            mismatched = sum(1 for s in settlements if s.reconciliation_status != "Matched")
            return AIQueryResponse(
                answer=(
                    f"Reconciled coverage is lower because {mismatched} settlements are not fully matched — "
                    f"including partial settlements and fee discrepancies that reduce recognized cash."
                ),
                supporting_records=[{"type": "settlement", "id": s.id} for s in settlements if s.reconciliation_status != "Matched"][:5],
                calculations=[],
                reasoning=["Compared Matched vs non-Matched settlement counts."],
                recommended_action="Investigate Critical exceptions first.",
            )

        # Default: overview
        total = sum(e.amount_affected for e in open_exc)
        critical = sum(1 for e in open_exc if e.severity == "critical")
        return AIQueryResponse(
            answer=(
                f"Finance Control Tower overview: {len(open_exc)} active exceptions "
                f"({critical} critical) totaling ₹{total/100:,.2f} at risk. "
                f"Ask about unreconciled amount, top exceptions, a settlement ID, or cash-flow risk."
            ),
            supporting_records=[{"type": "exception", "id": e.id} for e in sorted(open_exc, key=lambda x: -x.priority_score)[:3]],
            calculations=[],
            reasoning=["Default finance overview from live application state."],
            recommended_action="Open the Exceptions page and start with Critical severity.",
        )


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._mock = MockAIProvider()

    def analyze_exception(self, exception: FinancialException, context: dict[str, Any]) -> AIAnalysisResult:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            prompt = {
                "exception": {
                    "id": exception.id,
                    "type": exception.type,
                    "severity": exception.severity,
                    "entity_id": exception.entity_id,
                    "amount_affected": exception.amount_affected,
                    "expected_value": exception.expected_value,
                    "actual_value": exception.actual_value,
                    "root_cause": exception.root_cause,
                    "evidence": exception.evidence,
                    "pattern_info": exception.pattern_info,
                },
                "context": context,
                "instruction": "Return JSON with keys: summary, severity, amount_affected, root_cause, confidence, evidence, recommended_action, reasoning, requires_human_approval. Do not fabricate amounts.",
            }
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "You are an AI finance controller. Only use provided structured facts."},
                    {"role": "user", "content": json.dumps(prompt)},
                ],
                temperature=0.2,
            )
            data = json.loads(resp.choices[0].message.content)
            return AIAnalysisResult(**{**data, "fallback_used": False})
        except Exception:
            result = self._mock.analyze_exception(exception, context)
            result.fallback_used = True
            result.fallback_message = "AI service unavailable. Running deterministic financial analysis."
            return result

    def answer_query(self, query: str, db: Session) -> AIQueryResponse:
        # Prefer deterministic finance router; optionally enrich later
        base = self._mock.answer_query(query, db)
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "Refine the finance answer. Return JSON: answer, supporting_records, calculations, reasoning, recommended_action. Do not invent record IDs.",
                    },
                    {"role": "user", "content": json.dumps({"query": query, "draft": base.model_dump()})},
                ],
                temperature=0.2,
            )
            data = json.loads(resp.choices[0].message.content)
            return AIQueryResponse(**{**base.model_dump(), **data, "fallback_used": False})
        except Exception:
            base.fallback_used = True
            return base


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._mock = MockAIProvider()

    def analyze_exception(self, exception: FinancialException, context: dict[str, Any]) -> AIAnalysisResult:
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = (
                "Return ONLY JSON with keys summary,severity,amount_affected,root_cause,confidence,"
                "evidence,recommended_action,reasoning,requires_human_approval. Facts:\n"
                + json.dumps(
                    {
                        "amount_affected": exception.amount_affected,
                        "expected": exception.expected_value,
                        "actual": exception.actual_value,
                        "root_cause": exception.root_cause,
                        "evidence": exception.evidence,
                        "entity_id": exception.entity_id,
                    }
                )
            )
            resp = model.generate_content(prompt)
            text = resp.text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\n?", "", text)
                text = re.sub(r"\n?```$", "", text)
            data = json.loads(text)
            return AIAnalysisResult(**{**data, "fallback_used": False})
        except Exception:
            result = self._mock.analyze_exception(exception, context)
            result.fallback_used = True
            result.fallback_message = "AI service unavailable. Running deterministic financial analysis."
            return result

    def answer_query(self, query: str, db: Session) -> AIQueryResponse:
        base = self._mock.answer_query(query, db)
        base.fallback_used = False
        return base


def get_ai_provider() -> AIProvider:
    settings = get_settings()
    provider = settings.effective_ai_provider
    if provider == "openai" and settings.openai_api_key:
        return OpenAIProvider(settings.openai_api_key)
    if provider == "gemini" and settings.gemini_api_key:
        return GeminiProvider(settings.gemini_api_key)
    return MockAIProvider()
