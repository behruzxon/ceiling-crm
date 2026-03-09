"""TenantMiddleware — resolves X-Tenant-Slug header to request.state.tenant_id.

Skips resolution for health/docs paths.
Uses get_session_factory() directly (not the get_db() generator) because
middleware is not a route handler and cannot participate in FastAPI's
dependency injection lifecycle.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from infrastructure.database.session import get_session_factory
from infrastructure.di import get_tenant_repo

_SKIP_PATHS: frozenset[str] = frozenset({
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
})

# Admin routes use JWT authentication instead of X-Tenant-Slug
_SKIP_PREFIXES: tuple[str, ...] = ("/admin/",)


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _SKIP_PATHS or any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        slug = request.headers.get("X-Tenant-Slug")
        if not slug:
            return JSONResponse(
                {"detail": "X-Tenant-Slug header required"},
                status_code=400,
            )

        factory = get_session_factory()
        async with factory() as session:
            repo = get_tenant_repo(session)
            tenant = await repo.get_by_slug(slug)

        if not tenant:
            return JSONResponse(
                {"detail": f"Tenant '{slug}' not found"},
                status_code=404,
            )
        if not tenant.is_active:
            return JSONResponse(
                {"detail": "Tenant is inactive"},
                status_code=403,
            )

        request.state.tenant_id = tenant.id
        request.state.tenant = tenant
        return await call_next(request)
