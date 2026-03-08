"""
infrastructure.payment.click_provider
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Click.uz payment gateway integration.

Flow:
1. create_invoice() -> generates Click payment URL
2. User pays on Click's page
3. Click sends PREPARE callback (action=0) -> validate, mark PREPARING
4. Click sends COMPLETE callback (action=1) -> validate, mark PAID
"""
from __future__ import annotations

import hashlib
from urllib.parse import urlencode

from core.services.payment_provider import InvoiceResult, PaymentProvider, PaymentResult
from shared.config import ClickSettings
from shared.logging import get_logger

log = get_logger(__name__)

_CLICK_PAY_URL = "https://my.click.uz/services/pay"


class ClickPaymentProvider(PaymentProvider):
    """Click.uz payment provider implementation."""

    def __init__(self, settings: ClickSettings) -> None:
        self._settings = settings

    async def create_invoice(
        self,
        tenant_id: int,
        amount: int,
        currency: str,
        description: str,
        merchant_trans_id: str,
    ) -> InvoiceResult:
        """Build Click payment URL for the user to open."""
        if not self._settings.is_configured:
            return InvoiceResult(
                success=False,
                error_message="Click.uz is not configured",
            )

        params = {
            "service_id": self._settings.service_id,
            "merchant_id": self._settings.merchant_id,
            "amount": amount,
            "transaction_param": merchant_trans_id,
        }
        payment_url = f"{_CLICK_PAY_URL}?{urlencode(params)}"

        log.info(
            "click_invoice_created",
            tenant_id=tenant_id,
            merchant_trans_id=merchant_trans_id,
            amount=amount,
        )
        return InvoiceResult(
            success=True,
            payment_url=payment_url,
            merchant_trans_id=merchant_trans_id,
        )

    async def check_payment_status(self, transaction_id: str) -> PaymentResult:
        """Click doesn't provide a simple status API — return unknown."""
        return PaymentResult(success=False, error_message="Not implemented for Click")

    async def cancel_payment(self, transaction_id: str) -> bool:
        """Click payments cannot be cancelled via API."""
        return False

    async def verify_webhook_signature(
        self, data: dict, headers: dict,
    ) -> bool:
        """Verify Click callback MD5 signature.

        Signature = MD5(click_trans_id + service_id + secret_key
                        + merchant_trans_id + amount + action + sign_time)
        """
        if not self._settings.secret_key:
            return False

        sign_string = data.get("sign_string", "")
        expected = self._compute_signature(data)
        return sign_string == expected

    def _compute_signature(self, data: dict) -> str:
        """Compute expected MD5 signature for a Click callback."""
        secret = self._settings.secret_key.get_secret_value()
        parts = [
            str(data.get("click_trans_id", "")),
            str(self._settings.service_id),
            secret,
            str(data.get("merchant_trans_id", "")),
            str(data.get("amount", "")),
            str(data.get("action", "")),
            str(data.get("sign_time", "")),
        ]
        raw = "".join(parts)
        return hashlib.md5(raw.encode()).hexdigest()  # noqa: S324
