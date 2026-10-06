from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.environment == "development")
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    # Every DB column backing Mapped[datetime] is TIMESTAMPTZ (see the
    # migration's DDL) — map the Python side to match, once, here, rather
    # than repeating mapped_column(DateTime(timezone=True)) on every one
    # of the ~20 datetime columns across models/.
    type_annotation_map = {datetime: DateTime(timezone=True)}


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
