"""Typed exception hierarchy for the entire application."""

from __future__ import annotations


class CeilingCRMError(Exception):
    """Base exception for all application errors."""

    pass


class NotFoundError(CeilingCRMError):
    """Entity not found in the database."""

    def __init__(self, entity: str, id: int | str) -> None:
        super().__init__(f"{entity} with id={id} not found")
        self.entity = entity
        self.id = id


class PermissionDeniedError(CeilingCRMError):
    """User lacks required role/permission."""

    def __init__(self, role: str, permission: str) -> None:
        super().__init__(f"Role {role!r} lacks permission {permission!r}")


class InvalidStageTransitionError(CeilingCRMError):
    """Attempted an invalid CRM pipeline stage transition."""

    def __init__(self, from_stage: str, to_stage: str) -> None:
        super().__init__(f"Cannot transition from {from_stage!r} to {to_stage!r}")


class MissingLostReasonError(CeilingCRMError):
    """LOST stage transition requires a reason note."""

    pass


class DuplicateEntityError(CeilingCRMError):
    """Entity already exists (unique constraint)."""

    pass


class ValidationError(CeilingCRMError):
    """Business rule validation failed."""

    pass


class RateLimitExceededError(CeilingCRMError):
    """User has exceeded their request rate limit."""

    def __init__(self, user_id: int, remaining_seconds: int) -> None:
        super().__init__(f"User {user_id} rate limited for {remaining_seconds}s")
        self.user_id = user_id
        self.remaining_seconds = remaining_seconds
