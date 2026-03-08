"""
infrastructure.payment.payme_provider
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Payme.uz payment gateway integration.

Flow:
1. create_invoice() -> generates Payme checkout URL with base64-encoded params
2. User pays on Payme's page
3. Payme sends JSON-RPC 2.0 calls to our endpoint:
   - CheckPerformTransaction → can we accept this payment?
   - CreateTransaction → Payme created a transaction
   - PerformTransaction → payment completed
   - CancelTransaction → payment canceled/reversed
   - CheckTransaction → status query
"""
from __future__ import annotations

import base64

from core.services.payment_provider import InvoiceResult, PaymentProvider, PaymentResult
from shared.config import PaymeSettings
from shared.logging import get_logger

log = get_logger(__name__)


class PaymePaymentProvider(PaymentProvider):
    """Payme.uz payment provider implementation."""

    def __init__(self, settings: PaymeSettings) -> None:
        self._settings = settings

    async def create_invoice(
        self,
        tenant_id: int,
        amount: int,
        currency: str,
        description: str,
        merchant_trans_id: str,
    ) -> InvoiceResult:
        """Generate Payme checkout URL.

        Payme amounts are in tiyin (1 UZS = 100 tiyin).
        """
        if not self._settings.is_configured:
            return InvoiceResult(
                success=False,
                error_message="Payme.uz is not configured",
            )

        amount_tiyin = amount * 100
        params_str = (
            f"m={self._settings.merchant_id};"
            f"ac.order_id={merchant_trans_id};"
            f"a={amount_tiyin}"
        )
        encoded = base64.b64encode(params_str.encode()).decode()
        payment_url = f"{self._settings.checkout_base_url}/{encoded}"

        log.info(
            "payme_invoice_created",
            tenant_id=tenant_id,
            merchant_trans_id=merchant_trans_id,
            amount=amount,
            amount_tiyin=amount_tiyin,
        )
        return InvoiceResult(
            success=True,
            payment_url=payment_url,
            merchant_trans_id=merchant_trans_id,
        )

    async def check_payment_status(self, transaction_id: str) -> PaymentResult:
        """Payme status is tracked via webhooks — not implemented as polling."""
        return PaymentResult(success=False, error_message="Not implemented for Payme")

    async def cancel_payment(self, transaction_id: str) -> bool:
        """Payme cancellation is handled via JSON-RPC callbacks."""
        return False

    async def verify_webhook_signature(
        self, data: dict, headers: dict,
    ) -> bool:
        """Verify Payme Basic auth header.

        Authorization: Basic base64("Paycom:{merchant_key}")
        """
        if not self._settings.merchant_key:
            return False

        auth_header = headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            return False

        try:
            decoded = base64.b64decode(auth_header[6:]).decode()
        except Exception:
            return False

        expected_key = self._settings.merchant_key.get_secret_value()
        return decoded == f"Paycom:{expected_key}"
