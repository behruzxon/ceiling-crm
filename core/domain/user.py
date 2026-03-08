"""User domain model."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field
from shared.constants.enums import UserRole


class User(BaseModel):
    """Immutable domain representation of a Telegram user."""
    model_config = {"frozen": True}

    id: int                                    # Telegram user_id
    username: str | None = None
    first_name: str
    last_name: str | None = None
    phone: str | None = None
    language_code: str = "uz"
    role: UserRole = UserRole.CLIENT
    source: str | None = None
    is_blocked: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime | None = None
    tenant_id: int | None = None

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name

    def has_role(self, *roles: UserRole) -> bool:
        return self.role in roles
