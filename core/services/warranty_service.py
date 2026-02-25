"""Business logic for warranty records."""
from __future__ import annotations

from datetime import date

from core.domain.warranty import Warranty
from core.repositories.warranty_repo import AbstractWarrantyRepository
from shared.logging import get_logger

log = get_logger(__name__)

_WARRANTY_YEARS = 15


def _calc_expires_at(issued_at: date) -> date:
    """Return issued_at + 15 years, handling Feb-29 edge case gracefully."""
    try:
        return issued_at.replace(year=issued_at.year + _WARRANTY_YEARS)
    except ValueError:
        # issued_at is Feb 29 in a leap year; roll forward to Mar 1
        return date(issued_at.year + _WARRANTY_YEARS, 3, 1)


class WarrantyService:

    def __init__(self, repo: AbstractWarrantyRepository) -> None:
        self._repo = repo

    async def issue_warranty(
        self,
        *,
        lead_id: int,
        issued_at: date,
        created_by: int,
        warranty_card_no: str | None = None,
        notes: str | None = None,
    ) -> Warranty:
        """
        Issue a 15-year warranty for *lead_id*.
        Raises IntegrityError (propagated) if a warranty for this lead already exists.
        """
        expires_at = _calc_expires_at(issued_at)
        warranty = Warranty(
            id=0,  # DB assigns real id on insert
            lead_id=lead_id,
            issued_at=issued_at,
            expires_at=expires_at,
            warranty_card_no=warranty_card_no,
            notes=notes,
            created_by=created_by,
        )
        created = await self._repo.create(warranty)
        log.info(
            "warranty_issued",
            warranty_id=created.id,
            lead_id=lead_id,
            issued_at=str(issued_at),
            expires_at=str(expires_at),
        )
        return created

    async def get_by_lead(self, lead_id: int) -> Warranty | None:
        return await self._repo.get_by_lead(lead_id)

    async def get_by_id(self, warranty_id: int) -> Warranty | None:
        return await self._repo.get_by_id(warranty_id)
