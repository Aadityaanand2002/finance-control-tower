"""Demo narrative priority overrides for set_1024 centerpiece."""

from sqlalchemy.orm import Session

from app.models import FinancialException


def apply_demo_narrative_overrides(db: Session) -> None:
    """Keep set_1024 as Critical demo centerpiece after reconciliation upserts."""
    exc_1024 = db.query(FinancialException).filter(FinancialException.entity_id == "set_1024").first()
    if exc_1024 and exc_1024.status in ("open", "under_review", "action_approved"):
        exc_1024.severity = "critical"
        exc_1024.priority_score = 100.0
        exc_1024.root_cause = "partial_settlement"
        exc_1024.recommended_action = "Request settlement review"
        if not exc_1024.priority_reasons:
            exc_1024.priority_reasons = [
                "₹42,500.00 affected",
                "large financial exposure relative to typical discrepancies",
                "confidence of anomaly = 94%",
                "settlement is overdue or high-value exposure",
            ]
        exc_1024.confidence = max(exc_1024.confidence or 0, 0.94)

    exc_1030 = db.query(FinancialException).filter(FinancialException.entity_id == "set_1030").first()
    if exc_1030 and exc_1030.status in ("open", "under_review", "action_approved"):
        # Remains material for ~₹2.84L unreconciled, but below set_1024 for demo focus
        exc_1030.severity = "high"
        exc_1030.priority_score = min(float(exc_1030.priority_score or 0), 70.0)

    db.commit()
