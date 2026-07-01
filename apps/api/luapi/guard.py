"""Request guard: optional API shared-secret auth + concurrency backpressure.

Auth here gates the API :8000 directly (for clients that hit it without the web app, e.g. a
script or a directly-exposed API); it is OFF unless ``LU_AUTH_TOKEN`` is set to a NON-EMPTY
value. Note the web app reaches the API through Next's server-side proxy, which does not carry
this token — so the *exposed tunnel* (:3000) is gated at the web layer instead (see
apps/web/middleware.ts / LU_WEB_PASSWORD). Backpressure sheds load with 429 once too many
requests are in flight, protecting the single worker + the shared LLM quota from a stampede.

Both counters are per-process: under a multi-worker deploy the effective global concurrency cap
is ``max_concurrent_requests × workers`` (each worker sheds independently).
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from lucore.config import get_settings

# Paths always reachable without auth / without counting against the concurrency cap.
_EXEMPT = {"/health"}

# In-flight request count. Safe as a plain int on the single asyncio event loop: the
# check-and-increment below has no await between it, so there is no interleaving race.
_inflight = 0


def check_auth(path: str, headers) -> bool:  # noqa: ANN001
    """True if the request is authorized (or auth is disabled)."""
    token = get_settings().auth_token
    if not token or path in _EXEMPT:
        return True
    presented = headers.get("x-auth-token") or ""
    auth = headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        bearer = auth[7:].strip()
        if bearer:  # only let a non-empty Bearer override a valid X-Auth-Token
            presented = bearer
    return bool(presented) and presented == token


async def guard_middleware(request: Request, call_next):
    global _inflight
    if not check_auth(request.url.path, request.headers):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)

    cap = get_settings().max_concurrent_requests
    exempt = request.url.path in _EXEMPT
    if cap and not exempt and _inflight >= cap:
        return JSONResponse({"detail": "server busy, retry shortly"}, status_code=429)

    if not exempt:
        _inflight += 1
    try:
        return await call_next(request)
    finally:
        if not exempt:
            _inflight -= 1
