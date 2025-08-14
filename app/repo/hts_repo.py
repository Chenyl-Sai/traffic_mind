from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update
from datetime import datetime

from app.model.hts_model import HtsRateLine, HtsUpdateRecord, HtsRateLineFootnote, HtsStatSuffix, HtsVersionHistory


async def select_current_version(session: AsyncSession) -> HtsVersionHistory | None:
    result = await session.execute(select(HtsVersionHistory).filter(HtsVersionHistory.is_current_used == True))
    return result.scalar_one_or_none()


async def delete_hts_by_version(session: AsyncSession, version: str):
    await session.execute(delete(HtsRateLine).filter(HtsRateLine.version == version))


async def save_update_record(session: AsyncSession, record: HtsUpdateRecord) -> HtsUpdateRecord:
    session.add(record)
    await session.flush()
    return record


async def select_rate_line_by_row_index(session: AsyncSession, row_index: int) -> HtsRateLine | None:
    result = await session.execute(select(HtsRateLine).filter(HtsRateLine.row_index == row_index))
    return result.scalar_one_or_none()


async def select_stat_suffix_by_row_index(session: AsyncSession, row_index: int) -> HtsStatSuffix | None:
    result = await session.execute(select(HtsStatSuffix).filter(HtsStatSuffix.row_index == row_index))
    return result.scalar_one_or_none()


async def insert_rate_line(session: AsyncSession, record: HtsRateLine) -> HtsRateLine:
    session.add(record)
    await session.flush()
    return record


async def insert_rate_line_footnotes(session: AsyncSession, footnotes: list[HtsRateLineFootnote]):
    session.add_all(footnotes)


async def insert_stat_suffix(session: AsyncSession, record: HtsStatSuffix) -> HtsStatSuffix:
    session.add(record)
    await session.flush()
    return record


async def disable_last_version(session: AsyncSession):
    await session.execute(update(HtsVersionHistory)
                          .where(HtsVersionHistory.is_current_used == True)
                          .values(is_current_used=False,
                                  disabled_time=datetime.now()))


async def insert_current_version(session: AsyncSession, current_version: HtsVersionHistory):
    session.add(current_version)


async def select_last_update_record(session: AsyncSession, version: str) -> HtsUpdateRecord | None:
    result = await session.execute(select(HtsUpdateRecord)
                                   .filter(HtsUpdateRecord.update_version == version)
                                   .order_by(HtsUpdateRecord.id.desc())
                                   .limit(1))
    return result.scalar_one_or_none()


async def select_current_rate_lines_by_subheadings(session: AsyncSession, current_version: str, subheadings: list[str]):
    result = await session.execute(
        select(HtsRateLine).filter(HtsRateLine.version == current_version, HtsRateLine.wco_hs_subheading.in_(subheadings)))
    return result.scalars().all()

async def select_rate_line_by_id(session: AsyncSession, id: int):
    result = await session.execute(select(HtsRateLine).filter(HtsRateLine.id == id))
    return result.scalar_one_or_none()

async def select_children_rate_lines_by_parent_id(session: AsyncSession, parent_id: int):
    result = await session.execute(select(HtsRateLine).filter(HtsRateLine.parent_id == parent_id))
    return result.scalars().all()