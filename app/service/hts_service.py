from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import BackgroundTasks
from datetime import datetime
from collections import deque
import logging
import traceback

from app.core.exceptions import BackgroundTaskException
from app.repo.hts_repo import select_current_version, delete_hts_by_version, save_update_record, \
    select_rate_line_by_row_index, insert_rate_line, insert_rate_line_footnotes, insert_stat_suffix, \
    insert_current_version, select_last_update_record, select_stat_suffix_by_row_index, disable_last_version, \
    select_current_rate_lines_by_subheadings, select_rate_line_by_id, select_children_rate_lines_by_parent_id
from app.repo.wco_hs_repo import select_subheading_by_code
from app.db.session import AsyncSessionLocal
from app.model.hts_model import HtsUpdateRecord, HtsRateLine, HtsRateLineFootnote, HtsStatSuffix, HtsVersionHistory
from app.model.wco_hs_model import WcoHsSubheading
from app.schema.hts import HtsRecord, HtsProcessResult, HtsInheritanceDequeElement, CheckUpdateResponse
from app.util import hts_crawler_utils

logger = logging.getLogger(__name__)


async def check_hts_update(session: AsyncSession, background_tasks: BackgroundTasks):
    current_release = await get_last_version()
    current_version = await get_current_version(session)
    if current_release != current_version:
        last_update_status, last_update_record = await get_last_update_status(session, current_release)
        if last_update_status == 1:
            return CheckUpdateResponse(current_version=current_version, lastest_version=current_release,
                                       need_update=True, updating=True, message="正在更新中。。。")
        elif last_update_status == 2:
            background_tasks.add_task(consume_last_update_task, last_update_record)
            return CheckUpdateResponse(current_version=current_version, lastest_version=current_release,
                                       need_update=True, updating=False, message="重试上次更新失败任务中")
        else:
            background_tasks.add_task(start_new_update_task, current_release)
            return CheckUpdateResponse(current_version=current_version, lastest_version=current_release,
                                       need_update=True, updating=False, message="新建更新任务后台运行中")
    else:
        return CheckUpdateResponse(current_version=current_version, lastest_version=current_release,
                                   need_update=False, updating=False, message="无需更新")


async def get_last_update_status(session: AsyncSession, version: str):
    """
    检查上次更新情况

    :return:    0. 无上次更新/上次更新成功/上次更新失败单不可以断点续更
                1. 上次更新正在更新中
                2. 上次更新失败，但可以断点续更

    """
    last_update_record = await select_last_update_record(session, version)
    if last_update_record and last_update_record.update_status == "doing":
        return 1, last_update_record
    if last_update_record and last_update_record.update_status == "fail" and last_update_record.can_continue:
        return 2, last_update_record
    return 0, last_update_record


async def get_last_version():
    current_release = await hts_crawler_utils.get_current_release()
    return current_release["name"]


async def get_current_version(session: AsyncSession):
    version = await select_current_version(session)
    return version.version if version else "-1"


async def consume_last_update_task(record: HtsUpdateRecord):
    logger.info("Start resume update HTS data, release version: %s", record.update_version)
    data = await get_last_version_data(record.update_version)
    logger.info("Get data from HTS successfully, data size: %s", len(data))

    async with AsyncSessionLocal() as session:
        async with session.begin():
            record.update_status = "doing"
            record = await save_update_record(session, record)
        result = await process_data(session, record.update_version, data, record.fail_row)
        async with session.begin():
            if result.success:
                record.update_status = "success"
                record.finish_at = datetime.now()
                record.updated_at = datetime.now()
                await process_after_update(session, record)
            else:
                record.update_status = "fail"
                record.fail_message = result.message
                record.fail_row = result.failed_row
                record.can_continue = result.can_resume
                record.finish_at = datetime.now() if not record.can_continue else None
                record.updated_at = datetime.now()
                await process_after_update(session, record)
    logger.info("Finish resume update HTS data")


async def start_new_update_task(current_release: str):
    logger.info("Start update HTS data, release version: %s", current_release)
    data = await get_last_version_data(current_release)
    logger.info("Get data from HTS successfully, data size: %s", len(data))

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await delete_hts_by_version(session, current_release)
            record = await save_update_record(session,
                                              HtsUpdateRecord(update_time=datetime.now(),
                                                              update_version=current_release,
                                                              update_status="doing"))
        result = await process_data(session, current_release, data, 0)
        async with session.begin():
            if result.success:
                record.update_status = "success"
                record.finish_at = datetime.now()
                await process_after_update(session, record)
            else:
                record.update_status = "fail"
                record.fail_message = result.message
                record.fail_row = result.failed_row
                record.can_continue = result.can_resume
                record.finish_at = datetime.now() if not record.can_continue else None
                await process_after_update(session, record)
    logger.info("Finish update HTS data")


async def get_last_version_data(current_release_name) -> list[HtsRecord]:
    return await hts_crawler_utils.read_data(current_release_name)


async def process_data(session: AsyncSession,
                       current_release: str,
                       data: list[HtsRecord],
                       start_row: int) -> HtsProcessResult:
    logger.info("Start process data, start row: %s", start_row)
    inheritance_deque = deque()
    wco_subheading_cache = dict()
    current_process_row = start_row
    try:
        for index, datum in enumerate(data):
            if index < start_row:
                continue
            current_process_row = index
            # 每行独立提交
            await process_single_row(session, datum, index, inheritance_deque, wco_subheading_cache,
                                     current_release, data)
            if index + 1 % 1000 == 0:
                logger.info("Processed row: %s", index)
    except Exception as e:
        logger.exception("Process HTS failed, failed row: %s", current_process_row, exc_info=e)
        stack_trace = traceback.format_exc(2000)
        return HtsProcessResult(success=False,
                                message=stack_trace[:2000] if len(stack_trace) > 2000 else stack_trace,
                                failed_row=current_process_row,
                                can_resume=e.can_resume if isinstance(e, BackgroundTaskException) else True)
    else:
        logger.info("Process HTS successfully")
        return HtsProcessResult(success=True,
                                message="success")


async def process_single_row(session: AsyncSession,
                             datum: HtsRecord,
                             index: int,
                             inheritance_deque: deque,
                             wco_subheading_cache: dict,
                             current_release: str,
                             data: list):
    async with session.begin():
        # 去除编码中的点(.)
        if datum.htsno:
            datum.htsno = datum.htsno.replace(".", "")

        # 获取父级
        parent = await get_parent(session, inheritance_deque, index, data)

        # 是否税率线(8位，存储了税率信息的记录)
        is_rate_line = await check_is_rate_line(datum)
        # 是否是统计后缀(10位，有些10位实际上是8为后面补零，其中也存储了税率信息)
        is_stat_suffix = await check_is_stat_suffix(datum)
        # 是否是单纯的10位统计后缀，如果是，则不需要插入rate_line表，只插入stat_suffix表
        is_only_stat_suffix = await check_is_only_stat_suffix(datum)
        rate_line = None
        if not is_only_stat_suffix:
            htsno = datum.htsno
            if is_rate_line and is_stat_suffix:
                htsno = datum.htsno[:-2]
            wco_subheading_code = None
            if is_rate_line:
                wco_subheading = await get_wco_hs_subheading(session, datum, wco_subheading_cache)
                wco_subheading_code = wco_subheading.subheading_code if wco_subheading else None

            # 将当前行构建成持久化对象
            rate_line = HtsRateLine(
                rate_line_code=htsno,
                rate_line_description=datum.description,
                general_rate=datum.general,
                special_rate=datum.special,
                other=datum.other,
                units=",".join(datum.units),
                quota_quantity=datum.quotaQuantity,
                additional_duties=datum.additionalDuties,
                indent=datum.indent,
                is_superior=datum.superior if datum.superior else False,
                version=current_release,
                parent_id=parent.id if parent else None,
                wco_hs_subheading=wco_subheading_code,
                is_rate_line=is_rate_line,
                row_index=index
            )

            # 插入，拿到id
            rate_line = await insert_rate_line(session, rate_line)
            # 更新inheritance_deque最后添加的自己这个元素的id
            inheritance_deque[-1].id = rate_line.id

            # 如果有脚注则插入脚注信息
            save_foot_notes = []
            for foot_note in datum.footnotes if datum.footnotes else []:
                save_foot_notes.append(
                    HtsRateLineFootnote(
                        rate_line_id=rate_line.id,
                        related_column=",".join(foot_note.columns),
                        note_type=foot_note.type,
                        note_value=foot_note.value,
                        marker=foot_note.marker,
                        row_index=index,
                        version=current_release,
                    )
                )
            if save_foot_notes:
                await insert_rate_line_footnotes(session, save_foot_notes)

        # 如果这条记录是统计后缀，则插入后缀表
        if is_stat_suffix:
            rate_line_id = await get_stat_suffix_parent_rate_line_id(datum, rate_line, inheritance_deque)
            # 如果父类还是10位的，那么parent就是stat_suffix表的数据，则rate_parent_id就不能使用parent.id，设置为空，否则外键约束失败
            if not parent:
                rate_parent_id = None
            elif await check_is_only_stat_suffix(
                    HtsRecord(htsno=parent.code, indent=parent.indent, description=parent.description,
                              general=parent.general, special=parent.special, other=parent.other, units=[])):
                rate_parent_id = None
            else:
                rate_parent_id = parent.id
            stat_suffix = HtsStatSuffix(
                stat_code=datum.htsno,
                stat_description=datum.description,
                indent=datum.indent,
                is_superior=datum.superior if datum.superior else False,
                rate_line_id=rate_line_id,
                rate_parent_id=rate_parent_id,
                row_index=index,
                version=current_release,
            )
            await insert_stat_suffix(session, stat_suffix)


async def get_parent(session: AsyncSession,
                     inheritance_deque: deque[HtsInheritanceDequeElement],
                     current_index: int,
                     data: list[HtsRecord]) -> HtsInheritanceDequeElement | None:
    current_record = data[current_index]
    # 从deque中寻找父级
    parent = inheritance_deque[-1] if inheritance_deque else None
    while parent and parent.indent >= current_record.indent:
        inheritance_deque.pop()
        parent = inheritance_deque[-1] if inheritance_deque else None
    # 如果找到了，将当前添加到继承中，然后返回parent
    if not parent:
        # 非最高级别，但是没有发信parent，说明是断点重试，则需要从数据库中构建继承关系(因为需要父级id,所以要重新从数据库构建)
        if current_record.indent != 0:
            search_index = current_index - 1
            current_search_record = data[search_index]
            deque_first_element_indent = current_record.indent
            while search_index >= 0:
                if current_search_record.indent < deque_first_element_indent:
                    # 存在10位的父级还是10位的情况，这时候应该查找stat_suffix表寻找父级，否则找不到，rate_line表不存在stat suffix数据
                    element = None
                    if await check_is_only_stat_suffix(current_search_record):
                        stat_suffix = await select_stat_suffix_by_row_index(session, search_index)
                        if stat_suffix:
                            element = HtsInheritanceDequeElement(code=stat_suffix.stat_code,
                                                                 description=stat_suffix.stat_description,
                                                                 indent=stat_suffix.indent,
                                                                 is_superior=stat_suffix.is_superior,
                                                                 id=stat_suffix.id,
                                                                 type=1,
                                                                 general=None,
                                                                 special=None,
                                                                 other=None)
                    else:
                        rate_line = await select_rate_line_by_row_index(session, search_index)
                        if rate_line:
                            element = HtsInheritanceDequeElement(code=rate_line.rate_line_code,
                                                                 description=rate_line.rate_line_description,
                                                                 indent=rate_line.indent,
                                                                 is_superior=rate_line.is_superior,
                                                                 id=rate_line.id,
                                                                 type=0,
                                                                 general=rate_line.general_rate,
                                                                 special=rate_line.special_rate,
                                                                 other=rate_line.other)
                    if element:
                        inheritance_deque.appendleft(element)
                        deque_first_element_indent = current_search_record.indent
                    else:
                        raise BackgroundTaskException(can_resume=False, message="断点重试未获取到父级信息")
                # 到达最高级直接退出
                if current_search_record.indent == 0:
                    break
                search_index -= 1
                current_search_record = data[search_index]
            parent = inheritance_deque[-1] if inheritance_deque else None
    # 将当前元素添加到继承的末尾
    inheritance_deque.append(HtsInheritanceDequeElement(code=current_record.htsno,
                                                        description=current_record.description,
                                                        indent=current_record.indent,
                                                        is_superior=current_record.superior,
                                                        type=1 if await check_is_only_stat_suffix(
                                                            current_record) else 0,
                                                        general=current_record.general,
                                                        special=current_record.special,
                                                        other=current_record.other))
    return parent


async def check_is_rate_line(current_record: HtsRecord) -> bool:
    if current_record.htsno and len(current_record.htsno) == 8:
        return True
    # 存在结尾不是00的，但是是10位的税率线数据
    if current_record.htsno and len(current_record.htsno) == 10 and (
            current_record.general or current_record.special or current_record.other):
        return True
    return False


async def check_is_stat_suffix(current_record: HtsRecord) -> bool:
    if current_record.htsno and len(current_record.htsno) == 10:
        return True
    return False


async def check_is_only_stat_suffix(current_record: HtsRecord) -> bool:
    if current_record.htsno and len(current_record.htsno) == 10 and not (
            current_record.general or current_record.special or current_record.other):
        return True
    return False


async def get_wco_hs_subheading(session: AsyncSession,
                                current_record: HtsRecord,
                                wco_heading_cache: dict[str, WcoHsSubheading]) -> WcoHsSubheading | None:
    htsno = current_record.htsno
    if await check_is_stat_suffix(current_record):
        htsno = htsno[:-2]
    if await check_is_rate_line(current_record):
        htsno = htsno[:-2]
        # 检查一下是不是存在哦
        if htsno not in wco_heading_cache:
            wco_heading_cache[htsno] = await select_subheading_by_code(session, htsno)
        return wco_heading_cache[htsno]
    return None


async def get_stat_suffix_parent_rate_line_id(current_record: HtsRecord,
                                              current_rate_line: HtsRateLine,
                                              inheritance_deque: deque) -> int | None:
    if await check_is_rate_line(current_record):
        return current_rate_line.id
    # 倒序向上找父级
    for index, element in enumerate(reversed(inheritance_deque)):
        # 最后一个是当前元素
        if index == 0:
            continue
        # 父级是8位税率线编码
        if len(element.code) == 8:
            return element.id
    return None


async def process_after_update(session: AsyncSession, record: HtsUpdateRecord):
    await save_update_record(session, record)
    if record.update_status == "success":
        await disable_last_version(session)
        await insert_current_version(session, HtsVersionHistory(version=record.update_version, is_current_used=True,
                                                                enabled_time=datetime.now()))


async def get_rate_lines_by_wco_subheadings(subheadings: list[str]):
    subheading_detail_dict = dict()
    parent_cache = dict()
    top_level_group_id_set = set()
    async with (AsyncSessionLocal() as session):
        current_version_record = await select_current_version(session)
        if not current_version_record:
            raise Exception("HTS数据未初始化，请初始化后重试")
        current_version = current_version_record.version
        rate_lines = await select_current_rate_lines_by_subheadings(session, current_version, subheadings)
        for rate_line in rate_lines:
            # 准备好此RateLine对应的subheading插槽
            subheading_code = rate_line.wco_hs_subheading
            if subheading_code not in subheading_detail_dict:
                subheading_detail_dict.update({subheading_code: []})
            subheading_detail = subheading_detail_dict.get(subheading_code)

            # 获取上级
            parent_id = rate_line.parent_id
            # 如果上级为空，则直接将当前RateLine添加到插槽中
            if not parent_id:
                subheading_detail.append({
                    "rate_line_code": rate_line.rate_line_code,
                    "rate_line_description": rate_line.rate_line_description
                })
            else:
                # 如果有上级，获取上级，查看上级是否是说明信息
                while parent_id:
                    if parent_id not in parent_cache:
                        parent = await select_rate_line_by_id(session, parent_id)
                        logger.info(f"parent_id: {parent_id},  parent's parent_id: {parent.parent_id}")
                        parent_cache.update({parent_id: parent})
                    else:
                        parent = parent_cache.get(parent_id)
                    if not parent.is_superior:
                        break
                    parent_id = parent.parent_id

                # 从最上层parent_id构建整个树，然后添加到插槽中
                if parent_id in top_level_group_id_set:
                    # 按最上层的来看，已经存在了就直接跳过，不重复添加到插槽中
                    continue
                else:
                    subheading_detail.append(await construct_rate_line_tree(session, parent_id))
                    top_level_group_id_set.add(parent_id)

    return subheading_detail_dict


async def construct_rate_line_tree(session: AsyncSession, parent_id: int):
    """
    递归构建 RateLine 树结构
    """
    rate_line = await select_rate_line_by_id(session, parent_id)
    # 节点结构
    node = {rate_line.rate_line_description: []}

    # 获取所有子节点
    children = await select_children_rate_lines_by_parent_id(session, parent_id)
    slot = node[rate_line.rate_line_description]

    for child in (children if children else []):
        if child.is_superior:
            # 分组节点，递归构建
            slot.append(await construct_rate_line_tree(session, child.id))
        else:
            # 叶子节点，直接添加
            slot.append({
                "rate_line_code": child.rate_line_code,
                "rate_line_description": child.rate_line_description
            })

    return node