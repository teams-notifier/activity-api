#!/usr/bin/env python3
import os

# TeamsInterface is built at import time and refuses to construct without credentials.
os.environ.setdefault("MICROSOFT_APP_ID", "test-app-id")
os.environ.setdefault("MICROSOFT_APP_PASSWORD", "test-app-password")

from unittest.mock import AsyncMock  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402

import app as app_module  # noqa: E402
from db import database  # noqa: E402


class AsyncCM:
    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def connection(monkeypatch):
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=AsyncCM(None))
    monkeypatch.setattr(database, "acquire", AsyncMock(return_value=AsyncCM(conn)))
    return conn


@pytest.fixture
def teams(monkeypatch):
    send = AsyncMock(return_value="activity-id-1")
    monkeypatch.setattr(app_module.ti, "send_to_conversation", send)
    return send
