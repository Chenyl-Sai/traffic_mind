from typing import Annotated
from sqlalchemy.ext.asyncio.session import AsyncSession
from fastapi import Depends
from app.db.session import get_async_session
from app.core.db import Base, async_engine
from app import model

SessionDep = Annotated[AsyncSession, Depends(get_async_session)]

async def init_db(session: AsyncSession) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    async with async_engine.begin() as conn:
        # 在异步上下文中调用同步建表方法
        await conn.run_sync(Base.metadata.create_all)
