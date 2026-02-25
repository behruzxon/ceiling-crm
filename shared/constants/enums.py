"""
All business-domain enumerations.
Single source of truth — used by domain models, DB enums, and handlers.
"""
from __future__ import annotations
from enum import Enum


class UserRole(str, Enum):
    CLIENT     = "client"
    INSTALLER  = "installer"
    MANAGER    = "manager"
    ADMIN      = "admin"
    SUPERADMIN = "superadmin"


class CeilingCategory(str, Enum):
    GULLI         = "gulli"
    ODNOTONNY     = "odnotonny"
    MRAMOR        = "mramor"
    QORA_NAQSH_UF = "qora_naqsh_uf"
    HI_TECH       = "hi_tech"
    KOSMOS        = "kosmos"
    OSMON         = "osmon"
    OSHXONA       = "oshxona"
    NAQSH_RAMKA   = "naqsh_ramka"
    NAQSH_OQ      = "naqsh_oq"


class PipelineStage(str, Enum):
    NEW          = "NEW"
    CONTACTED    = "CONTACTED"
    MEASUREMENT  = "MEASUREMENT"
    QUOTE        = "QUOTE"
    DEAL         = "DEAL"
    INSTALLATION = "INSTALLATION"
    COMPLETED    = "COMPLETED"
    LOST         = "LOST"


class AppointmentType(str, Enum):
    MEASUREMENT  = "measurement"
    INSTALLATION = "installation"


class AppointmentStatus(str, Enum):
    SCHEDULED    = "scheduled"
    CONFIRMED    = "confirmed"
    DONE         = "done"
    CANCELLED    = "cancelled"
    RESCHEDULED  = "rescheduled"


class BroadcastStatus(str, Enum):
    DRAFT      = "draft"
    SCHEDULED  = "scheduled"
    RUNNING    = "running"
    DONE       = "done"
    FAILED     = "failed"


class LeadSource(str, Enum):
    GROUP    = "group"
    SITE     = "site"
    ADS      = "ads"
    DEEPLINK = "deeplink"
    REFERRAL = "referral"


class PaymentStatus(str, Enum):
    PENDING  = "pending"
    PAID     = "paid"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    CASH     = "cash"
    CARD     = "card"
    TRANSFER = "transfer"
