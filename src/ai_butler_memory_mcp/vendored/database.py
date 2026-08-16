"""Secret-safe asynchronous database configuration and session lifecycle."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from .config import ConfigurationError
from .models import Base

_SUPPORTED_DRIVERS = {"postgresql+asyncpg", "sqlite+aiosqlite"}
PERSISTENCE_SCHEMA_HEAD = "e2f3a4b5c6d7"


class DatabaseConfig(BaseModel):
    """Database settings whose string representation never reveals the URL."""

    model_config = ConfigDict(extra="forbid")

    url: SecretStr
    health_timeout_seconds: float = Field(default=2.0, gt=0, le=30)

    @property
    def drivername(self) -> str:
        return make_url(self.url.get_secret_value()).drivername

    @property
    def is_test_sqlite(self) -> bool:
        return self.drivername == "sqlite+aiosqlite"

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        required: bool = True,
    ) -> "DatabaseConfig | None":
        source = os.environ if environment is None else environment
        raw_url = source.get("AI_BUTLER_DATABASE_URL", "").strip()
        if not raw_url:
            if required:
                raise ConfigurationError(
                    "AI_BUTLER_DATABASE_URL is not configured. Fill it in the local "
                    ".env file."
                )
            return None

        try:
            parsed = make_url(raw_url)
        except Exception as exc:
            raise ConfigurationError("Database URL is invalid") from exc
        if parsed.drivername not in _SUPPORTED_DRIVERS:
            raise ConfigurationError(
                "Database URL must use postgresql+asyncpg; sqlite+aiosqlite is "
                "accepted only for local automated tests"
            )
        if parsed.drivername == "postgresql+asyncpg" and not parsed.database:
            raise ConfigurationError("PostgreSQL database name is missing")

        try:
            return cls(
                url=raw_url,
                health_timeout_seconds=source.get(
                    "AI_BUTLER_DATABASE_HEALTH_TIMEOUT_SECONDS", "2"
                ),
            )
        except ValueError as exc:
            raise ConfigurationError(
                "Database configuration is invalid; check non-secret values in .env"
            ) from exc


class Database:
    """Own an async engine and issue one AsyncSession per unit of work."""

    def __init__(self, config: DatabaseConfig) -> None:
        url = config.url.get_secret_value()
        engine_options: dict[str, object] = {
            "pool_pre_ping": True,
        }
        if config.is_test_sqlite and make_url(url).database in {None, "", ":memory:"}:
            engine_options["poolclass"] = StaticPool
        self.config = config
        self.engine: AsyncEngine = create_async_engine(url, **engine_options)
        self.sessions = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Commit one unit of work or roll it back in full."""

        async with self.sessions() as session:
            try:
                yield session
                await session.commit()
            except BaseException:
                await session.rollback()
                raise

    async def ping(self) -> None:
        async with asyncio.timeout(self.config.health_timeout_seconds):
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))

    async def readiness(self) -> None:
        """Verify connectivity and that the deployment applied the current schema."""

        async with asyncio.timeout(self.config.health_timeout_seconds):
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
                revision = await connection.scalar(
                    text("SELECT version_num FROM alembic_version")
                )
        if revision != PERSISTENCE_SCHEMA_HEAD:
            raise RuntimeError("Database schema is not at the expected revision")

    async def create_schema_for_tests(self) -> None:
        """Build metadata only for SQLite tests; deployments must use Alembic."""

        if not self.config.is_test_sqlite:
            raise RuntimeError("Production schemas must be created with Alembic")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self.engine.dispose()
