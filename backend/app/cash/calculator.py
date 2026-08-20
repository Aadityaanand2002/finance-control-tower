"""Cash position and control-adjusted projections."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import BankTransaction, Expense, FinancialException, Invoice, Refund, Settlement
from app.schemas import CashPositionOut


def calculate_cash_position(db: Session) -> CashPositionOut:
    # Available cash ≈ sum of credit bank txs - debit bank txs (simplified ledger)
    credits = db.query(BankTransaction).filter(BankTransaction.type == "credit").all()
    debits = db.query(BankTransaction).filter(BankTransaction.type == "debit").all()
    available_cash = sum(b.amount for b in credits) - sum(b.amount for b in debits)

    # Expected settlements still pending / mismatched net expected
    pending_settlements = (
        db.query(Settlement)
        .filter(Settlement.status.in_(["pending", "mismatched", "processed"]))
        .all()
    )
    expected_settlements = 0
    for s in pending_settlements:
        if s.status == "pending" or s.reconciliation_status in (
            "Missing Bank Entry",
            "Partially Matched",
            "Mismatched",
        ):
            # remaining expected credit
            already = s.settled_amount or 0
            expected_settlements += max(0, s.expected_amount - already)

    # Pending receivables from unpaid invoices
    invoices = db.query(Invoice).all()
    pending_receivables = sum(max(0, inv.amount - inv.paid_amount) for inv in invoices if inv.status != "paid")

    # Upcoming expenses (unpaid)
    expenses = db.query(Expense).filter(Expense.payment_status.in_(["pending", "due", "scheduled"])).all()
    upcoming_expenses = sum(e.amount for e in expenses)

    # Outstanding refunds
    refunds = db.query(Refund).filter(Refund.status.in_(["pending", "processed"])).all()
    outstanding_refunds = sum(r.amount for r in refunds if r.status == "pending")

    # At-risk / unreconciled from open exceptions
    open_exc = db.query(FinancialException).filter(
        FinancialException.status.in_(["open", "under_review", "action_approved"])
    ).all()
    at_risk = sum(e.amount_affected for e in open_exc)

    projected = available_cash + expected_settlements + pending_receivables - upcoming_expenses - outstanding_refunds - at_risk

    steps = [
        f"Available Cash: ₹{available_cash / 100:,.2f}",
        f"+ Expected Settlements: ₹{expected_settlements / 100:,.2f}",
        f"+ Pending Receivables: ₹{pending_receivables / 100:,.2f}",
        f"− Upcoming Expenses: ₹{upcoming_expenses / 100:,.2f}",
        f"− Outstanding Refunds: ₹{outstanding_refunds / 100:,.2f}",
        f"− At-Risk/Unreconciled: ₹{at_risk / 100:,.2f}",
        f"= Projected Net Cash: ₹{projected / 100:,.2f}",
    ]

    return CashPositionOut(
        available_cash=available_cash,
        expected_settlements=expected_settlements,
        pending_receivables=pending_receivables,
        upcoming_expenses=upcoming_expenses,
        outstanding_refunds=outstanding_refunds,
        at_risk_unreconciled=at_risk,
        projected_net_cash=projected,
        calculation_steps=steps,
    )
