"""Dashboard aggregation from live DB state."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.cash.calculator import calculate_cash_position
from app.models import ActivityEvent, FinancialException, Payment, Settlement
from app.schemas import ActivityEventOut, DashboardOut, ExceptionOut, SettlementOut


def settlement_to_out(s: Settlement, payment_ids: list[str] | None = None) -> SettlementOut:
    return SettlementOut(
        id=s.id,
        gross_amount=s.gross_amount,
        fee=s.fee,
        tax=s.tax,
        expected_amount=s.expected_amount,
        settled_amount=s.settled_amount,
        settlement_date=s.settlement_date,
        utr=s.utr,
        status=s.status,
        reconciliation_status=s.reconciliation_status,
        match_confidence=s.match_confidence,
        notes=s.notes,
        payment_ids=payment_ids or [],
    )


def build_dashboard(db: Session) -> DashboardOut:
    payments = db.query(Payment).all()
    settlements = db.query(Settlement).all()
    exceptions = db.query(FinancialException).all()
    open_exc = [e for e in exceptions if e.status in ("open", "under_review", "action_approved")]

    total_payments = sum(p.amount for p in payments)
    total_settled = sum(s.settled_amount or 0 for s in settlements if s.reconciliation_status == "Matched")
    pending_settlement = sum(
        s.expected_amount for s in settlements if s.status == "pending" or s.reconciliation_status == "Missing Bank Entry"
    )
    unreconciled = sum(e.amount_affected for e in open_exc)
    high_risk = sum(1 for e in open_exc if e.severity in ("critical", "high"))

    cash = calculate_cash_position(db)

    matched = sum(1 for s in settlements if s.reconciliation_status == "Matched")
    recon_pct = (matched / len(settlements) * 100) if settlements else 0.0

    status_dist = Counter(s.reconciliation_status or s.status for s in settlements)
    sev_dist = Counter(e.severity for e in open_exc)

    # Cash trend — last 7 days synthetic from bank-ish settlement dates
    trend = []
    now = datetime.now(timezone.utc)
    running = cash.available_cash
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date().isoformat()
        # approximate daily delta from settlements on that day
        day_settle = sum(
            (s.settled_amount or 0)
            for s in settlements
            if s.settlement_date and s.settlement_date.date().isoformat() == day
        )
        point_val = max(0, running - (6 - i) * 50_000_00 + day_settle // 10)
        trend.append({"date": day, "cash": point_val})

    recent = sorted(open_exc, key=lambda e: e.priority_score, reverse=True)[:5]
    activity = (
        db.query(ActivityEvent)
        .order_by(ActivityEvent.created_at.desc())
        .limit(15)
        .all()
    )

    return DashboardOut(
        total_payments=total_payments,
        total_settled=total_settled,
        pending_settlement=pending_settlement,
        unreconciled_amount=unreconciled,
        active_exceptions=len(open_exc),
        high_risk_exceptions=high_risk,
        expected_cash_position=cash.projected_net_cash,
        recoverable_at_risk=unreconciled,
        reconciliation_percentage=round(recon_pct, 1),
        settlement_status_distribution=dict(status_dist),
        exception_severity_distribution=dict(sev_dist),
        cash_position_trend=trend,
        recent_high_priority_exceptions=[ExceptionOut.model_validate(e) for e in recent],
        activity_stream=[ActivityEventOut.model_validate(a) for a in activity],
    )
