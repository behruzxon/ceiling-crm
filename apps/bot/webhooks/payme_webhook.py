"""
apps.bot.webhooks.payme_webhook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
HTTP handler for Payme.uz JSON-RPC 2.0 callbacks.

Single endpoint ``/webhooks/payme`` handles all Payme method calls:
- CheckPerformTransaction
- CreateTransaction
- PerformTransaction
- CancelTransaction
- CheckTransaction

Authentication: Basic auth with ``Paycom:{merchant_key}``.

All responses follow JSON-RPC 2.0:
  {"jsonrpc": "2.0", "id": <id>, "result": {...}}
  {"jsonrpc": "2.0", "id": <id>, "error": {"code": <N>, "message": {...}}}
"""
from __future__ import annotations

import time
from typing import Any

from aiohttp import web

from infrastructure.database.session import get_session_factory
from infrastructure.di import get_subscription_billing_service
from infrastructure.payment.payme_provider import PaymePaymentProvider
from shared.config import get_settings
from shared.constants.enums import SubscriptionPaymentStatus
from shared.logging import get_logger

log = get_logger(__name__)

# Payme JSON-RPC error codes
_ERR_TRANSPORT = -32300
_ERR_SERVER = -32400
_ERR_METHOD_NOT_FOUND = -32601
_ERR_INVALID_PARAMS = -31050
_ERR_CANT_PERFORM = -31001
_ERR_ALREADY_DONE = -31008
_ERR_TRANSACTION_NOT_FOUND = -31003


def _ok(rpc_id: Any, result: dict) -> web.Response:
    return web.json_response({"jsonrpc": "2.0", "id": rpc_id, "result": result})


def _err(rpc_id: Any, code: int, message: str) -> web.Response:
    return web.json_response({
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": {"code": code, "message": {"uz": message, "ru": message, "en": message}},
    })


async def payme_jsonrpc_handler(request: web.Request) -> web.Response:
    """Handle all Payme JSON-RPC 2.0 method calls."""
    # 1. Verify auth
    settings = get_settings()
    provider = PaymePaymentProvider(settings.payme)
    if not await provider.verify_webhook_signature({}, dict(request.headers)):
        log.warning("payme_webhook_auth_failed")
        return _err(None, _ERR_TRANSPORT, "Authentication failed")

    # 2. Parse JSON-RPC body
    try:
        body = await request.json()
    except Exception:
        return _err(None, _ERR_TRANSPORT, "Invalid JSON")

    rpc_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    log.info("payme_rpc_received", method=method, rpc_id=rpc_id)

    # 3. Dispatch
    dispatch = {
        "CheckPerformTransaction": _check_perform_transaction,
        "CreateTransaction": _create_transaction,
        "PerformTransaction": _perform_transaction,
        "CancelTransaction": _cancel_transaction,
        "CheckTransaction": _check_transaction,
    }

    handler = dispatch.get(method)
    if handler is None:
        return _err(rpc_id, _ERR_METHOD_NOT_FOUND, f"Method not found: {method}")

    return await handler(rpc_id, params)


# ── Method handlers ─────────────────────────────────────────────────────


async def _check_perform_transaction(rpc_id: Any, params: dict) -> web.Response:
    """Validate that we can accept a payment with these parameters."""
    account = params.get("account", {})
    order_id = account.get("order_id", "")
    amount = params.get("amount", 0)  # tiyin

    factory = get_session_factory()
    async with factory() as session:
        svc = get_subscription_billing_service(session)
        payment = await svc.get_by_merchant_trans_id(order_id)

    if payment is None:
        return _err(rpc_id, _ERR_INVALID_PARAMS, "Order not found")

    # Verify amount (convert our UZS to tiyin)
    expected_tiyin = payment.amount * 100
    if amount != expected_tiyin:
        return _err(rpc_id, _ERR_INVALID_PARAMS, "Amount mismatch")

    if payment.status not in (
        SubscriptionPaymentStatus.PENDING,
        SubscriptionPaymentStatus.PREPARING,
    ):
        return _err(rpc_id, _ERR_CANT_PERFORM, "Cannot perform transaction")

    return _ok(rpc_id, {"allow": True})


async def _create_transaction(rpc_id: Any, params: dict) -> web.Response:
    """Payme has created a transaction — store provider_trans_id."""
    payme_id = params.get("id", "")
    account = params.get("account", {})
    order_id = account.get("order_id", "")
    amount = params.get("amount", 0)
    create_time = params.get("time", int(time.time() * 1000))

    factory = get_session_factory()
    async with factory() as session:
        svc = get_subscription_billing_service(session)
        payment = await svc.get_by_merchant_trans_id(order_id)

        if payment is None:
            return _err(rpc_id, _ERR_INVALID_PARAMS, "Order not found")

        expected_tiyin = payment.amount * 100
        if amount != expected_tiyin:
            return _err(rpc_id, _ERR_INVALID_PARAMS, "Amount mismatch")

        if payment.status == SubscriptionPaymentStatus.PAID:
            return _err(rpc_id, _ERR_ALREADY_DONE, "Already paid")

        if payment.status not in (
            SubscriptionPaymentStatus.PENDING,
            SubscriptionPaymentStatus.PREPARING,
        ):
            return _err(rpc_id, _ERR_CANT_PERFORM, "Cannot create transaction")

        await svc.handle_prepare(
            merchant_trans_id=order_id,
            provider_trans_id=payme_id,
            provider_meta={"payme_create_time": create_time},
        )
        await session.commit()

    return _ok(rpc_id, {
        "create_time": create_time,
        "transaction": payme_id,
        "state": 1,
    })


async def _perform_transaction(rpc_id: Any, params: dict) -> web.Response:
    """Payment completed — extend subscription."""
    payme_id = params.get("id", "")
    perform_time = int(time.time() * 1000)

    factory = get_session_factory()
    async with factory() as session:
        svc = get_subscription_billing_service(session)
        payment = await svc._payment_repo.get_by_provider_trans_id(
            payme_id, for_update=True,
        )

        if payment is None:
            return _err(rpc_id, _ERR_TRANSACTION_NOT_FOUND, "Transaction not found")

        if payment.status == SubscriptionPaymentStatus.PAID:
            log.info(
                "duplicate_webhook",
                provider="payme",
                payme_id=payme_id,
                merchant_trans_id=payment.merchant_trans_id,
            )
            return _ok(rpc_id, {
                "transaction": payme_id,
                "perform_time": perform_time,
                "state": 2,
            })

        try:
            await svc.handle_payment_success(
                merchant_trans_id=payment.merchant_trans_id,
                provider_trans_id=payme_id,
                provider_meta={"payme_perform_time": perform_time},
            )
            await session.commit()
            log.info(
                "payment_processed",
                provider="payme",
                merchant_trans_id=payment.merchant_trans_id,
                payme_id=payme_id,
            )
        except Exception:
            await session.rollback()
            log.exception(
                "payment_failed",
                provider="payme",
                payme_id=payme_id,
            )
            return _err(rpc_id, _ERR_SERVER, "Processing failed")

    return _ok(rpc_id, {
        "transaction": payme_id,
        "perform_time": perform_time,
        "state": 2,
    })


async def _cancel_transaction(rpc_id: Any, params: dict) -> web.Response:
    """Payment canceled/reversed."""
    payme_id = params.get("id", "")
    reason = params.get("reason", 0)
    cancel_time = int(time.time() * 1000)

    factory = get_session_factory()
    async with factory() as session:
        svc = get_subscription_billing_service(session)
        payment = await svc._payment_repo.get_by_provider_trans_id(
            payme_id, for_update=True,
        )

        if payment is None:
            return _err(rpc_id, _ERR_TRANSACTION_NOT_FOUND, "Transaction not found")

        if payment.status == SubscriptionPaymentStatus.CANCELED:
            return _ok(rpc_id, {
                "transaction": payme_id,
                "cancel_time": cancel_time,
                "state": -1,
            })

        await svc.handle_payment_cancel(
            merchant_trans_id=payment.merchant_trans_id,
            provider_meta={
                "payme_cancel_time": cancel_time,
                "payme_reason": reason,
            },
        )
        await session.commit()

    return _ok(rpc_id, {
        "transaction": payme_id,
        "cancel_time": cancel_time,
        "state": -1,
    })


async def _check_transaction(rpc_id: Any, params: dict) -> web.Response:
    """Return current transaction state."""
    payme_id = params.get("id", "")

    factory = get_session_factory()
    async with factory() as session:
        svc = get_subscription_billing_service(session)
        payment = await svc._payment_repo.get_by_provider_trans_id(payme_id)

    if payment is None:
        return _err(rpc_id, _ERR_TRANSACTION_NOT_FOUND, "Transaction not found")

    state_map = {
        SubscriptionPaymentStatus.PENDING: 1,
        SubscriptionPaymentStatus.PREPARING: 1,
        SubscriptionPaymentStatus.PAID: 2,
        SubscriptionPaymentStatus.CANCELED: -1,
        SubscriptionPaymentStatus.FAILED: -2,
    }
    state = state_map.get(SubscriptionPaymentStatus(payment.status), 0)

    create_time = (payment.provider_meta or {}).get(
        "payme_create_time", int(payment.created_at.timestamp() * 1000) if payment.created_at else 0,
    )
    perform_time = (payment.provider_meta or {}).get("payme_perform_time", 0)
    cancel_time = (payment.provider_meta or {}).get("payme_cancel_time", 0)

    return _ok(rpc_id, {
        "create_time": create_time,
        "perform_time": perform_time,
        "cancel_time": cancel_time,
        "transaction": payme_id,
        "state": state,
        "reason": (payment.provider_meta or {}).get("payme_reason"),
    })


def setup_payme_routes(app: web.Application) -> None:
    """Register Payme.uz webhook route on the aiohttp application."""
    app.router.add_post("/webhooks/payme", payme_jsonrpc_handler)
