from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update
from datetime import datetime

from app.model.hts_classify_cache_model import ItemRewriteCache


async def insert_item_rewrite_cache(session: AsyncSession, item_rewrite_cache: ItemRewriteCache) -> ItemRewriteCache:
    session.add(item_rewrite_cache)
    await session.flush()
    return item_rewrite_cache


async def select_item_rewrite_cache(session: AsyncSession, item: str) -> ItemRewriteCache | None:
    result = await session.execute(select(ItemRewriteCache).filter(ItemRewriteCache.origin_item_name == item))
    return result.scalars().first()