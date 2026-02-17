"""
Seed database with initial required data:
- 10 ceiling category groups
- Pricing config in Redis cache
- Default superadmin user
- District zone modifiers
"""
from __future__ import annotations

import asyncio
import os
from decimal import Decimal

from shared.logging import configure_logging, get_logger

log = get_logger(__name__)


# Category group definitions (chat_id must be set via env or manually)
CATEGORY_GROUPS = [
    {"category": "matviy_oq",       "title": "Matviy Oq Shiftlar"},
    {"category": "yaltiroq_oq",     "title": "Yaltiroq Oq Shiftlar"},
    {"category": "qora_premium",    "title": "Qora Premium Shiftlar"},
    {"category": "gulli_3d",        "title": "Gulli 3D Shiftlar"},
    {"category": "mramor_dizayn",   "title": "Mramor Dizayn Shiftlar"},
    {"category": "led_podsvetka",   "title": "LED Podsvetka Shiftlar"},
    {"category": "yulduzli_osmon",  "title": "Yulduzli Osmon Shiftlar"},
    {"category": "ikki_darajali",   "title": "Ikki Darajali Shiftlar"},
    {"category": "ofis_minimal",    "title": "Ofis Minimal Shiftlar"},
    {"category": "oshxona",         "title": "Oshxona Shiftlar"},
]

# Base prices per sqm (UZS) — synced with PricingService defaults
BASE_PRICES = {
    "matviy_oq":       "120000",
    "yaltiroq_oq":     "130000",
    "qora_premium":    "180000",
    "gulli_3d":        "250000",
    "mramor_dizayn":   "220000",
    "led_podsvetka":   "200000",
    "yulduzli_osmon":  "300000",
    "ikki_darajali":   "280000",
    "ofis_minimal":    "100000",
    "oshxona":         "140000",
}

# District zone modifiers (Tashkent districts)
DISTRICT_MODIFIERS = {
    "yunusobod":    "1.10",
    "mirzo_ulugbek": "1.05",
    "chilonzor":    "1.00",
    "sergeli":      "0.95",
    "yakkasaroy":   "1.15",
    "shayxontohur": "1.00",
    "olmazor":      "1.00",
    "uchtepa":      "0.95",
    "mirobod":      "1.10",
    "bektemir":     "0.90",
    "yashnobod":    "0.95",
}


async def seed() -> None:
    configure_logging()
    log.info("seeding_database")

    from infrastructure.cache.client import connect_redis, get_redis
    from infrastructure.database.session import connect_database, get_session_factory
    from infrastructure.database.models.user import UserModel
    from shared.constants.enums import UserRole

    await connect_database()
    await connect_redis()

    # ── Seed pricing config to Redis ────────────────────────────────────
    cache = get_redis()

    for category, price in BASE_PRICES.items():
        await cache.set(f"price:{category}", price)
    log.info("seeded_base_prices", count=len(BASE_PRICES))

    for district, modifier in DISTRICT_MODIFIERS.items():
        await cache.set(f"district_mod:{district}", modifier)
    log.info("seeded_district_modifiers", count=len(DISTRICT_MODIFIERS))

    # ── Seed superadmin user ────────────────────────────────────────────
    superadmin_id = os.environ.get("SUPERADMIN_TELEGRAM_ID")
    if superadmin_id:
        factory = get_session_factory()
        async with factory() as session:
            from sqlalchemy.dialects.postgresql import insert

            stmt = insert(UserModel).values(
                id=int(superadmin_id),
                first_name="Superadmin",
                role=UserRole.SUPERADMIN.value,
                language_code="uz",
            ).on_conflict_do_update(
                index_elements=["id"],
                set_={"role": UserRole.SUPERADMIN.value},
            )
            await session.execute(stmt)
            await session.commit()
            log.info("seeded_superadmin", telegram_id=superadmin_id)
    else:
        log.warning("SUPERADMIN_TELEGRAM_ID not set — skipping superadmin creation")

    log.info("seeding_complete")


if __name__ == "__main__":
    asyncio.run(seed())
