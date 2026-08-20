"""Data provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.config import get_settings


class DataProvider(ABC):
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    def fetch_payments(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def fetch_settlements(self) -> list[dict[str, Any]]:
        ...


class MockDataProvider(DataProvider):
    def name(self) -> str:
        return "mock"

    def is_configured(self) -> bool:
        return True

    def fetch_payments(self) -> list[dict[str, Any]]:
        return []  # Seed script owns demo data

    def fetch_settlements(self) -> list[dict[str, Any]]:
        return []


class RazorpayProvider(DataProvider):
    def __init__(self, key_id: str, key_secret: str):
        self.key_id = key_id
        self.key_secret = key_secret

    def name(self) -> str:
        return "razorpay"

    def is_configured(self) -> bool:
        return bool(self.key_id and self.key_secret)

    def fetch_payments(self) -> list[dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("Razorpay credentials not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.")
        import httpx

        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                "https://api.razorpay.com/v1/payments",
                auth=(self.key_id, self.key_secret),
                params={"count": 20},
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            return [
                {
                    "id": p.get("id"),
                    "amount": p.get("amount"),
                    "currency": p.get("currency"),
                    "status": p.get("status"),
                    "method": p.get("method"),
                    "order_id": p.get("order_id"),
                    "created_at": p.get("created_at"),
                }
                for p in items
            ]

    def fetch_settlements(self) -> list[dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("Razorpay credentials not configured.")
        import httpx

        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                "https://api.razorpay.com/v1/settlements",
                auth=(self.key_id, self.key_secret),
                params={"count": 20},
            )
            # Settlements API may not be available on all accounts — degrade gracefully
            if resp.status_code >= 400:
                return []
            items = resp.json().get("items", [])
            return items


def get_data_provider() -> DataProvider:
    settings = get_settings()
    if settings.data_provider == "razorpay" and settings.razorpay_key_id and settings.razorpay_key_secret:
        return RazorpayProvider(settings.razorpay_key_id, settings.razorpay_key_secret)
    return MockDataProvider()
