#!/usr/bin/env python3
import asyncio
import logging

import asyncpg.connect_utils

import config

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
    def __init__(self, dsn: str):
        self._pool: asyncpg.Pool | None = None
        self.dsn = dsn

    async def connect(self):
        log.debug("connecting to database")
        self._pool = await asyncpg.create_pool(
            dsn=self.dsn,
            server_settings={"application_name": "notiteams-activity-api"},
            connection_class=NoResetConnection,
        )

    async def disconnect(self):
        if self._pool:
            await self._pool.close()

    async def acquire(self) -> asyncpg.pool.PoolAcquireContext:
        assert self._pool is not None
        return self._pool.acquire()


database = DatabaseLifecycleHandler(config.DefaultConfig.DATABASE_URL)
