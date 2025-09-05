"""
构建用于检索商品所属分类的向量数据库
"""
import asyncio
import json
import logging

from pymilvus import AsyncMilvusClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import MilvusCollectionName
from app.llm.embedding import default_embeddings_service
from app.model.milvus.knowledge_model import ChapterKnowledge, HeadingKnowledge
from app.service.wco_hs_service import get_current_version_chapters, get_headings_by_chapter_code
from app.llm.chain.expand_hs_title import get_chapter_extends, get_heading_extends
from app.schema.llm.llm import HeadingExtends

logger = logging.getLogger(__name__)


async def build_chapter_knowledge_collection(session: AsyncSession, async_milvus_client: AsyncMilvusClient):
    chapters = await get_current_version_chapters(session)
    # 从LLM将chapter信息补充完整
    for index, chapter in enumerate(chapters):
        # 索引已经存在的编码不再重复初始化
        filtered_docs = await async_milvus_client.query(collection_name=MilvusCollectionName.KNOWLEDGE_CHAPTER.value,
                                                        filter=f"chapter_code=='{chapter.chapter_code}'",
                                                        limit=1)
        if filtered_docs:
            logger.debug("Skip init exist expend of chapter: %s", chapter.chapter_code)
            continue

        logger.info("Start init expend of chapter: %s", chapter.chapter_code)
        extends = await get_chapter_extends(chapter.chapter_title)
        section = await chapter.awaitable_attrs.section
        content = extends.model_dump_json()
        data = ChapterKnowledge(chapter_code=chapter.chapter_code, chapter_title=chapter.chapter_title,
                                section_code=section.section_code,
                                includes=extends.includes, common_examples=extends.common_examples,
                                content=content,
                                content_vector=await default_embeddings_service.get_embeddings_for_str(content, False))
        await async_milvus_client.insert(collection_name=MilvusCollectionName.KNOWLEDGE_CHAPTER.value,
                                         data=[data.model_dump()])


async def build_heading_knowledge_collection(session: AsyncSession, async_milvus_client: AsyncMilvusClient):
    """
    构建混合的heading(在heading中挂在chapter信息)
    """
    chapters = await async_milvus_client.query(collection_name=MilvusCollectionName.KNOWLEDGE_CHAPTER.value,
                                               limit=100,
                                               output_fields=["chapter_code", "chapter_title", "content"])
    for chapter in chapters:
        chapter_code = chapter["chapter_code"]
        chapter_title = chapter["chapter_title"]
        chapter_description = chapter["content"]
        # 获取chapter下的章节列表
        headings = await get_headings_by_chapter_code(session, chapter_code)
        if headings:
            data = []
            for heading in headings:
                data.append(HeadingKnowledge(heading_code=heading.heading_code,
                                             heading_title=heading.heading_title,
                                             heading_description="{}",
                                             heading_description_vector=[],
                                             chapter_code=chapter_code,
                                             chapter_title=chapter_title,
                                             chapter_description=chapter_description)
                            .model_dump())

            # 去除已经初始化过的heading
            exist_headings = await async_milvus_client.query(
                collection_name=MilvusCollectionName.KNOWLEDGE_HEADING.value,
                filter=f"chapter_code=='{chapter_code}'",
                output_fields=["heading_code"],
                limit=1000)
            if exist_headings:
                exists_heading_codes = [heading["heading_code"] for heading in exist_headings]
                data = [d for d in data if d["heading_code"] not in exists_heading_codes]
            if data:
                group_size = 10
                grouped_data = [data[i:i + group_size] for i in range(0, len(data), group_size)]
                for group in grouped_data:
                    # 批量获取heading 补充信息
                    tasks = []
                    for heading in group:
                        tasks.append(get_heading_extends(chapter_title, heading["heading_title"]))
                    result: list[HeadingExtends] = await asyncio.gather(*tasks)
                    # 将结果更新到 heading
                    for i, heading_extend in enumerate(result):
                        group[i].update({"heading_includes": heading_extend.includes})
                        group[i].update({"heading_common_examples": heading_extend.common_examples})
                        description = json.dumps({
                            "heading_title": group[i]["heading_title"],
                            "includes": heading_extend.includes,
                            "common_examples": heading_extend.common_examples,
                        }, ensure_ascii=False)
                        description_vector = await default_embeddings_service.get_embeddings_for_str(description, False)
                        group[i].update({"heading_description": description})
                        group[i].update({"heading_description_vector": description_vector})
                    # 批量插入索引
                    await async_milvus_client.insert(
                        collection_name=MilvusCollectionName.KNOWLEDGE_HEADING.value,
                        data=group)
