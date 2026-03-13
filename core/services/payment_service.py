"""Business logic for payment records."""
from __future__ import annotations

from core.domain.payment import Payment
from core.repositories.payment_repo import AbstractPaymentRepository
from shared.constants.enums import PaymentMethod, PaymentStatus
from shared.logging import get_logger

log = get_logger(__name__)

# ── Payment state machine ────────────────────────────────────────────────────
# Keys = current status, values = set of statuses reachable from that state.
ALLOWED_TRANSITIONS: dict[PaymentStatus, frozenset[PaymentStatus]] = {
    PaymentStatus.PENDING:  frozenset({PaymentStatus.PAID, PaymentStatus.REJECTED, PaymentStatus.CANCELED}),
    PaymentStatus.PAID:     frozenset({PaymentStatus.REFUNDED}),
    PaymentStatus.CANCELED: frozenset(),
    PaymentStatus.REFUNDED: frozenset(),
    PaymentStatus.REJECTED: frozenset(),
}


def _validate_transition(current: PaymentStatus, target: PaymentStatus) -> None:
    """Raise ValueError if the transition is not allowed."""
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ValueError(
            f"Invalid payment transition: {current.value} → {target.value}"
        )


class PaymentService:

    def __init__(self, repo: AbstractPaymentRepository) -> None:
        self._repo = repo

    async def create_payment(
        self,
        *,
        lead_id: int,
        amount: int,
        method: PaymentMethod,
        notes: str | None = None,
        receipt_url: str | None = None,
        proof_file_id: str | None = None,
        created_by: int | None = None,
    ) -> Payment:
        """Record a new payment in PENDING status."""
        payment = Payment(
            id=0,  # DB assigns real id on insert
            lead_id=lead_id,
            amount=amount,
            method=method,
            status=PaymentStatus.PENDING,
            notes=notes,
            receipt_url=receipt_url,
            proof_file_id=proof_file_id,
            created_by=created_by,
        )
        created = await self._repo.create(payment)
        log.info(
            "payment_created",
            payment_id=created.id,
            lead_id=lead_id,
            amount=amount,
            method=method.value,
        )
        return created

    async def mark_paid(
        self,
        payment_id: int,
        *,
        receipt_url: str | None = None,
    ) -> Payment:
        """Transition payment PENDING → PAID and optionally attach a receipt URL."""
        payment = await self._repo.update_status(
            payment_id, PaymentStatus.PAID, expected_status=PaymentStatus.PENDING,
        )
        if receipt_url is not None:
            payment = await self._repo.update(
                Payment(**{**payment.model_dump(), "receipt_url": receipt_url})
            )
        log.info("payment_marked_paid", payment_id=payment_id)
        return payment

    async def cancel_payment(self, payment_id: int) -> Payment:
        """Transition payment PENDING → CANCELED."""
        payment = await self._repo.update_status(
            payment_id, PaymentStatus.CANCELED, expected_status=PaymentStatus.PENDING,
        )
        log.info("payment_canceled", payment_id=payment_id)
        return payment

    async def refund_payment(self, payment_id: int) -> Payment:
        """Transition payment PAID → REFUNDED."""
        payment = await self._repo.update_status(
            payment_id, PaymentStatus.REFUNDED, expected_status=PaymentStatus.PAID,
        )
        log.info("payment_refunded", payment_id=payment_id)
        return payment

    async def reject_payment(self, payment_id: int) -> Payment:
        """Transition payment PENDING → REJECTED."""
        payment = await self._repo.update_status(
            payment_id, PaymentStatus.REJECTED, expected_status=PaymentStatus.PENDING,
        )
        log.info("payment_rejected", payment_id=payment_id)
        return payment

    async def list_by_lead(self, lead_id: int) -> list[Payment]:
        return await self._repo.list_by_lead(lead_id)

    async def get_by_id(self, payment_id: int) -> Payment | None:
        return await self._repo.get_by_id(payment_id)
