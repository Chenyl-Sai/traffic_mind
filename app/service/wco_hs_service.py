from pyexpat.errors import messages

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import BackgroundTasks
from datetime import datetime
import logging
import copy

from sqlalchemy import inspect
from sqlalchemy.orm import make_transient

from app.core.config import settings
from app.util import wco_crawler_utils
from app.repo.wco_hs_repo import insert_update_record, insert_sections, update_record_result, \
    insert_chapters, insert_headings, insert_subheadings, select_last_update_record, select_sections_by_version, \
    select_chapters_by_section, select_headings_by_chapter, select_wco_current_version, \
    delete_wco_section_by_version, disable_last_version, insert_current_version, select_all_chapters, \
    select_current_version_chapters_by_codes, select_current_version_headings_by_codes, select_subheadings_by_heading, \
    select_current_version_subheadings_by_codes, select_all_headings
from app.model.wco_hs_model import WcoHsSection, WcoHsUpdateRecord, WcoHsChapter, WcoHsHeading, WcoHsSubheading, \
    WcoHsVersionHistory
from app.schema.wco_hs import CheckUpdateResponse, WcoHsProcessResult
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def check_wco_hs_update(session: AsyncSession, background_tasks: BackgroundTasks) -> CheckUpdateResponse:
    """
    检查wco官网是否有新的hscode更新
    """
    # 检查是否正在更新
    last_update_status, last_record = await check_wco_last_update(session)
    if last_update_status == 1:
        return CheckUpdateResponse(updating=True, message="正在更新中")
    # 从网站获取当前最新的版本
    page = await wco_crawler_utils.fetch_page(settings.WCO_HSCODE_MAIN_URL + "/en/harmonized-system", is_ajax=False)
    newest_version = await wco_crawler_utils.get_newest_version(page)
    # 从数据库中获取当前版本
    current_version_record = await select_wco_current_version(session)
    current_version = current_version_record.version if current_version_record else "-1"
    # 如果存在新版本，则发起一个后台更新的task，然后返回
    need_update = newest_version != current_version
    if last_update_status == 2:
        # 避免将带有SQLAlchemy状态的对象直接传入后台任务中！！！！
        make_transient(last_record)
        background_tasks.add_task(recovery_update_task, last_record, newest_version)
    elif need_update:
        background_tasks.add_task(update_wco_hs_code_task, newest_version)
    return CheckUpdateResponse(current_version=current_version,
                               latest_version=newest_version,
                               message="更新任务后台执行" if need_update else "无需更新",
                               need_update=need_update,
                               updating=False)


async def check_wco_last_update(session: AsyncSession):
    """
    检查上次更新情况

    :return:    0. 无上次更新/上次更新成功/上次更新失败单不可以断点续更
                1. 上次更新正在更新中
                2. 上次更新失败，但可以断点续更

    """
    last_record = await select_last_update_record(session)
    if last_record and last_record.update_status == "doing":
        return 1, last_record
    elif last_record and last_record.update_status == "fail" and last_record.can_continue:
        return 2, last_record
    return 0, last_record


async def update_wco_hs_code_task(newest_version):
    """
    检查到新数据，更新wco hscode
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            logger.info("Start update wco hs")
            await clear_last_update_cache(session, newest_version)
            logger.info("Clear last update cache")
            record = await add_update_record(session, newest_version)
        result = await process_wco_update(newest_version)
        async with session.begin():
            if result.success:
                record.update_status = "fail"
                record.fail_message = result.message
                record.failed_section = result.failed_section
                record.failed_chapter = result.failed_chapter
                record.failed_heading = result.failed_heading
                record.can_continue = result.can_resume
                record.finish_at = datetime.now() if not record.can_continue else None
                record.updated_at = datetime.now()
                await save_record_result(session, record)
                logger.info("Finish update wco hs with error")
            else:
                record.update_status = "success"
                record.finish_at = datetime.now()
                record.updated_at = datetime.now()
                await save_record_result(session, record)
                logger.info("Finish update wco hs success")


async def process_wco_update(newest_version) -> WcoHsProcessResult:
    current_section_code = ""
    current_chapter_code = ""
    current_heading_code = ""
    try:
        section_list = await process_sections(newest_version)
        for section in section_list:
            logger.debug("Start process section %s", section.section_code)
            current_section_code = section.section_code
            chapter_list = await process_chapters(section)
            for chapter in chapter_list:
                logger.debug("Start process chapter %s", chapter.chapter_code)
                current_chapter_code = chapter.chapter_code
                heading_list = await process_headings(chapter)
                for heading in heading_list:
                    logger.debug("Start process heading %s", heading.heading_code)
                    current_heading_code = heading.heading_code
                    await process_subheadings(heading)
    except Exception as e:
        logger.exception("Update failed", exc_info=e)
        return WcoHsProcessResult(success=False, message=str(e)[:2000] if len(str(e)) > 2000 else str(e),
                                  failed_section=current_section_code, failed_chapter=current_chapter_code,
                                  failed_heading=current_heading_code,
                                  can_resume=True if current_section_code else False)
    else:
        return WcoHsProcessResult(success=True, message="Success", can_resume=False)


async def recovery_update_task(record: WcoHsUpdateRecord, version: str):
    # 更新当前记录为doing
    logger.info("Start resume update wco hs")
    async with AsyncSessionLocal() as session:
        async with session.begin():
            record.update_status = "doing"
            await save_record_result(session, record)
        # 虽然这个方法内部的每个更新操作都是重新创建的session来处理但是其中包含查询，需要包裹在一个事务当中，
        # 否则下面处理异常结果的时候开启事务回失败
        # 但是在这里开启新事务的话，这个事务的时间会超级长
        # 不过也好像也没关系，这个session只负责一些查询
        async with session.begin():
            result = await process_resume_wco_update(record, session, version)
        async with session.begin():
            if not result.success:
                record.update_status = "fail"
                record.fail_message = result.message
                record.failed_section = result.failed_section
                record.failed_chapter = result.failed_chapter
                record.failed_heading = result.failed_heading
                record.can_continue = result.can_resume
                record.finish_at = datetime.now() if not record.can_continue else None
                record.updated_at = datetime.now()
                await save_record_result(session, record)
                logger.info("Finish resume update wco hs with error")
            else:
                record.update_status = "success"
                record.finish_at = datetime.now()
                record.updated_at = datetime.now()
                await save_record_result(session, record)
                logger.info("Finish resume update wco hs success")


async def process_resume_wco_update(record, session, version) -> WcoHsProcessResult:
    last_section_code = record.failed_section
    last_chapter_code = record.failed_chapter
    last_heading_code = record.failed_heading
    skip_section = True
    skip_chapter = True if last_chapter_code else False
    skip_heading = True if last_heading_code else False
    current_section_code = ""
    current_chapter_code = ""
    current_heading_code = ""
    try:
        sections = await select_sections_by_version(session, version)
        for section in sections if sections else []:
            if section.section_code != last_section_code and skip_section:
                logger.debug("Skip section %s", section.section_code)
                continue
            else:
                skip_section = False
            logger.debug("Start process section %s", section.section_code)
            current_section_code = section.section_code
            chapters = []
            if skip_chapter and section.section_code == last_section_code:
                exist_chapters = await select_chapters_by_section(session, section.id)
                for chapter in exist_chapters:
                    if chapter.chapter_code != last_chapter_code and skip_chapter:
                        logger.debug("Skip chapter %s", chapter.chapter_code)
                        continue
                    else:
                        skip_chapter = False
                        chapters.append(chapter)
            else:
                chapters = await process_chapters(section)

            for chapter in chapters if chapters else []:
                logger.debug("Start process chapter %s", chapter.chapter_code)
                current_chapter_code = chapter.chapter_code
                headings = []
                if skip_heading and chapter.chapter_code == last_chapter_code:
                    exist_heading = await select_headings_by_chapter(session, chapter.id)
                    for heading in exist_heading:
                        if heading.heading_code != last_heading_code and skip_heading:
                            logger.debug("Skip heading %s", heading.heading_code)
                            continue
                        else:
                            skip_heading = False
                            headings.append(heading)
                else:
                    headings = await process_headings(chapter)

                for heading in headings if headings else []:
                    logger.debug("Start process heading %s", heading.heading_code)
                    current_heading_code = heading.heading_code
                    await process_subheadings(heading)
    except Exception as e:
        logger.exception("Update failed", exc_info=e)
        return WcoHsProcessResult(success=False, message=str(e)[:2000] if len(str(e)) > 2000 else str(e),
                                  failed_section=current_section_code, failed_chapter=current_chapter_code,
                                  failed_heading=current_heading_code,
                                  can_resume=True if current_section_code else False)
    else:
        return WcoHsProcessResult(success=True, message="Success", can_resume=False)


async def add_update_record(session: AsyncSession, newest_version):
    """
    添加更新记录
    """
    update_record = WcoHsUpdateRecord(update_time=datetime.now(), update_status="doing",
                                      update_version=newest_version)
    return await insert_update_record(session, update_record)


async def save_record_result(session: AsyncSession, record):
    """
    更新记录结果
    """
    await update_record_result(session, record)
    if record.update_status == "success":
        # 更新成功之后，切换当前正在使用的版本为最新版本
        await disable_last_version(session)
        await insert_current_version(session, WcoHsVersionHistory(version=record.update_version, is_current_used=True,
                                                                  enabled_time=datetime.now()))
    return record


async def process_sections(version: str) -> list[WcoHsSection] | None:
    """
    获取并保存section列表到数据库

    :param session:
    :param version: 当前更新的版本
    :return: None
    """
    section_list = await wco_crawler_utils.get_section(version)
    if section_list:
        async with AsyncSessionLocal() as session:
            sections = [WcoHsSection(section_code=section["code"], section_title=section["title"],
                                     load_children_url=section["list_url"], version=version)
                        for section in section_list if section["code"]]
            return await insert_sections(session, sections)
    else:
        raise Exception("没有获取到Section数据")


async def process_chapters(section: WcoHsSection) -> list[WcoHsChapter] | None:
    """
    获取并保存章节数据
    :param section: 所属分类
    :return: None
    """
    chapter_list = await wco_crawler_utils.get_chapter(section)
    if chapter_list:
        async with AsyncSessionLocal() as session:
            chapters = [WcoHsChapter(chapter_code=chapter["code"].zfill(2), chapter_title=chapter["title"],
                                     load_children_url=chapter["list_url"], section_id=section.id,
                                     version=section.version)
                        for chapter in chapter_list if chapter["code"]]
            return await insert_chapters(session, chapters)
    return None


async def process_headings(chapter: WcoHsChapter) -> list[WcoHsHeading] | None:
    """
    获取并保存类目数据
    :param chapter: 所属章节
    :return: None
    """
    heading_list = await wco_crawler_utils.get_heading(chapter)
    if heading_list:
        async with AsyncSessionLocal() as session:
            headings = [WcoHsHeading(heading_code=heading["code"], heading_title=heading["title"],
                                     load_children_url=heading["list_url"], chapter_id=chapter.id,
                                     version=chapter.version)
                        for heading in heading_list if heading["code"]]
            return await insert_headings(session, headings)
    return None


async def process_subheadings(heading: WcoHsHeading) -> list[WcoHsSubheading] | None:
    """
    获取并保存子目数据
    :param heading: 所属类目
    :return: None
    """
    subheading_list = await wco_crawler_utils.get_subheading(heading)
    if subheading_list:
        async with AsyncSessionLocal() as session:
            subheadings = [WcoHsSubheading(subheading_code=subheading["code"], subheading_title=subheading["title"],
                                           heading_id=heading.id, version=heading.version)
                           for subheading in subheading_list if subheading["code"]]
            return await insert_subheadings(session, subheadings)
    return None


async def clear_last_update_cache(session: AsyncSession, version):
    async with session.begin():
        await delete_wco_section_by_version(session, version)


async def get_current_version(session: AsyncSession):
    """
    获取当前使用的版本
    """
    version_record = await select_wco_current_version(session)
    current_version = version_record.version if version_record else None
    return current_version if current_version else None


async def get_current_version_chapters(session: AsyncSession):
    current_version = await get_current_version(session)
    if current_version:
        return await select_all_chapters(session, current_version)
    raise Exception("没有获取到当前版本，请先初始化数据！")

async def get_current_version_headings(session: AsyncSession):
    current_version = await get_current_version(session)
    if current_version:
        return await select_all_headings(session, current_version)
    raise Exception("没有获取到当前版本，请先初始化数据！")

async def get_chapters_by_chapter_codes(session: AsyncSession, chapter_codes: list[str]):
    current_version = await get_current_version(session)
    if current_version:
        return await select_current_version_chapters_by_codes(session, current_version, chapter_codes)
    raise Exception("没有获取到当前版本，请先初始化数据！")

async def get_headings_by_heading_codes(session: AsyncSession, heading_codes: list[str]):
    current_version = await get_current_version(session)
    if current_version:
        return await select_current_version_headings_by_codes(session, current_version, heading_codes)
    raise Exception("没有获取到当前版本，请先初始化数据！")

async def get_subheadings_by_subheading_codes(session: AsyncSession, subheading_codes: list[str]):
    current_version = await get_current_version(session)
    if current_version:
        return await select_current_version_subheadings_by_codes(session, current_version, subheading_codes)
    raise Exception("没有获取到当前版本，请先初始化数据！")



async def get_heading_detail_by_chapter_codes(chapter_codes: list):
    chapter_detail_dict = dict()
    async with AsyncSessionLocal() as session:
        chapters = await get_chapters_by_chapter_codes(session, chapter_codes)
        for chapter in chapters:
            headings = await select_headings_by_chapter(session, chapter.id)
            if headings:
                chapter_detail_dict.update({chapter.chapter_code + ":" + chapter.chapter_title:
                                                [{"heading_code": heading.heading_code,
                                                  "heading_title": heading.heading_title}
                                                 for heading in headings]})
    return chapter_detail_dict


async def get_subheading_detail_by_heading_codes(heading_codes: list):
    chapter_heading_detail_dict = dict()
    async with AsyncSessionLocal() as session:
        headings = await get_headings_by_heading_codes(session, heading_codes)
        for heading in headings:
            chapter = await heading.awaitable_attrs.chapter
            chapter_key = chapter.chapter_code + ":" + chapter.chapter_title
            if chapter_key not in chapter_heading_detail_dict:
                chapter_heading_detail_dict.update({chapter_key: dict()})
            subheadings = await select_subheadings_by_heading(session, heading.id)
            if subheadings:
                heading_details = chapter_heading_detail_dict.get(chapter_key)
                heading_details.update({heading.heading_code + ":" + heading.heading_title:
                                            [{"subheading_code": subheading.subheading_code,
                                              "subheading_title": subheading.subheading_title}
                                             for subheading in subheadings]})
    return chapter_heading_detail_dict


async def get_subheading_dict_by_subheading_codes(subheading_codes: list):
    chapter_heading_detail_dict = dict()
    async with AsyncSessionLocal() as session:
        sub_headings = await get_subheadings_by_subheading_codes(session, subheading_codes)
        for sub_heading in sub_headings:
            heading = await sub_heading.awaitable_attrs.heading
            chapter = await heading.awaitable_attrs.chapter
            heading_key = heading.heading_code + ":" + heading.heading_title
            chapter_key = chapter.chapter_code + ":" + chapter.chapter_title
            if chapter_key not in chapter_heading_detail_dict:
                chapter_heading_detail_dict.update({chapter_key: dict()})
            chapter_details = chapter_heading_detail_dict.get(chapter_key)
            if heading_key not in chapter_details:
                chapter_details.update({heading_key: dict()})
            header_details = chapter_details.get(heading_key)
            header_details.update({sub_heading.subheading_code + ":" + sub_heading.subheading_title: list()})
    return chapter_heading_detail_dict