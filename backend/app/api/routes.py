import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit.service import log_action
from app.ai.provider import check_rate_limit, get_ai_provider
from app.cash.calculator import calculate_cash_position
from app.core.config import get_settings
from app.core.database import get_db
from app.core.timeutil import to_iso_z, utc_now
from app.exceptions.engine import upsert_exceptions_from_matches
from app.exceptions.demo_overrides import apply_demo_narrative_overrides
from app.reconciliation.engine import run_reconciliation
from app.models import (
    ActivityEvent,
    AuditLog,
    BankTransaction,
    Expense,
    FinancialException,
    Invoice,
    Payment,
    Refund,
    Settlement,
)
from app.schemas import (
    ActionRequest,
    AIAnalysisResult,
    AIQueryRequest,
    AIQueryResponse,
    AuditLogOut,
    BankTransactionOut,
    CashPositionOut,
    DashboardOut,
    ExceptionDetailOut,
    ExceptionOut,
    ExpenseOut,
    HealthOut,
    InvoiceOut,
    PaymentOut,
    ReconciliationMatchOut,
    ReconciliationRunResult,
    RefundOut,
    SettlementOut,
    SimulationResult,
)
from app.services.dashboard import build_dashboard, settlement_to_out
from app.services.seed import seed_database
from app.simulation.engine import generate_new_exception, run_simulation
from app.providers.base import get_data_provider

router = APIRouter(prefix="/api")


def _payment_ids_for(db: Session, settlement_id: str) -> list[str]:
    return [p.id for p in db.query(Payment).filter(Payment.settlement_id == settlement_id).all()]


@router.get("/health", response_model=HealthOut)
def health():
    settings = get_settings()
    provider = get_data_provider()
    return HealthOut(
        status="ok",
        demo_mode=settings.demo_mode,
        ai_provider=settings.effective_ai_provider,
        data_provider=provider.name(),
        database="connected",
    )


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)):
    return build_dashboard(db)


@router.get("/payments", response_model=list[PaymentOut])
def list_payments(db: Session = Depends(get_db)):
    return db.query(Payment).order_by(Payment.created_at.desc()).all()


@router.get("/settlements", response_model=list[SettlementOut])
def list_settlements(db: Session = Depends(get_db)):
    rows = db.query(Settlement).order_by(Settlement.settlement_date.desc()).all()
    return [settlement_to_out(s, _payment_ids_for(db, s.id)) for s in rows]


@router.get("/settlements/{settlement_id}", response_model=SettlementOut)
def get_settlement(settlement_id: str, db: Session = Depends(get_db)):
    s = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not s:
        raise HTTPException(404, "Settlement not found")
    return settlement_to_out(s, _payment_ids_for(db, s.id))


@router.get("/bank-transactions", response_model=list[BankTransactionOut])
def list_banks(db: Session = Depends(get_db)):
    return db.query(BankTransaction).order_by(BankTransaction.date.desc()).all()


@router.get("/invoices", response_model=list[InvoiceOut])
def list_invoices(db: Session = Depends(get_db)):
    return db.query(Invoice).all()


@router.get("/expenses", response_model=list[ExpenseOut])
def list_expenses(db: Session = Depends(get_db)):
    return db.query(Expense).order_by(Expense.date.desc()).all()


@router.get("/refunds", response_model=list[RefundOut])
def list_refunds(db: Session = Depends(get_db)):
    return db.query(Refund).all()


@router.get("/exceptions", response_model=list[ExceptionOut])
def list_exceptions(
    severity: Optional[str] = None,
    type: Optional[str] = Query(None, alias="type"),
    status: Optional[str] = None,
    min_amount: Optional[int] = None,
    max_amount: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(FinancialException)
    if severity:
        q = q.filter(FinancialException.severity == severity.lower())
    if type:
        q = q.filter(FinancialException.type == type)
    if status:
        q = q.filter(FinancialException.status == status)
    if min_amount is not None:
        q = q.filter(FinancialException.amount_affected >= min_amount)
    if max_amount is not None:
        q = q.filter(FinancialException.amount_affected <= max_amount)
    return q.order_by(FinancialException.priority_score.desc()).all()


@router.get("/exceptions/{exception_id}", response_model=ExceptionDetailOut)
def get_exception(exception_id: str, db: Session = Depends(get_db)):
    exc = db.query(FinancialException).filter(FinancialException.id == exception_id).first()
    if not exc:
        raise HTTPException(404, "Exception not found")

    settlement = db.query(Settlement).filter(Settlement.id == exc.entity_id).first()
    payments = []
    banks = []
    if settlement:
        payments = db.query(Payment).filter(Payment.settlement_id == settlement.id).all()
        banks = db.query(BankTransaction).filter(
            (BankTransaction.settlement_id == settlement.id)
            | (BankTransaction.utr == settlement.utr)
        ).all()
    elif exc.related_payment_ids:
        payments = db.query(Payment).filter(Payment.id.in_(exc.related_payment_ids)).all()
    if exc.related_bank_ids:
        extra = db.query(BankTransaction).filter(BankTransaction.id.in_(exc.related_bank_ids)).all()
        existing = {b.id for b in banks}
        banks.extend([b for b in extra if b.id not in existing])

    audit = (
        db.query(AuditLog)
        .filter(AuditLog.exception_id == exc.id)
        .order_by(AuditLog.timestamp.desc())
        .all()
    )

    timeline = []
    for p in payments:
        timeline.append({"at": to_iso_z(p.created_at), "label": f"Payment {p.id} captured", "kind": "payment"})
    if settlement:
        timeline.append({"at": to_iso_z(settlement.settlement_date), "label": f"Settlement {settlement.id}", "kind": "settlement"})
    for b in banks:
        timeline.append({"at": to_iso_z(b.date), "label": f"Bank {b.id} {b.type} ₹{b.amount/100:.2f}", "kind": "bank"})
    timeline.append({"at": to_iso_z(exc.created_at), "label": "Exception detected", "kind": "exception"})
    timeline.sort(key=lambda x: x["at"] or "")

    return ExceptionDetailOut(
        exception=ExceptionOut.model_validate(exc),
        payments=[PaymentOut.model_validate(p) for p in payments],
        settlement=settlement_to_out(settlement, [p.id for p in payments]) if settlement else None,
        bank_transactions=[BankTransactionOut.model_validate(b) for b in banks],
        audit_trail=[AuditLogOut.model_validate(a) for a in audit],
        timeline=timeline,
    )


@router.post("/reconciliation/run", response_model=ReconciliationRunResult)
def reconciliation_run(db: Session = Depends(get_db)):
    try:
        matches = run_reconciliation(db)
        created, updated = upsert_exceptions_from_matches(db, matches)
        apply_demo_narrative_overrides(db)
        return ReconciliationRunResult(
            matches=[
                ReconciliationMatchOut(
                    settlement_id=m.settlement_id,
                    payment_ids=m.payment_ids,
                    bank_ids=m.bank_ids,
                    status=m.status,
                    expected_amount=m.expected_amount,
                    actual_amount=m.actual_amount,
                    difference=m.difference,
                    confidence=m.confidence,
                    signals=m.signals,
                    explanation=m.explanation,
                )
                for m in matches
            ],
            exceptions_created=created,
            exceptions_updated=updated,
            message=f"Reconciled {len(matches)} records; created {created}, updated {updated} exceptions.",
        )
    except Exception as e:
        raise HTTPException(500, f"Reconciliation failure: {e}") from e


@router.post("/exceptions/{exception_id}/analyze", response_model=AIAnalysisResult)
def analyze_exception(exception_id: str, db: Session = Depends(get_db)):
    if not check_rate_limit("ai_analyze", get_settings().ai_rate_limit_per_minute):
        raise HTTPException(429, "AI rate limit exceeded. Try again shortly.")
    exc = db.query(FinancialException).filter(FinancialException.id == exception_id).first()
    if not exc:
        raise HTTPException(404, "Exception not found")
    settlement = db.query(Settlement).filter(Settlement.id == exc.entity_id).first()
    banks = []
    if settlement:
        banks = db.query(BankTransaction).filter(BankTransaction.settlement_id == settlement.id).all()
    context = {
        "settlement_id": exc.entity_id,
        "bank_amount": banks[0].amount if banks else exc.actual_value,
    }
    ai = get_ai_provider()
    result = ai.analyze_exception(exc, context)
    exc.explanation = result.summary
    exc.root_cause = result.root_cause
    exc.confidence = result.confidence
    exc.recommended_action = result.recommended_action
    exc.evidence = result.evidence
    exc.reasoning = result.reasoning
    exc.severity = result.severity if result.severity else exc.severity
    db.commit()
    log_action(
        db,
        action="AI analysis completed",
        performed_by="AI Finance Controller",
        exception_id=exc.id,
        entity_id=exc.entity_id,
        entity_type="settlement",
        old_state=exc.status,
        new_state=exc.status,
        explanation=result.summary,
        ai_recommendation=result.recommended_action,
    )
    return result


def _transition(
    db: Session,
    exception_id: str,
    new_status: str,
    decision: str,
    action_label: str,
    body: ActionRequest,
):
    settings = get_settings()
    exc = db.query(FinancialException).filter(FinancialException.id == exception_id).first()
    if not exc:
        raise HTTPException(404, "Exception not found")
    old = exc.status
    exc.status = new_status
    if new_status == "resolved":
        exc.resolved_at = utc_now()
    db.commit()
    user = body.performed_by or settings.demo_user
    log_action(
        db,
        action=action_label,
        performed_by=user,
        exception_id=exc.id,
        entity_id=exc.entity_id,
        entity_type=exc.entity_type,
        old_state=old,
        new_state=new_status,
        explanation=body.note or action_label,
        ai_recommendation=exc.recommended_action,
        user_decision=decision,
    )
    db.add(
        ActivityEvent(
            id=f"act_{uuid.uuid4().hex[:12]}",
            event_type="action",
            message=f"{action_label} on {exc.entity_id}",
            entity_id=exc.entity_id,
            created_at=utc_now(),
        )
    )
    db.commit()
    return ExceptionOut.model_validate(exc)


@router.post("/exceptions/{exception_id}/review", response_model=ExceptionOut)
def review_exception(exception_id: str, body: ActionRequest = ActionRequest(), db: Session = Depends(get_db)):
    return _transition(db, exception_id, "under_review", "Reviewed", "Marked under review", body)


@router.post("/exceptions/{exception_id}/approve", response_model=ExceptionOut)
def approve_exception(exception_id: str, body: ActionRequest = ActionRequest(), db: Session = Depends(get_db)):
    return _transition(
        db,
        exception_id,
        "action_approved",
        "Approved",
        "Reconciliation case created / action approved",
        body,
    )


@router.post("/exceptions/{exception_id}/reject", response_model=ExceptionOut)
def reject_exception(exception_id: str, body: ActionRequest = ActionRequest(), db: Session = Depends(get_db)):
    return _transition(db, exception_id, "rejected", "Rejected", "AI recommendation rejected", body)


@router.post("/exceptions/{exception_id}/resolve", response_model=ExceptionOut)
def resolve_exception(exception_id: str, body: ActionRequest = ActionRequest(), db: Session = Depends(get_db)):
    return _transition(db, exception_id, "resolved", "Resolved", "Exception marked resolved", body)


@router.post("/exceptions/{exception_id}/finance-request", response_model=ExceptionOut)
def finance_request(exception_id: str, body: ActionRequest = ActionRequest(), db: Session = Depends(get_db)):
    return _transition(
        db,
        exception_id,
        "action_approved",
        "Approved",
        "Finance request generated — supporting settlement information requested",
        body,
    )


@router.get("/audit-log", response_model=list[AuditLogOut])
def audit_log(
    entity_id: Optional[str] = None,
    user: Optional[str] = None,
    decision: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)
    if entity_id:
        q = q.filter(AuditLog.entity_id == entity_id)
    if user:
        q = q.filter(AuditLog.performed_by.like(f"%{user}%"))
    if decision:
        q = q.filter(AuditLog.user_decision == decision)
    return q.order_by(AuditLog.timestamp.desc()).limit(200).all()


@router.get("/cash-position", response_model=CashPositionOut)
def cash_position(db: Session = Depends(get_db)):
    return calculate_cash_position(db)


@router.post("/simulation/run", response_model=SimulationResult)
def simulation_run(db: Session = Depends(get_db)):
    return run_simulation(db)


@router.post("/simulation/generate-exception", response_model=SimulationResult)
def simulation_generate(db: Session = Depends(get_db)):
    return generate_new_exception(db)


@router.post("/demo/reset")
def demo_reset(db: Session = Depends(get_db)):
    result = seed_database(db)
    return {"message": "Demo reset complete", **result}


@router.post("/ai/query", response_model=AIQueryResponse)
def ai_query(body: AIQueryRequest, db: Session = Depends(get_db)):
    if not check_rate_limit("ai_query", get_settings().ai_rate_limit_per_minute):
        raise HTTPException(429, "AI rate limit exceeded. Try again shortly.")
    # Sanitize
    query = body.query.strip()[:2000]
    if not query:
        raise HTTPException(400, "Query cannot be empty")
    ai = get_ai_provider()
    try:
        return ai.answer_query(query, db)
    except Exception as e:
        raise HTTPException(503, f"AI unavailable: {e}") from e


@router.get("/activity", response_model=list)
def activity(db: Session = Depends(get_db)):
    rows = db.query(ActivityEvent).order_by(ActivityEvent.created_at.desc()).limit(30).all()
    return [
        {
            "id": r.id,
            "event_type": r.event_type,
            "message": r.message,
            "entity_id": r.entity_id,
            "created_at": to_iso_z(r.created_at),
        }
        for r in rows
    ]


@router.get("/reconciliation", response_model=list[ReconciliationMatchOut])
def reconciliation_view(db: Session = Depends(get_db)):
    settlements = db.query(Settlement).all()
    result = []
    for s in settlements:
        payments = db.query(Payment).filter(Payment.settlement_id == s.id).all()
        banks = db.query(BankTransaction).filter(
            (BankTransaction.settlement_id == s.id) | (BankTransaction.utr == s.utr)
        ).all()
        expected = s.expected_amount
        actual = s.settled_amount if s.settled_amount is not None else (banks[0].amount if banks else 0)
        result.append(
            ReconciliationMatchOut(
                settlement_id=s.id,
                payment_ids=[p.id for p in payments],
                bank_ids=[b.id for b in banks],
                status=s.reconciliation_status or "Unexplained",
                expected_amount=expected,
                actual_amount=actual,
                difference=expected - actual,
                confidence=s.match_confidence or 0.0,
                signals=[],
                explanation=s.notes or "",
            )
        )
    return result
