"""
apps.bot.webhooks.click_webhook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
HTTP handlers for Click.uz payment callbacks.

Click sends two callbacks per payment:
- PREPARE (action=0): "Can you accept this payment?"
- COMPLETE (action=1): "Payment was successful."

Both arrive as application/x-www-form-urlencoded POST requests.

Response format (JSON):
    click_trans_id, merchant_trans_id, merchant_prepare_id/merchant_confirm_id,
    error, error_note
"""
from __future__ import annotations

from aiohttp import web

from infrastructure.database.session import get_session_factory
from infrastructure.di import get_subscription_billing_service
from infrastructure.payment.click_provider import ClickPaymentProvider
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)

# Click error codes
_OK = 0
_SIGN_ERROR = -1
_BAD_REQUEST = -2
_NOT_FOUND = -5
_ALREADY_PAID = -4
_CANCELLED = -9


async def click_prepare_handler(request: web.Request) -> web.Response:
    """Handle Click PREPARE callback (action=0).

    Validates signature, checks merchant_trans_id exists, confirms amount.
    """
    data = dict(await request.post())

    click_trans_id = data.get("click_trans_id", "")
    merchant_trans_id = data.get("merchant_trans_id", "")

    log.info("click_prepare_received", merchant_trans_id=merchant_trans_id)

    # 1. Verify signature
    settings = get_settings()
    provider = ClickPaymentProvider(settings.click)
    if not await provider.verify_webhook_signature(data, dict(request.headers)):
        log.warning("click_prepare_bad_signature", merchant_trans_id=merchant_trans_id)
        return web.json_response({
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "error": _SIGN_ERROR,
            "error_note": "Invalid signature",
        })

    # 2. Look up payment
    factory = get_session_factory()
    async with factory() as session:
        svc = get_subscription_billing_service(session)
        payment = await svc.get_by_merchant_trans_id(merchant_trans_id)

        if payment is None:
            return web.json_response({
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "error": _NOT_FOUND,
                "error_note": "Transaction not found",
            })

        # 3. Check amount matches
        try:
            click_amount = float(data.get("amount", 0))
        except (TypeError, ValueError):
            click_amount = 0
        if int(click_amount) != payment.amount:
            return web.json_response({
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "error": _BAD_REQUEST,
                "error_note": "Amount mismatch",
            })

        # 4. Check if already paid
        from shared.constants.enums import SubscriptionPaymentStatus
        if payment.status == SubscriptionPaymentStatus.PAID:
            return web.json_response({
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "error": _ALREADY_PAID,
                "error_note": "Already paid",
            })

        # 5. Mark PREPARING
        await svc.handle_prepare(
            merchant_trans_id=merchant_trans_id,
            provider_trans_id=str(click_trans_id),
            provider_meta={"sign_time": data.get("sign_time")},
        )
        await session.commit()

    return web.json_response({
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "merchant_prepare_id": payment.id,
        "error": _OK,
        "error_note": "Success",
    })


async def click_complete_handler(request: web.Request) -> web.Response:
    """Handle Click COMPLETE callback (action=1).

    On success: marks payment PAID, extends tenant subscription.
    """
    data = dict(await request.post())

    click_trans_id = data.get("click_trans_id", "")
    merchant_trans_id = data.get("merchant_trans_id", "")
    error_code = int(data.get("error", 0))

    log.info(
        "click_complete_received",
        merchant_trans_id=merchant_trans_id,
        error=error_code,
    )

    # 1. Verify signature
    settings = get_settings()
    provider = ClickPaymentProvider(settings.click)
    if not await provider.verify_webhook_signature(data, dict(request.headers)):
        log.warning("click_complete_bad_signature", merchant_trans_id=merchant_trans_id)
        return web.json_response({
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "error": _SIGN_ERROR,
            "error_note": "Invalid signature",
        })

    # 2. Look up payment
    factory = get_session_factory()
    async with factory() as session:
        svc = get_subscription_billing_service(session)
        payment = await svc.get_by_merchant_trans_id(merchant_trans_id)

        if payment is None:
            return web.json_response({
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "error": _NOT_FOUND,
                "error_note": "Transaction not found",
            })

        # 3. If Click reports an error, mark as failed
        if error_code < 0:
            await svc.handle_payment_failure(
                merchant_trans_id=merchant_trans_id,
                error_message=f"Click error: {error_code}",
                provider_meta={"click_error": error_code},
            )
            await session.commit()
            return web.json_response({
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "error": error_code,
                "error_note": "Payment failed",
            })

        # 4. Mark PAID and extend subscription
        from shared.constants.enums import SubscriptionPaymentStatus
        if payment.status == SubscriptionPaymentStatus.PAID:
            return web.json_response({
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "merchant_confirm_id": payment.id,
                "error": _ALREADY_PAID,
                "error_note": "Already paid",
            })

        await svc.handle_payment_success(
            merchant_trans_id=merchant_trans_id,
            provider_trans_id=str(click_trans_id),
            provider_meta={
                "sign_time": data.get("sign_time"),
                "click_trans_id": click_trans_id,
            },
        )
        await session.commit()

    return web.json_response({
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "merchant_confirm_id": payment.id,
        "error": _OK,
        "error_note": "Success",
    })


def setup_click_routes(app: web.Application) -> None:
    """Register Click.uz webhook routes on the aiohttp application."""
    app.router.add_post("/webhooks/click/prepare", click_prepare_handler)
    app.router.add_post("/webhooks/click/complete", click_complete_handler)
