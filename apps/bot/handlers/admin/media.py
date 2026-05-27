"""
Admin media upload handler.
Accepts photo/video/document uploads from admin users.
"""

from __future__ import annotations

import io

from aiogram import Bot, F, Router
from aiogram.types import Message

from apps.bot.filters.role import RoleFilter
from infrastructure.storage.adapter import (
    MAX_IMAGE_SIZE,
    MAX_VIDEO_SIZE,
    get_storage_adapter,
)
from shared.constants.enums import UserRole
from shared.logging import get_logger

log = get_logger(__name__)

router = Router(name="admin:media")


@router.message(
    F.photo,
    RoleFilter(UserRole.ADMIN, UserRole.SUPERADMIN),
)
async def handle_photo_upload(message: Message, bot: Bot, **data: object) -> None:
    """Handle photo upload from admin."""
    photo = message.photo[-1]  # Highest resolution

    if photo.file_size and photo.file_size > MAX_IMAGE_SIZE:
        await message.reply("❌ Rasm hajmi 20 MB dan oshmasligi kerak.")
        return

    file = await bot.get_file(photo.file_id)
    file_bytes = io.BytesIO()
    await bot.download_file(file.file_path, file_bytes)  # type: ignore[arg-type]

    storage = get_storage_adapter()
    filename = f"photo_{photo.file_id[:16]}.jpg"
    path = await storage.upload(file_bytes.getvalue(), filename, "image/jpeg")

    await message.reply(
        f"✅ Rasm yuklandi!\n"
        f"📂 Fayl: <code>{filename}</code>\n"
        f"🔗 Telegram file_id: <code>{photo.file_id}</code>"
    )

    log.info(
        "media_uploaded",
        type="photo",
        file_id=photo.file_id,
        path=path,
        actor_id=message.from_user.id,  # type: ignore[union-attr]
    )


@router.message(
    F.video,
    RoleFilter(UserRole.ADMIN, UserRole.SUPERADMIN),
)
async def handle_video_upload(message: Message, bot: Bot, **data: object) -> None:
    """Handle video upload from admin."""
    video = message.video  # type: ignore[union-attr]

    if video.file_size and video.file_size > MAX_VIDEO_SIZE:
        await message.reply("❌ Video hajmi 50 MB dan oshmasligi kerak.")
        return

    file = await bot.get_file(video.file_id)
    file_bytes = io.BytesIO()
    await bot.download_file(file.file_path, file_bytes)  # type: ignore[arg-type]

    storage = get_storage_adapter()
    filename = f"video_{video.file_id[:16]}.mp4"
    path = await storage.upload(file_bytes.getvalue(), filename, "video/mp4")

    await message.reply(
        f"✅ Video yuklandi!\n"
        f"📂 Fayl: <code>{filename}</code>\n"
        f"🔗 Telegram file_id: <code>{video.file_id}</code>"
    )

    log.info(
        "media_uploaded",
        type="video",
        file_id=video.file_id,
        path=path,
        actor_id=message.from_user.id,  # type: ignore[union-attr]
    )


@router.message(
    F.document,
    RoleFilter(UserRole.ADMIN, UserRole.SUPERADMIN),
)
async def handle_document_upload(message: Message, bot: Bot, **data: object) -> None:
    """Handle document upload from admin."""
    doc = message.document  # type: ignore[union-attr]

    if doc.file_size and doc.file_size > MAX_IMAGE_SIZE:
        await message.reply("❌ Fayl hajmi 20 MB dan oshmasligi kerak.")
        return

    file = await bot.get_file(doc.file_id)
    file_bytes = io.BytesIO()
    await bot.download_file(file.file_path, file_bytes)  # type: ignore[arg-type]

    storage = get_storage_adapter()
    filename = doc.file_name or f"doc_{doc.file_id[:16]}"
    content_type = doc.mime_type or "application/octet-stream"
    path = await storage.upload(file_bytes.getvalue(), filename, content_type)

    await message.reply(
        f"✅ Fayl yuklandi!\n"
        f"📂 Fayl: <code>{filename}</code>\n"
        f"🔗 Telegram file_id: <code>{doc.file_id}</code>"
    )

    log.info(
        "media_uploaded",
        type="document",
        file_id=doc.file_id,
        path=path,
        actor_id=message.from_user.id,  # type: ignore[union-attr]
    )
