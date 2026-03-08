"""
core.services.payment_provider
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Abstract payment provider interface.

Concrete implementations (Click, Payme) live in ``infrastructure/payment/``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PaymentResult:
    """Outcome of a payment status check."""

    success: bool
    transaction_id: str | None = None
    error_message: str | None = None
    paid_at: datetime | None = None
    amount: int = 0          # in minor currency units (e.g., tiyin for UZS)
    currency: str = "UZS"


@dataclass(frozen=True)
class InvoiceResult:
    """Outcome of invoice creation."""

    success: bool
    payment_url: str | None = None
    merchant_trans_id: str | None = None
    error_message: str | None = None


class PaymentProvider(ABC):
    """Interface for payment processing integrations.

    Concrete implementations:
    - ClickPaymentProvider  (Click.uz)
    - PaymePaymentProvider  (Payme.uz)
    """

    @abstractmethod
    async def create_invoice(
        self,
        tenant_id: int,
        amount: int,
        currency: str,
        description: str,
        merchant_trans_id: str,
    ) -> InvoiceResult:
        """Create a payment invoice. Returns an InvoiceResult with payment URL."""
        ...

    @abstractmethod
    async def check_payment_status(self, transaction_id: str) -> PaymentResult:
        """Query the payment provider for the status of a transaction."""
        ...

    @abstractmethod
    async def cancel_payment(self, transaction_id: str) -> bool:
        """Cancel a pending payment. Returns True if successfully cancelled."""
        ...

    @abstractmethod
    async def verify_webhook_signature(
        self, data: dict, headers: dict,
    ) -> bool:
        """Verify that the incoming webhook is authentically from the provider."""
        ...
