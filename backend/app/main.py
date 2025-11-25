from __future__ import annotations

from functools import lru_cache
import asyncio

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
from app.config import settings
from app.services.session_queue import configure_session_queue


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
        provider_registry = get_provider_registry()
        session_repo = get_session_repo()
        transcode_service = get_transcode_service()
        tts_service = get_tts_service()
        rate_limiter = get_rate_limiter()
        logger.info(
            "All singleton services initialized "
            "(providers=%d, sessions_repo=%s, transcode_service=%s, rate_limiter=%s)",
            len(list(provider_registry.list_providers())),
            type(session_repo).__name__,
            type(transcode_service).__name__,
            type(rate_limiter).__name__,
        )

        # Configure bounded streaming queue and worker pool.
        configure_session_queue(
            tts_service=tts_service,
            maxsize=settings.session_queue_maxsize,
            worker_count=settings.session_queue_worker_count,
        )
        logger.info(
            "Session queue ready (maxsize=%d, workers=%d)",
            settings.session_queue_maxsize,
            settings.session_queue_worker_count,
        )

        # Background task: periodically resample rate-limit metrics so that
        # Prometheus sees a continuously updated view of usage / window
        # remaining, even when no new requests are arriving.
        async def rate_limit_metrics_loop() -> None:
            while True:
                await asyncio.sleep(
                    max(0.1, settings.rate_limit_metrics_poll_interval_seconds)
                )
                try:
                    rate_limiter.sample_metrics()
                except Exception:
                    logger.exception("Error while sampling rate-limit metrics")

        asyncio.create_task(rate_limit_metrics_loop())

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
