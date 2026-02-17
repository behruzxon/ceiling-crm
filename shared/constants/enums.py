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
    MATTE_WHITE    = "matviy_oq"
    GLOSSY_WHITE   = "yaltiroq_oq"
    BLACK_PREMIUM  = "qora_premium"
    FLORAL_3D      = "gulli_3d"
    MARBLE         = "mramor_dizayn"
    LED_BACKLIGHT  = "led_podsvetka"
    STARRY_SKY     = "yulduzli_osmon"
    TWO_LEVEL      = "ikki_darajali"
    OFFICE_MINIMAL = "ofis_minimal"
    KITCHEN        = "oshxona"


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
