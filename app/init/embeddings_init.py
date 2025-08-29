"""
构建用于检索商品所属分类的向量数据库
"""
import logging

from pymilvus import AsyncMilvusClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import MilvusCollectionName
from app.model.milvus.knowledge_model import ChapterKnowledge, HeadingKnowledge
from app.service.wco_hs_service import get_current_version_chapters, get_current_version_headings
from app.llm.chain.expand_hs_title import get_chapter_extends

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
        data = ChapterKnowledge(chapter_code=chapter.chapter_code, chapter_title=chapter.chapter_title,
                                section_code=section.section_code,
                                includes=extends.includes, common_examples=extends.common_examples,
                                content=extends.model_dump_json())
        await async_milvus_client.insert(collection_name=MilvusCollectionName.KNOWLEDGE_CHAPTER,
                                         data=[data.model_dump()])


async def build_heading_knowledge_collection(session: AsyncSession, async_milvus_client: AsyncMilvusClient):
    """
    构建heading层的向量
    """
    exist_heading = await async_milvus_client.query(collection_name=MilvusCollectionName.KNOWLEDGE_HEADING.value,
                                                    limit=1)
    if exist_heading:
        logger.info("Heading already inited")
    else:
        headings = await get_current_version_headings(session)
        data = []
        for heading in headings:
            data.append(HeadingKnowledge(heading_code=heading.heading_code,
                                         heading_title=heading.heading_title,
                                         chapter_code=heading.heading_code[:2])
                        .model_dump())
        await async_milvus_client.insert(collection_name=MilvusCollectionName.KNOWLEDGE_CHAPTER,
                                         data=data)
