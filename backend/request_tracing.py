import logging
from contextvars import ContextVar
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import MutableHeaders

logger = logging.getLogger("uvicorn.error")
request_id = ContextVar("request_id", default="-")


def stage(event: str, **fields) -> None:
    fields_text = " ".join(f"{name}={value}" for name, value in fields.items())
    logger.info("request_id=%s stage=%s %s", request_id.get(), event, fields_text)


class RequestTracingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] == "/api/v1/health":
            return await self.app(scope, receive, send)
        started = perf_counter()
        identifier = uuid4().hex
        token = request_id.set(identifier)
        status = 500

        async def traced_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = identifier
            await send(message)

        try:
            stage("request.start", method=scope["method"])
            await self.app(scope, receive, traced_send)
        finally:
            route = getattr(scope.get("route"), "path", None) or "unmatched"
            stage("request.complete", route=route, status=status, elapsed_ms=round((perf_counter() - started) * 1000))
            request_id.reset(token)
