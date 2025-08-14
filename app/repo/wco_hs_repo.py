from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update

from datetime import datetime

from app.model.wco_hs_model import WcoHsSection, WcoHsUpdateRecord, WcoHsChapter, WcoHsHeading, WcoHsSubheading, \
    WcoHsVersionHistory


async def select_last_version_section(session: AsyncSession) -> WcoHsSection | None:
    result = await session.execute(select(WcoHsSection).order_by(WcoHsSection.version.desc()).limit(1))
    return result.scalar_one_or_none()


async def select_update_record_by_id(session: AsyncSession, id: int):
    result = await session.execute(select(WcoHsUpdateRecord).filter(WcoHsUpdateRecord.id == id))
    return result.scalar_one_or_none()


async def select_sections_by_version(session: AsyncSession, version: str) -> list[WcoHsSection] | None:
    result = await session.execute(
        select(WcoHsSection).filter(WcoHsSection.version == version).order_by(WcoHsSection.section_code.asc()))
    sections = result.scalars().all()
    return list(sections) if sections else None


async def select_chapters_by_section(session: AsyncSession, section_id: int) -> list[WcoHsChapter] | None:
    result = await session.execute(
        select(WcoHsChapter).filter(WcoHsChapter.section_id == section_id).order_by(WcoHsChapter.chapter_code.asc()))
    chapters = result.scalars().all()
    return list(chapters) if chapters else None


async def select_headings_by_chapter(session: AsyncSession, chapter_id: int) -> list[WcoHsHeading] | None:
    result = await session.execute(
        select(WcoHsHeading).filter(WcoHsHeading.chapter_id == chapter_id).order_by(WcoHsHeading.heading_code.asc()))
    headings = result.scalars().all()
    return list(headings) if headings else None


async def select_last_update_record(session: AsyncSession):
    result = await session.execute(select(WcoHsUpdateRecord).order_by(WcoHsUpdateRecord.update_time.desc()).limit(1))
    return result.scalar_one_or_none()


async def insert_update_record(session: AsyncSession, record: WcoHsUpdateRecord) -> WcoHsUpdateRecord:
    session.add(record)
    await session.flush()  # 刷新以获取自增ID
    return record


async def update_record_result(session: AsyncSession, record: WcoHsUpdateRecord):
    await session.execute(update(WcoHsUpdateRecord)
                          .where(WcoHsUpdateRecord.id == record.id)
                          .values(update_status=record.update_status,
                                  fail_message=record.fail_message,
                                  failed_section=record.failed_section,
                                  failed_chapter=record.failed_chapter,
                                  failed_heading=record.failed_heading,
                                  can_continue=record.can_continue,
                                  finish_at=record.finish_at,
                                  updated_at=record.updated_at))
    # session.add(record)


async def insert_sections(session: AsyncSession, sections: list[WcoHsSection]) -> list[WcoHsSection]:
    session.add_all(sections)
    await session.flush()
    return sections


async def insert_chapters(session: AsyncSession, chapters: list[WcoHsChapter]) -> list[WcoHsChapter]:
    session.add_all(chapters)
    await session.flush()
    return chapters


async def insert_headings(session: AsyncSession, headings: list[WcoHsHeading]) -> list[WcoHsHeading]:
    session.add_all(headings)
    await session.flush()
    return headings


async def insert_subheadings(session: AsyncSession, subheadings: list[WcoHsSubheading]) -> list[WcoHsSubheading]:
    session.add_all(subheadings)
    await session.flush()
    return subheadings


async def disable_last_version(session: AsyncSession):
    await session.execute(update(WcoHsVersionHistory)
                          .where(WcoHsVersionHistory.is_current_used == True)
                          .values(is_current_used=False,
                                  disabled_time=datetime.now()))


async def insert_current_version(session: AsyncSession, current_version: WcoHsVersionHistory):
    session.add(current_version)


async def select_wco_current_version(session: AsyncSession) -> WcoHsVersionHistory | None:
    result = await session.execute(select(WcoHsVersionHistory).filter(WcoHsVersionHistory.is_current_used == True))
    return result.scalar_one_or_none()


async def delete_wco_section_by_version(session: AsyncSession, version: str):
    await session.execute(delete(WcoHsSection).where(WcoHsSection.version == version))


async def select_subheading_by_code(session: AsyncSession, code: str):
    result = await session.execute(select(WcoHsSubheading).filter(WcoHsSubheading.subheading_code == code))
    return result.scalar_one_or_none()


async def select_all_chapters(session: AsyncSession, version: str):
    result = await session.execute(select(WcoHsChapter).filter(WcoHsChapter.version == version))
    return result.scalars().all()


async def select_current_version_chapters_by_codes(session: AsyncSession, current_version: str, codes: list[str]):
    result = await session.execute(
        select(WcoHsChapter).filter(WcoHsChapter.version == current_version, WcoHsChapter.chapter_code.in_(codes)))
    return result.scalars().all()


async def select_current_version_headings_by_codes(session: AsyncSession, current_version: str, codes: list[str]):
    result = await session.execute(
        select(WcoHsHeading).filter(WcoHsHeading.version == current_version, WcoHsHeading.heading_code.in_(codes)))
    return result.scalars().all()


async def select_subheadings_by_heading(session: AsyncSession, heading_id: str):
    result = await session.execute(select(WcoHsSubheading).filter(WcoHsSubheading.heading_id == heading_id))
    return result.scalars().all()


async def select_current_version_subheadings_by_codes(session: AsyncSession, current_version: str, codes: list[str]):
    result = await session.execute(
        select(WcoHsSubheading).filter(WcoHsSubheading.version == current_version,
                                       WcoHsSubheading.subheading_code.in_(codes)))
    return result.scalars().all()
