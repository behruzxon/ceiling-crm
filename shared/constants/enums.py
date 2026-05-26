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


class AgentCustomerState(str, Enum):
    NEW_VISITOR         = "new_visitor"
    BROWSING_CATALOG    = "browsing_catalog"
    DESIGN_INTERESTED   = "design_interested"
    PRICE_CHECKING      = "price_checking"
    PRICE_CONSIDERING   = "price_considering"
    ORDER_INTENT        = "order_intent"
    ORDER_ABANDONED     = "order_abandoned"
    PHONE_SHARED_HOT    = "phone_shared_hot"
    OPERATOR_HANDOFF    = "operator_handoff"
    NEGOTIATING_PRICE   = "negotiating_price"
    INACTIVE_WARM       = "inactive_warm"
    INACTIVE_COLD       = "inactive_cold"
    STOPPED             = "stopped"
    LOST                = "lost"
    CLOSED              = "closed"


class AgentActionType(str, Enum):
    WAIT                     = "wait"
    SEND_CATALOG_FOLLOWUP    = "send_catalog_followup"
    SEND_PRICE_FOLLOWUP      = "send_price_followup"
    SEND_ORDER_FOLLOWUP      = "send_order_followup"
    SUGGEST_PRICE_CALCULATOR = "suggest_price_calculator"
    SUGGEST_ORDER            = "suggest_order"
    SUGGEST_OPERATOR         = "suggest_operator"
    NOTIFY_ADMIN             = "notify_admin"
    MARK_HOT_LEAD            = "mark_hot_lead"
    DISABLE_FOLLOWUP         = "disable_followup"
    ESCALATE_TO_ADMIN        = "escalate_to_admin"
    REQUEST_PHONE            = "request_phone"
    REQUEST_AREA             = "request_area"
    REQUEST_DESIGN_CHOICE    = "request_design_choice"


class JourneyEventType(str, Enum):
    STARTED_BOT           = "started_bot"
    OPENED_CATALOG        = "opened_catalog"
    VIEWED_CATALOG_ITEM   = "viewed_catalog_item"
    USED_PRICE_CALCULATOR = "used_price_calculator"
    PRICE_CALCULATED      = "price_calculated"
    CLICKED_ORDER         = "clicked_order"
    ORDER_FORM_STARTED    = "order_form_started"
    ORDER_FORM_ABANDONED  = "order_form_abandoned"
    PHONE_SHARED          = "phone_shared"
    LOCATION_SHARED       = "location_shared"
    IMAGE_SENT            = "image_sent"
    OPERATOR_REQUESTED    = "operator_requested"
    ADMIN_NOTIFIED        = "admin_notified"
    DEAL_CLOSED           = "deal_closed"
    LOST_LEAD             = "lost_lead"


class CustomerIntent(str, Enum):
    WANTS_PRICE             = "wants_price"
    WANTS_CATALOG           = "wants_catalog"
    WANTS_ORDER             = "wants_order"
    WANTS_OPERATOR          = "wants_operator"
    WANTS_MEASUREMENT       = "wants_measurement"
    WANTS_DISCOUNT          = "wants_discount"
    WANTS_INSTALLATION_TIME = "wants_installation_time"
    WANTS_LOCATION_SERVICE  = "wants_location_service"
    SENDS_OBJECTION         = "sends_objection"
    STOP_REQUEST            = "stop_request"
    UNCLEAR                 = "unclear"


class ObjectionType(str, Enum):
    PRICE                  = "price"
    TIME                   = "time"
    TRUST                  = "trust"
    NEED_CONSULTATION      = "need_consultation"
    COMPARING              = "comparing"
    NOT_READY              = "not_ready"
    LOCATION               = "location"
    SPOUSE_FAMILY_DECISION = "spouse_family_decision"
    UNKNOWN                = "unknown"


class UrgencyLevel(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class OfferType(str, Enum):
    PRICE_CALCULATION      = "price_calculation"
    CHEAPER_OPTION         = "cheaper_option"
    PREMIUM_OPTION         = "premium_option"
    MEASUREMENT_VISIT      = "measurement_visit"
    OPERATOR_CONSULTATION  = "operator_consultation"
    WARRANTY_TRUST         = "warranty_trust"
    PORTFOLIO_SOCIAL_PROOF = "portfolio_social_proof"
    FAST_INSTALLATION      = "fast_installation"
    DESIGN_HELP            = "design_help"
    ORDER_CONTINUE         = "order_continue"
    DISCOUNT_DISCUSSION    = "discount_discussion"
    CALLBACK_REQUEST       = "callback_request"
    NO_OFFER               = "no_offer"


class OfferCTA(str, Enum):
    ASK_AREA               = "ask_area"
    ASK_DESIGN_TYPE        = "ask_design_type"
    OPEN_PRICE_CALCULATOR  = "open_price_calculator"
    CONTINUE_ORDER         = "continue_order"
    CONTACT_OPERATOR       = "contact_operator"
    SHOW_CATALOG           = "show_catalog"
    SEND_PHOTO             = "send_photo"
    REQUEST_PHONE          = "request_phone"
    WAIT                   = "wait"
    STOP                   = "stop"


class OfferPriority(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"
    URGENT = "urgent"


class ConversationPolicyAction(str, Enum):
    NO_ACTION         = "no_action"
    REPLY_NOW         = "reply_now"
    SCHEDULE_FOLLOWUP = "schedule_followup"
    CANCEL_FOLLOWUPS  = "cancel_followups"
    ESCALATE_ADMIN    = "escalate_admin"
    HANDOFF_OPERATOR  = "handoff_operator"
    WAIT_AND_OBSERVE  = "wait_and_observe"
    DISABLE_AGENT     = "disable_agent"
    STORE_ONLY        = "store_only"


class ConversationChannel(str, Enum):
    USER_DM       = "user_dm"
    ADMIN_GROUP   = "admin_group"
    INTERNAL_ONLY = "internal_only"
    NONE          = "none"


class ConversationRiskLevel(str, Enum):
    NONE   = "none"
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class AgentOrchestratorSource(str, Enum):
    USER_MESSAGE   = "user_message"
    JOURNEY_EVENT  = "journey_event"
    FOLLOWUP_DUE   = "followup_due"
    ADMIN_ACTION   = "admin_action"
    SCHEDULER_TICK = "scheduler_tick"


class AgentOrchestratorAction(str, Enum):
    NO_ACTION         = "no_action"
    SEND_USER_REPLY   = "send_user_reply"
    SCHEDULE_FOLLOWUP = "schedule_followup"
    CANCEL_FOLLOWUPS  = "cancel_followups"
    SEND_ADMIN_ALERT  = "send_admin_alert"
    HANDOFF_OPERATOR  = "handoff_operator"
    DISABLE_AGENT     = "disable_agent"
    STORE_MEMORY_ONLY = "store_memory_only"


class AgentExecutionMode(str, Enum):
    LOG_ONLY          = "log_only"
    DRY_RUN           = "dry_run"
    CANARY            = "canary"
    APPROVAL_REQUIRED = "approval_required"
    LIVE              = "live"


class AgentExecutionStatus(str, Enum):
    PROPOSED    = "proposed"
    APPROVED    = "approved"
    REJECTED    = "rejected"
    EXECUTED    = "executed"
    BLOCKED     = "blocked"
    FAILED      = "failed"
    ROLLED_BACK = "rolled_back"
    EXPIRED     = "expired"


class AgentExecutionRisk(str, Enum):
    NONE     = "none"
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"
