"""
Group member status change handler.
Tracks join / leave / ban events for analytics.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import BaseFilter
from aiogram.types import ChatMemberUpdated

from infrastructure.database.session import get_session_factory
from infrastructure.di import get_group_join_repo
from shared.config import get_settings
from shared.logging import get_logger

router = Router(name="group:member_status")
log = get_logger(__name__)

# Statuses that mean "not a member" — a join transitions FROM one of these
_NOT_MEMBER = frozenset({"left", "kicked", "restricted", "banned"})
# Statuses that mean "now a member"
_IS_MEMBER = frozenset({"member", "administrator", "creator"})


class _IsMainGroup(BaseFilter):
    """Passes only for chat_member events in the configured main customer group.

    Must be a decorator-level filter rather than a runtime guard inside the
    handler body.  In aiogram 3, a handler that executes and returns ``None``
    *consumes* the update — downstream handlers (e.g. welcome_router) never
    see it.  A filter that rejects the event lets aiogram pass it to the
    next registered handler instead.
    """

    async def __call__(self, event: ChatMemberUpdated) -> bool:
        main_group_id = get_settings().bot.main_group_id
        return bool(main_group_id) and event.chat.id == main_group_id


@router.my_chat_member()
async def on_bot_status_change(event: ChatMemberUpdated, **data: object) -> None:
    """Log when the bot is added to or removed from any group."""
    log.info(
        "bot_status_changed",
        chat_id=event.chat.id,
        chat_title=event.chat.title,
        old_status=event.old_chat_member.status,
        new_status=event.new_chat_member.status,
    )


@router.chat_member(_IsMainGroup())
async def on_user_join(event: ChatMemberUpdated, **data: object) -> None:
    """Record a user joining the main customer group for join-count analytics.

    Only fires for BOT_MAIN_GROUP_ID (enforced by _IsMainGroup filter).
    Uses INSERT … ON CONFLICT DO NOTHING so re-joins are silently ignored.
    Never raises — a tracking failure must never disrupt the group.
    """
    main_group_id = get_settings().bot.main_group_id  # guaranteed non-None by filter

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    # Only record transitions from non-member → member
    if old_status not in _NOT_MEMBER or new_status not in _IS_MEMBER:
        return

    joining_user = event.new_chat_member.user
    if joining_user.id <= 0 or joining_user.is_bot:
        return

    try:
        factory = get_session_factory()
        async with factory() as session:
            await get_group_join_repo(session).upsert_join(
                group_id=main_group_id,
                user_id=joining_user.id,
                joined_at=event.date,
            )
            await session.commit()
        log.info("group_join_recorded", group_id=main_group_id, user_id=joining_user.id)
    except Exception:
        log.exception(
            "group_join_record_error",
            group_id=main_group_id,
            user_id=joining_user.id,
        )
