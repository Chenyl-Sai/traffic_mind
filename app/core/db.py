from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(AsyncAttrs, DeclarativeBase):
    pass


async_engine = create_async_engine(
    url=str(settings.sqlalchemy_database_uri),
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600
)
