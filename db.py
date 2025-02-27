#!/usr/bin/env python3
import asyncio
import logging

import asyncpg.connect_utils

from config import config
from config import DefaultConfig

log = logging.getLogger(__name__)


class NoResetConnection(asyncpg.connection.Connection):
    def __init__(
        self,
        protocol: asyncpg.protocol.protocol.BaseProtocol,
        transport: object,
        loop: asyncio.AbstractEventLoop,
        addr: tuple[str, int] | str,
        config: asyncpg.connect_utils._ClientConfiguration,
        params: asyncpg.connect_utils._ConnectionParameters,
    ) -> None:
        super().__init__(protocol, transport, loop, addr, config, params)
        self._reset_query: list[str] = []


class DatabaseLifecycleHandler:
    def __init__(
        self,
        conf: DefaultConfig,
    ):
        self._pool: asyncpg.Pool | None = None
        self._config: DefaultConfig = conf

    async def connect(self):
        log.debug("connecting to database")
        self._pool = await asyncpg.create_pool(
            dsn=self._config.DATABASE_URL,
            server_settings={"application_name": "notiteams-activity-api"},
            connection_class=NoResetConnection,
            min_size=self._config.DATABASE_POOL_MIN_SIZE,
            max_size=self._config.DATABASE_POOL_MAX_SIZE,
        )

        # Simple check at startup, will validate database resolution and creds
        async with await self.acquire() as connection:
            await connection.fetchval("SELECT 1")

    async def disconnect(self):
        if self._pool:
            await self._pool.close()

    async def acquire(self) -> asyncpg.pool.PoolAcquireContext:
        assert self._pool is not None
        return self._pool.acquire()


database = DatabaseLifecycleHandler(config)
