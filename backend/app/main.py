"""Application entrypoint.

Assembles middleware, exception handlers, and the versioned API. Contains no
business logic — if you're tempted to add logic here, it belongs in a module.
"""
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.events.bus import bus
from app.modules.bootstrap import wire_event_subscribers
from app.core.config import get_settings
from app.core.context import bind_request_context, clear_request_context
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging()
wire_event_subscribers(bus)
log = get_logger(__name__)

app = FastAPI(
    title="Tekaplay API",
    version="1.0.0",
    docs_url=f"{settings.api_v1_prefix}/docs",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(
    request: Request, call_next: Callable[[Request], Awaitable]
):
    rid = bind_request_context(
        request_id=request.headers.get("x-request-id"),
        correlation_id=request.headers.get("x-correlation-id"),
    )
    try:
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response
    finally:
        clear_request_context()


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    log.warning("app_error", code=exc.code, message=exc.message, path=request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "retryable": exc.retryable,
                "request_id": request.headers.get("x-request-id"),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_error", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "Something went wrong. Please try again.",
                "details": {},
                "retryable": True,
                "request_id": request.headers.get("x-request-id"),
            }
        },
    )


app.include_router(api_router, prefix=settings.api_v1_prefix)
