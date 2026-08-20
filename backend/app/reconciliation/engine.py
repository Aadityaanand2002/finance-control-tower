"""Deterministic payment → settlement → bank reconciliation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.models import BankTransaction, Payment, Settlement

# Tolerances (paise)
ROUNDING_TOLERANCE = 100  # ₹1
FEE_BAND_MIN = 100  # ₹1
DATE_WINDOW_DAYS = 2

STATUS_MATCHED = "Matched"
STATUS_PARTIAL = "Partially Matched"
STATUS_MISMATCHED = "Mismatched"
STATUS_MISSING_SETTLEMENT = "Missing Settlement"
STATUS_MISSING_BANK = "Missing Bank Entry"
STATUS_DUPLICATE = "Duplicate"
STATUS_UNEXPLAINED = "Unexplained"


@dataclass
class MatchResult:
    settlement_id: str
    payment_ids: list[str] = field(default_factory=list)
    bank_ids: list[str] = field(default_factory=list)
    status: str = STATUS_UNEXPLAINED
    expected_amount: int = 0
    actual_amount: int = 0
    difference: int = 0
    confidence: float = 0.0
    signals: list[str] = field(default_factory=list)
    explanation: str = ""


def _date_close(a, b, days: int = DATE_WINDOW_DAYS) -> bool:
    if a is None or b is None:
        return False
    # normalize timezone-naive comparison
    da = a.replace(tzinfo=None) if getattr(a, "tzinfo", None) else a
    db = b.replace(tzinfo=None) if getattr(b, "tzinfo", None) else b
    return abs((da - db).days) <= days


def _fuzzy_desc(desc: str, settlement_id: str, utr: Optional[str]) -> float:
    score = 0.0
    if settlement_id and settlement_id.lower() in (desc or "").lower():
        score = max(score, 90.0)
    if utr and utr.lower() in (desc or "").lower():
        score = max(score, 95.0)
    if utr:
        score = max(score, float(fuzz.partial_ratio(utr, desc or "")))
    return score


def match_settlement_to_banks(
    settlement: Settlement,
    banks: list[BankTransaction],
    payments: list[Payment],
) -> MatchResult:
    """Match one settlement against candidate bank transactions."""
    result = MatchResult(
        settlement_id=settlement.id,
        payment_ids=[p.id for p in payments],
        expected_amount=settlement.expected_amount,
    )
    signals: list[str] = []

    # Duplicate detection among banks with same UTR
    if settlement.utr:
        utr_matches = [b for b in banks if b.utr and b.utr == settlement.utr and b.type == "credit"]
        if len(utr_matches) > 1:
            result.bank_ids = [b.id for b in utr_matches]
            result.actual_amount = sum(b.amount for b in utr_matches)
            result.difference = result.expected_amount - utr_matches[0].amount
            result.status = STATUS_DUPLICATE
            result.confidence = 0.98
            result.signals = [f"Duplicate UTR {settlement.utr} appears {len(utr_matches)} times"]
            result.explanation = (
                f"Same UTR {settlement.utr} appears on {len(utr_matches)} bank credits. "
                f"Expected settlement ₹{settlement.expected_amount / 100:.2f}."
            )
            return result

    candidates: list[tuple[BankTransaction, float, list[str]]] = []

    for bank in banks:
        if bank.type != "credit":
            continue
        score = 0.0
        bank_signals: list[str] = []

        # UTR exact match (strongest)
        if settlement.utr and bank.utr and settlement.utr == bank.utr:
            score += 50
            bank_signals.append(f"UTR exact match ({settlement.utr})")

        # Reference / settlement id in description
        if bank.reference and settlement.id.lower() in bank.reference.lower():
            score += 20
            bank_signals.append("Settlement ID in bank reference")

        fuzzy = _fuzzy_desc(bank.description, settlement.id, settlement.utr)
        if fuzzy >= 70:
            score += min(15, fuzzy / 10)
            bank_signals.append(f"Description similarity {fuzzy:.0f}%")

        # Amount proximity
        amount_diff = abs(bank.amount - settlement.expected_amount)
        if amount_diff == 0:
            score += 25
            bank_signals.append("Exact amount match")
        elif amount_diff <= ROUNDING_TOLERANCE:
            score += 20
            bank_signals.append(f"Amount within rounding tolerance (Δ₹{amount_diff / 100:.2f})")
        elif amount_diff <= settlement.fee + settlement.tax + 10000:
            score += 10
            bank_signals.append(f"Amount within fee/tax band (Δ₹{amount_diff / 100:.2f})")
        elif bank.amount < settlement.expected_amount:
            # possible partial
            score += 5
            bank_signals.append(f"Bank credit lower than expected (Δ₹{amount_diff / 100:.2f})")

        # Date proximity
        if _date_close(bank.date, settlement.settlement_date):
            score += 10
            bank_signals.append("Date within ±2 day window")

        if score > 0:
            candidates.append((bank, score, bank_signals))

    # Require a meaningful match — avoid weak accidental associations
    candidates = [
        c for c in candidates
        if c[1] >= 40
        and (
            any("UTR exact" in s for s in c[2])
            or any("Settlement ID" in s for s in c[2])
            or any("Exact amount" in s for s in c[2])
            or any("rounding" in s for s in c[2])
            or any("fee/tax band" in s for s in c[2])
            or any("Bank credit lower" in s for s in c[2]) and any("Description" in s for s in c[2])
            or any("Description similarity" in s for s in c[2]) and c[1] >= 50
        )
    ]

    if not candidates:
        result.status = STATUS_MISSING_BANK
        result.actual_amount = 0
        result.difference = result.expected_amount
        result.confidence = 0.92
        result.signals = ["No bank credit matched UTR, amount, or description signals"]
        result.explanation = (
            f"Settlement {settlement.id} expects ₹{settlement.expected_amount / 100:.2f} "
            f"but no matching bank credit was found."
        )
        return result

    candidates.sort(key=lambda x: x[1], reverse=True)
    best_bank, best_score, best_signals = candidates[0]
    signals.extend(best_signals)

    result.bank_ids = [best_bank.id]
    result.actual_amount = best_bank.amount
    result.difference = result.expected_amount - best_bank.amount
    result.confidence = min(0.99, best_score / 100.0)
    result.signals = signals

    diff = result.difference

    if abs(diff) <= ROUNDING_TOLERANCE and best_score >= 60:
        result.status = STATUS_MATCHED
        result.explanation = (
            f"Payment → Settlement → Bank fully matched. "
            f"Expected ₹{result.expected_amount / 100:.2f}, received ₹{result.actual_amount / 100:.2f}."
        )
    elif diff > ROUNDING_TOLERANCE and best_bank.amount > 0:
        # Partial or fee mismatch
        fee_tax = settlement.fee + settlement.tax
        if 40000 <= abs(diff) <= 70000:  # recurring ~₹500-600 band in paise... wait ₹500 = 50000 paise
            result.status = STATUS_MISMATCHED
            result.explanation = (
                f"Settlement discrepancy detected: ₹{abs(diff) / 100:.2f}. "
                f"Expected ₹{result.expected_amount / 100:.2f} but received ₹{result.actual_amount / 100:.2f}."
            )
        elif best_bank.amount < settlement.expected_amount and abs(diff) > fee_tax + ROUNDING_TOLERANCE:
            # Significant shortfall → partial settlement
            if abs(diff) >= 100000:  # ≥ ₹1000 shortfall treated as partial/mismatch
                result.status = STATUS_PARTIAL if abs(diff) < settlement.expected_amount * 0.5 else STATUS_MISMATCHED
                if abs(diff) >= settlement.expected_amount * 0.25:
                    result.status = STATUS_PARTIAL
                result.explanation = (
                    f"Partial settlement detected. Expected ₹{result.expected_amount / 100:.2f}, "
                    f"bank credited ₹{result.actual_amount / 100:.2f} "
                    f"(shortfall ₹{abs(diff) / 100:.2f})."
                )
            else:
                result.status = STATUS_MISMATCHED
                result.explanation = (
                    f"Fee/tax discrepancy of ₹{abs(diff) / 100:.2f}. "
                    f"Expected ₹{result.expected_amount / 100:.2f}, received ₹{result.actual_amount / 100:.2f}."
                )
        else:
            result.status = STATUS_MISMATCHED
            result.explanation = (
                f"Amount mismatch of ₹{abs(diff) / 100:.2f} between settlement and bank credit."
            )
    elif diff < -ROUNDING_TOLERANCE:
        result.status = STATUS_MISMATCHED
        result.explanation = (
            f"Bank credit exceeds expected settlement by ₹{abs(diff) / 100:.2f}."
        )
    else:
        result.status = STATUS_UNEXPLAINED
        result.explanation = "Matching signals inconclusive; marked unexplained."

    # Boost confidence for strong UTR + amount
    if any("UTR exact" in s for s in signals):
        result.confidence = max(result.confidence, 0.85)

    return result


def detect_duplicate_banks(banks: list[BankTransaction]) -> list[MatchResult]:
    """Find duplicate bank credits by UTR independent of settlements."""
    by_utr: dict[str, list[BankTransaction]] = {}
    for b in banks:
        if b.utr and b.type == "credit":
            by_utr.setdefault(b.utr, []).append(b)

    results: list[MatchResult] = []
    for utr, group in by_utr.items():
        if len(group) > 1:
            results.append(
                MatchResult(
                    settlement_id=group[0].settlement_id or f"dup_{utr}",
                    bank_ids=[b.id for b in group],
                    status=STATUS_DUPLICATE,
                    expected_amount=group[0].amount,
                    actual_amount=sum(b.amount for b in group),
                    difference=group[0].amount,
                    confidence=0.99,
                    signals=[f"UTR {utr} duplicated {len(group)} times"],
                    explanation=f"Duplicate bank credits share UTR {utr}.",
                )
            )
    return results


def run_reconciliation(db: Session) -> list[MatchResult]:
    settlements = db.query(Settlement).all()
    banks = db.query(BankTransaction).all()
    payments = db.query(Payment).all()
    payments_by_settlement: dict[str, list[Payment]] = {}
    for p in payments:
        if p.settlement_id:
            payments_by_settlement.setdefault(p.settlement_id, []).append(p)

    results: list[MatchResult] = []
    matched_bank_ids: set[str] = set()

    for settlement in settlements:
        related_payments = payments_by_settlement.get(settlement.id, [])
        # Prefer unused banks first, but allow re-check for duplicates
        available = [b for b in banks if b.id not in matched_bank_ids or (b.utr and settlement.utr == b.utr)]
        match = match_settlement_to_banks(settlement, available if available else banks, related_payments)
        results.append(match)

        settlement.reconciliation_status = match.status
        settlement.match_confidence = match.confidence
        if match.status == STATUS_MATCHED and match.bank_ids:
            settlement.settled_amount = match.actual_amount
            settlement.status = "processed"
        elif match.status in (STATUS_MISMATCHED, STATUS_PARTIAL, STATUS_DUPLICATE, STATUS_UNEXPLAINED):
            settlement.settled_amount = match.actual_amount
            settlement.status = "mismatched"
        elif match.status == STATUS_MISSING_BANK:
            settlement.status = "pending"
            settlement.settled_amount = None

        for bid in match.bank_ids:
            matched_bank_ids.add(bid)
            bank = next((b for b in banks if b.id == bid), None)
            if bank:
                bank.settlement_id = settlement.id
                bank.reconciliation_status = match.status
                if match.status == STATUS_DUPLICATE:
                    bank.is_duplicate = True

    # Payments without settlement
    for p in payments:
        if not p.settlement_id and p.status == "captured":
            results.append(
                MatchResult(
                    settlement_id=f"missing_for_{p.id}",
                    payment_ids=[p.id],
                    status=STATUS_MISSING_SETTLEMENT,
                    expected_amount=p.amount - p.fee - p.tax,
                    actual_amount=0,
                    difference=p.amount - p.fee - p.tax,
                    confidence=0.9,
                    signals=["Captured payment has no settlement_id"],
                    explanation=f"Payment {p.id} is captured but has no linked settlement.",
                )
            )

    db.commit()
    return results
