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
    NEW              = "NEW"
    PACKAGE_SELECTED = "PACKAGE_SELECTED"
    CONTACTED        = "CONTACTED"
    MEASUREMENT      = "MEASUREMENT"
    QUOTE            = "QUOTE"
    DEAL             = "DEAL"
    INSTALLATION     = "INSTALLATION"
    COMPLETED        = "COMPLETED"
    LOST             = "LOST"


class PackageType(str, Enum):
    STANDARD = "standard"
    PREMIUM  = "premium"
    VIP      = "vip"


class LeadStatus(str, Enum):
    HOT  = "hot"
    WARM = "warm"
    COLD = "cold"


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
    PENDING    = "pending"
    SCHEDULED  = "scheduled"
    RUNNING    = "running"
    DONE       = "done"
    FAILED     = "failed"
    CANCELLED  = "cancelled"


class SegmentType(str, Enum):
    ALL_PRIVATE    = "all_private"    # all non-blocked private users
    LEAD_STAGE     = "lead_stage"     # users whose latest pipeline stage == X
    ADMIN_GROUPS   = "admin_groups"   # bot's tracked admin/announcement groups


class PayloadType(str, Enum):
    TEXT    = "text"
    PHOTO   = "photo"
    VIDEO   = "video"
    DOCUMENT = "document"


class LeadSource(str, Enum):
    GROUP    = "group"
    SITE     = "site"
    ADS      = "ads"
    DEEPLINK = "deeplink"
    REFERRAL = "referral"


class LostReason(str, Enum):
    PRICE          = "price"
    COMPETITOR     = "competitor"
    NO_RESPONSE    = "no_response"
    NOT_INTERESTED = "not_interested"
    OTHER          = "other"


class PaymentStatus(str, Enum):
    PENDING  = "pending"
    PAID     = "paid"
    CANCELED = "canceled"
    REFUNDED = "refunded"
    REJECTED = "rejected"


class PaymentMethod(str, Enum):
    CASH     = "cash"
    CARD     = "card"
    TRANSFER = "transfer"
    MANUAL   = "manual"   # bot-submitted payment awaiting admin approval
