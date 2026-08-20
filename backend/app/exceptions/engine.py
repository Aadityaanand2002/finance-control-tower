"""Exception detection, priority scoring, and recurring pattern analysis."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import FinancialException, Settlement
from app.reconciliation.engine import (
    STATUS_DUPLICATE,
    STATUS_MATCHED,
    STATUS_MISSING_BANK,
    STATUS_MISSING_SETTLEMENT,
    STATUS_MISMATCHED,
    STATUS_PARTIAL,
    STATUS_UNEXPLAINED,
    MatchResult,
)


SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

ROOT_CAUSE_MAP = {
    STATUS_PARTIAL: "partial_settlement",
    STATUS_MISSING_BANK: "missing_bank_entry",
    STATUS_DUPLICATE: "duplicate_deduction",
    STATUS_MISSING_SETTLEMENT: "missing_settlement",
    STATUS_MISMATCHED: "settlement_mismatch",
    STATUS_UNEXPLAINED: "unknown_discrepancy",
}

ACTION_MAP = {
    "partial_settlement": "Request settlement review and create reconciliation case.",
    "missing_bank_entry": "Request supporting settlement information from bank / PSP.",
    "duplicate_deduction": "Flag duplicate bank credit and initiate reversal investigation.",
    "missing_settlement": "Chase settlement for captured payment.",
    "settlement_mismatch": "Create reconciliation case and flag settlement for finance review.",
    "unexpected_fee": "Review fee schedule and request fee breakdown from PSP.",
    "tax_difference": "Reconcile GST/tax line items against settlement advice.",
    "recurring_fee_discrepancy": "Escalate recurring fee discrepancy pattern to PSP account manager.",
    "unknown_discrepancy": "Create reconciliation case for manual investigation.",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def classify_root_cause(match: MatchResult, settlement: Optional[Settlement] = None) -> str:
    if match.status == STATUS_MISMATCHED and 40000 <= abs(match.difference) <= 70000:
        return "unexpected_fee"
    if match.status == STATUS_MISMATCHED and settlement and abs(match.difference) <= (settlement.fee + settlement.tax) * 2:
        return "tax_difference"
    return ROOT_CAUSE_MAP.get(match.status, "unknown_discrepancy")


def compute_priority(
    amount_affected: int,
    confidence: float,
    recurrence: int,
    urgency: float,
) -> tuple[float, str, list[str]]:
    """
    Priority Score = financial impact × likelihood × recurrence × urgency
    Returns (score, severity, reasons).
    """
    # Normalize impact: ₹1L (10_000_000 paise) → 1.0
    impact_norm = min(1.0, abs(amount_affected) / 10_000_000)
    likelihood = max(0.1, min(1.0, confidence))
    recurrence_factor = 1.0 + min(2.0, (recurrence - 1) * 0.35) if recurrence > 0 else 1.0
    urgency_factor = max(0.5, min(1.5, urgency))

    score = impact_norm * likelihood * recurrence_factor * urgency_factor * 100

    reasons: list[str] = []
    reasons.append(f"₹{abs(amount_affected) / 100:,.2f} affected")
    reasons.append(f"confidence of anomaly = {confidence * 100:.0f}%")
    if recurrence > 1:
        reasons.append(f"recurring {recurrence} times this period")
    if urgency >= 1.2:
        reasons.append("settlement is overdue or high-value exposure")

    if score >= 40 or abs(amount_affected) >= 4_000_000:  # ₹40,000+
        severity = SEVERITY_CRITICAL
    elif score >= 20 or abs(amount_affected) >= 50000:  # ₹500+
        severity = SEVERITY_HIGH
    elif score >= 8:
        severity = SEVERITY_MEDIUM
    else:
        severity = SEVERITY_LOW

    # Force critical for very large gaps
    if abs(amount_affected) >= 4_000_000:
        severity = SEVERITY_CRITICAL
        if "largest exposure" not in " ".join(reasons):
            reasons.append("large financial exposure relative to typical discrepancies")

    return score, severity, reasons


def find_recurring_patterns(db: Session) -> dict[str, dict]:
    """Detect recurring discrepancy bands (e.g. ₹500–₹600)."""
    exceptions = (
        db.query(FinancialException)
        .filter(FinancialException.status.in_(["open", "under_review", "action_approved"]))
        .all()
    )
    bands: dict[str, list[FinancialException]] = defaultdict(list)
    for exc in exceptions:
        # Band by 10000 paise (₹100)
        band = abs(exc.amount_affected) // 10000 * 10000
        if 40000 <= band <= 70000:  # ₹400–₹700 recurring fee pattern
            bands["fee_500_600"].append(exc)
        elif band >= 4_000_000:
            bands["high_value"].append(exc)

    patterns: dict[str, dict] = {}
    for key, group in bands.items():
        if len(group) < 2 and key != "high_value":
            continue
        amounts = [abs(e.amount_affected) for e in group]
        dates = [e.created_at for e in group if e.created_at]
        patterns[key] = {
            "label": "Recurring discrepancy pattern detected" if key == "fee_500_600" else "High-value exception cluster",
            "occurrences": len(group),
            "total_historical_impact": sum(amounts),
            "average_discrepancy": int(sum(amounts) / len(amounts)) if amounts else 0,
            "first_occurrence": min(dates).isoformat() if dates else None,
            "latest_occurrence": max(dates).isoformat() if dates else None,
            "entity_ids": [e.entity_id for e in group],
            "likely_root_cause": "unexpected_fee" if key == "fee_500_600" else "partial_settlement",
            "recommended_intervention": ACTION_MAP.get(
                "recurring_fee_discrepancy" if key == "fee_500_600" else "partial_settlement"
            ),
        }
    return patterns


def exception_type_for(status: str, root_cause: str) -> str:
    if root_cause == "unexpected_fee":
        return "fee_discrepancy"
    mapping = {
        STATUS_PARTIAL: "partial_settlement",
        STATUS_MISSING_BANK: "missing_bank_entry",
        STATUS_DUPLICATE: "duplicate",
        STATUS_MISSING_SETTLEMENT: "missing_settlement",
        STATUS_MISMATCHED: "amount_mismatch",
        STATUS_UNEXPLAINED: "unexplained",
    }
    return mapping.get(status, "financial_exception")


def upsert_exceptions_from_matches(db: Session, matches: list[MatchResult]) -> tuple[int, int]:
    created = 0
    updated = 0
    settlements = {s.id: s for s in db.query(Settlement).all()}

    # Count existing open exceptions by root-cause band for recurrence
    open_exc = db.query(FinancialException).filter(
        FinancialException.status.in_(["open", "under_review", "action_approved"])
    ).all()
    recurrence_by_band: dict[str, int] = defaultdict(int)
    for e in open_exc:
        band = abs(e.amount_affected) // 10000
        recurrence_by_band[str(band)] += 1

    for match in matches:
        if match.status == STATUS_MATCHED:
            continue
        if match.difference == 0 and match.status not in (STATUS_MISSING_BANK, STATUS_DUPLICATE, STATUS_MISSING_SETTLEMENT):
            continue

        settlement = settlements.get(match.settlement_id)
        root_cause = classify_root_cause(match, settlement)
        amount = abs(match.difference) if match.difference else abs(match.expected_amount)
        band = str(amount // 10000)
        recurrence = recurrence_by_band.get(band, 0) + 1

        urgency = 1.0
        if match.status == STATUS_MISSING_BANK:
            urgency = 1.3
        if amount >= 4_000_000:
            urgency = 1.5
        if settlement and settlement.status == "pending":
            urgency = max(urgency, 1.25)

        score, severity, reasons = compute_priority(amount, match.confidence, recurrence, urgency)
        exc_type = exception_type_for(match.status, root_cause)
        action = ACTION_MAP.get(root_cause, ACTION_MAP["unknown_discrepancy"])

        existing = (
            db.query(FinancialException)
            .filter(
                FinancialException.entity_id == match.settlement_id,
                FinancialException.status.in_(["open", "under_review", "action_approved"]),
            )
            .first()
        )

        payload = {
            "type": exc_type,
            "severity": severity,
            "amount_affected": amount,
            "expected_value": match.expected_amount,
            "actual_value": match.actual_amount,
            "explanation": match.explanation,
            "root_cause": root_cause,
            "confidence": match.confidence,
            "recommended_action": action,
            "priority_score": score,
            "priority_reasons": reasons,
            "evidence": match.signals,
            "related_payment_ids": match.payment_ids,
            "related_bank_ids": match.bank_ids,
            "requires_human_approval": True,
        }

        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
            updated += 1
        else:
            exc = FinancialException(
                id=f"exc_{uuid.uuid4().hex[:10]}",
                entity_id=match.settlement_id,
                entity_type="settlement" if not match.settlement_id.startswith("missing_for_") else "payment",
                status="open",
                created_at=_utcnow(),
                **payload,
            )
            db.add(exc)
            created += 1
            recurrence_by_band[band] = recurrence

    # Attach pattern info
    patterns = find_recurring_patterns(db)
    fee_pattern = patterns.get("fee_500_600")
    if fee_pattern:
        for e in db.query(FinancialException).filter(
            FinancialException.entity_id.in_(fee_pattern["entity_ids"])
        ).all():
            e.pattern_info = fee_pattern
            if e.root_cause == "unexpected_fee":
                e.recommended_action = ACTION_MAP["recurring_fee_discrepancy"]

    db.commit()
    return created, updated
