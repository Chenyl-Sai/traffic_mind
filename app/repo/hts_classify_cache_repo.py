from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.model.hts_classify_cache_model import ItemRewriteCache, DetermineChapterCache, HtsClassifyE2ECache


async def insert_item_rewrite_cache(session: AsyncSession, item_rewrite_cache: ItemRewriteCache) -> ItemRewriteCache:
    session.add(item_rewrite_cache)
    await session.flush()
    return item_rewrite_cache


async def select_item_rewrite_cache(session: AsyncSession, item: str) -> ItemRewriteCache | None:
    result = await session.execute(select(ItemRewriteCache).filter(ItemRewriteCache.origin_item_name == item))
    return result.scalars().first()


async def insert_chapter_determine_cache(session: AsyncSession, cache: DetermineChapterCache) -> DetermineChapterCache:
    session.add(cache)
    await session.flush()
    return cache


async def select_chapter_determine_cache(session: AsyncSession, hashed_cache_key: str) -> DetermineChapterCache | None:
    result = await session.execute(
        select(DetermineChapterCache).filter(DetermineChapterCache.hashed_cache_key == hashed_cache_key))
    return result.scalars().first()


async def insert_e2e_cache(session: AsyncSession, cache: HtsClassifyE2ECache) -> HtsClassifyE2ECache:
    session.add(cache)
    await session.flush()
    return cache


async def select_e2e_cache(session: AsyncSession, origin_item_name: str) -> HtsClassifyE2ECache | None:
    result = await session.execute(
        select(HtsClassifyE2ECache).filter(HtsClassifyE2ECache.origin_item_name == origin_item_name))
    return result.scalars().first()
