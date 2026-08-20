"""Audit trail helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_action(
    db: Session,
    *,
    action: str,
    performed_by: str,
    exception_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    old_state: Optional[str] = None,
    new_state: Optional[str] = None,
    explanation: Optional[str] = None,
    ai_recommendation: Optional[str] = None,
    user_decision: Optional[str] = None,
) -> AuditLog:
    entry = AuditLog(
        id=f"aud_{uuid.uuid4().hex[:12]}",
        exception_id=exception_id,
        entity_id=entity_id,
        entity_type=entity_type,
        action=action,
        performed_by=performed_by,
        timestamp=datetime.now(timezone.utc),
        old_state=old_state,
        new_state=new_state,
        explanation=explanation,
        ai_recommendation=ai_recommendation,
        user_decision=user_decision,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
