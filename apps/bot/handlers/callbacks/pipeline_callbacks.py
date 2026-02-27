"""
Pipeline stage transition callbacks.
Handles stage advancement buttons on lead cards.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from infrastructure.database.session import get_session_factory
from infrastructure.di import get_crm_service, get_lead_action_repo
from shared.constants.enums import PipelineStage
from shared.exceptions.base import (
    InvalidStageTransitionError,
    MissingLostReasonError,
    NotFoundError,
)
from shared.utils.formatting import bold

router = Router(name="callbacks:pipeline")


@router.callback_query(F.data.startswith("pipeline:advance:"))
async def cb_advance_stage(callback: CallbackQuery, **data: object) -> None:
    """Show valid next stages for the lead and let admin pick."""
    lead_id = int(callback.data.split(":")[-1])  # type: ignore[union-attr]

    factory = get_session_factory()
    async with factory() as session:
        crm = get_crm_service(session)
        from infrastructure.di import get_lead_repo

        lead_repo = get_lead_repo(session)
        lead = await lead_repo.get_by_id(lead_id)
        if lead is None:
            await callback.answer("Lid topilmadi", show_alert=True)
            return

        valid_next = crm.get_valid_transitions(lead.current_stage)
        if not valid_next:
            await callback.answer("Bu bosqichdan o'tish mumkin emas", show_alert=True)
            return

        buttons = [
            [InlineKeyboardButton(
                text=f"➡️ {stage.value}",
                callback_data=f"pipeline:do_advance:{lead_id}:{stage.value}",
            )]
            for stage in valid_next
            if stage != PipelineStage.LOST  # LOST has separate button
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(  # type: ignore[union-attr]
            f"📊 Lid #{lead_id}\n"
            f"Hozirgi: {bold(lead.current_stage.value)}\n\n"
            "Keyingi bosqichni tanlang:",
            reply_markup=keyboard,
        )
        await callback.answer()


@router.callback_query(F.data.startswith("pipeline:do_advance:"))
async def cb_do_advance(callback: CallbackQuery, **data: object) -> None:
    """Execute stage transition."""
    parts = callback.data.split(":")  # type: ignore[union-attr]
    lead_id = int(parts[2])
    new_stage = PipelineStage(parts[3])
    actor_id = callback.from_user.id

    factory = get_session_factory()
    async with factory() as session:
        try:
            crm = get_crm_service(session)
            lead = await crm.advance_stage(lead_id, new_stage, actor_id)

            # Semantic action log — fire-and-forget (never raises)
            if new_stage == PipelineStage.MEASUREMENT:
                _action = "measurement_set"
            elif new_stage in (PipelineStage.DEAL, PipelineStage.QUOTE):
                _action = "order_done"
            else:
                _action = "status_changed"
            await get_lead_action_repo(session).insert(
                lead_id, actor_id, _action, payload={"new": new_stage.value}
            )

            await session.commit()

            await callback.message.edit_text(  # type: ignore[union-attr]
                f"✅ Lid #{lead_id} → {bold(new_stage.value)}"
            )
            await callback.answer("Bosqich o'zgartirildi!")
        except InvalidStageTransitionError as e:
            await callback.answer(str(e), show_alert=True)
        except NotFoundError:
            await callback.answer("Lid topilmadi", show_alert=True)
        except Exception:
            await session.rollback()
            await callback.answer("Xatolik yuz berdi", show_alert=True)
            raise


@router.callback_query(F.data.startswith("pipeline:lost:"))
async def cb_mark_lost(callback: CallbackQuery, **data: object) -> None:
    """Mark lead as LOST. Requires reason note."""
    lead_id = int(callback.data.split(":")[-1])  # type: ignore[union-attr]
    actor_id = callback.from_user.id

    # For now, use a default reason. A proper implementation would
    # prompt for a reason via inline reply or FSM.
    factory = get_session_factory()
    async with factory() as session:
        try:
            crm = get_crm_service(session)
            await crm.advance_stage(
                lead_id, PipelineStage.LOST, actor_id,
                note="Yo'qotildi (admin paneldan belgilangan)",
            )
            await get_lead_action_repo(session).insert(
                lead_id, actor_id, "status_changed", payload={"new": PipelineStage.LOST.value}
            )
            await session.commit()

            await callback.message.edit_text(  # type: ignore[union-attr]
                f"❌ Lid #{lead_id} → {bold('LOST')}"
            )
            await callback.answer("Lid yo'qotildi deb belgilandi")
        except InvalidStageTransitionError as e:
            await callback.answer(str(e), show_alert=True)
        except NotFoundError:
            await callback.answer("Lid topilmadi", show_alert=True)
        except Exception:
            await session.rollback()
            await callback.answer("Xatolik yuz berdi", show_alert=True)
            raise
