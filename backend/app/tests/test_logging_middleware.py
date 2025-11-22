from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from app.main import app


def test_http_logging_middleware_logs_request(caplog) -> None:
    client = TestClient(app)

    with caplog.at_level(logging.INFO):
        response = client.get("/healthz")

    assert response.status_code == 200
    messages = [record.getMessage() for record in caplog.records]
    assert any("HTTP GET /healthz" in msg for msg in messages)

