from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.logging_utils import get_logger
from app.container import (
    get_provider_registry,
    get_session_repo,
    get_transcode_service,
    get_tts_service,
    get_rate_limiter,
)


logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="tts-gateway", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_http_requests(request: Request, call_next):
        """Centralized logging for all HTTP requests."""
        import time

        start = time.monotonic()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration = time.monotonic() - start
            client_host = request.client.host if request.client else "unknown"
            status_code = response.status_code if response is not None else 500
            logger.info(
                "HTTP %s %s from %s -> %d in %.3fs",
                request.method,
                request.url.path,
                client_host,
                status_code,
                duration,
            )

    app.include_router(api_router)

    @app.on_event("startup")
    async def on_startup() -> None:
        # Force-init singletons so that failures surface at startup.
        _ = get_provider_registry()
        _ = get_session_repo()
        _ = get_transcode_service()
        _ = get_tts_service()
        _ = get_rate_limiter()
        logger.info("All singleton services initialized.")

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        try:
            tts = get_tts_service()
            close = getattr(tts, "close", None)
            if callable(close):
                close()
        except Exception:
            logger.exception("Error while shutting down TTS service")

    return app


@lru_cache(maxsize=1)
def get_app() -> FastAPI:
    return create_app()


app = get_app()

