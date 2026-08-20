"""Backend unit and API tests."""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

# Ensure backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

os.environ["DATABASE_URL"] = "sqlite:///./test_finance_control_tower.db"
os.environ["AI_PROVIDER"] = "mock"
os.environ["DEMO_MODE"] = "true"

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.reconciliation.engine import (  # noqa: E402
    STATUS_MATCHED,
    STATUS_MISSING_BANK,
    STATUS_PARTIAL,
    match_settlement_to_banks,
)
from app.exceptions.engine import compute_priority  # noqa: E402
from app.cash.calculator import calculate_cash_position  # noqa: E402
from app.services.seed import seed_database  # noqa: E402
from app.models import BankTransaction, Settlement  # noqa: E402
from datetime import datetime, timezone  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_perfect_match():
    settlement = Settlement(
        id="set_t1",
        gross_amount=100000,
        fee=1000,
        tax=180,
        expected_amount=98820,
        settlement_date=datetime.now(timezone.utc),
        utr="UTRT1",
        status="pending",
    )
    bank = BankTransaction(
        id="bank_t1",
        date=datetime.now(timezone.utc),
        description="NEFT set_t1",
        reference="set_t1",
        amount=98820,
        type="credit",
        utr="UTRT1",
        bank="HDFC",
    )
    result = match_settlement_to_banks(settlement, [bank], [])
    assert result.status == STATUS_MATCHED
    assert result.difference == 0


def test_partial_and_fee_discrepancy():
    settlement = Settlement(
        id="set_t2",
        gross_amount=14250000,
        fee=0,
        tax=0,
        expected_amount=14250000,
        settlement_date=datetime.now(timezone.utc),
        utr="UTRT2",
        status="pending",
    )
    bank = BankTransaction(
        id="bank_t2",
        date=datetime.now(timezone.utc),
        description="NEFT SET_T2",
        reference="set_t2",
        amount=10000000,
        type="credit",
        utr="UTRT2",
        bank="HDFC",
    )
    result = match_settlement_to_banks(settlement, [bank], [])
    assert result.status == STATUS_PARTIAL
    assert result.difference == 4250000


def test_missing_bank():
    settlement = Settlement(
        id="set_t3",
        gross_amount=500000,
        fee=0,
        tax=0,
        expected_amount=500000,
        settlement_date=datetime.now(timezone.utc),
        utr="UTRNONE",
        status="pending",
    )
    result = match_settlement_to_banks(settlement, [], [])
    assert result.status == STATUS_MISSING_BANK


def test_priority_critical_for_large_amount():
    score, severity, reasons = compute_priority(4_250_000, 0.94, 1, 1.5)
    assert severity == "critical"
    assert score > 0
    assert any("42,500" in r or "42500" in r or "affected" in r for r in reasons)


def test_seed_and_dashboard(client):
    db = SessionLocal()
    try:
        result = seed_database(db)
        assert result["exceptions_created"] >= 1
        assert result["unreconciled_amount"] > 200_000_00  # ~₹2L+
    finally:
        db.close()
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    body = res.json()
    assert body["unreconciled_amount"] > 0
    assert body["active_exceptions"] > 0


def test_exception_approve_creates_audit(client):
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    exc = client.get("/api/exceptions").json()
    critical = next(e for e in exc if e["entity_id"] == "set_1024")
    res = client.post(f"/api/exceptions/{critical['id']}/approve", json={})
    assert res.status_code == 200
    assert res.json()["status"] == "action_approved"
    audit = client.get("/api/audit-log").json()
    assert any(a["user_decision"] == "Approved" and a["entity_id"] == "set_1024" for a in audit)


def test_ai_query(client):
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    res = client.post("/api/ai/query", json={"query": "How much money is currently unreconciled?"})
    assert res.status_code == 200
    assert "₹" in res.json()["answer"] or "unreconciled" in res.json()["answer"].lower()


def test_simulation(client):
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    before = client.get("/api/dashboard").json()["active_exceptions"]
    res = client.post("/api/simulation/run")
    assert res.status_code == 200
    after = client.get("/api/dashboard").json()["active_exceptions"]
    assert after >= before


def test_cash_calculation():
    db = SessionLocal()
    try:
        seed_database(db)
        cash = calculate_cash_position(db)
        assert cash.calculation_steps
        assert isinstance(cash.projected_net_cash, int)
    finally:
        db.close()


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
