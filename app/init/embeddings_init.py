"""
构建用于检索商品所属分类的向量数据库
"""
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.service.vector_store_service import FAISSVectorStore
from app.service.wco_hs_service import get_current_version_chapters
from app.llm.chain.expand_hs_title import get_chapter_extends

logger = logging.getLogger(__name__)


async def build_vector_store(session: AsyncSession, vector_store: FAISSVectorStore):
    changed: bool = False
    try:
        chapters = await get_current_version_chapters(session)
        # 从LLM将chapter信息补充完整
        for index, chapter in enumerate(chapters):
            # 索引已经存在的编码不再重复初始化
            filtered_docs = [
                doc for doc in vector_store.index.docstore._dict.values()
                if doc.metadata.get("type") == "chapter" and doc.metadata.get("code") == chapter.chapter_code
            ]
            if filtered_docs:
                logger.debug("Skip init exist expend of chapter: %s", chapter.chapter_code)
                continue

            logger.info("Start init expend of chapter: %s", chapter.chapter_code)
            extends = await get_chapter_extends(chapter.chapter_title)
            extends_dict = extends.model_dump()
            extends_dict["chapter_code"] = chapter.chapter_code
            text = json.dumps(extends_dict)
            logger.info("Expend of chapter: %s", json.dumps(extends_dict, indent=4))
            section = await chapter.awaitable_attrs.section
            await vector_store.add_texts([text], [{"type": "chapter",
                                                   "code": chapter.chapter_code,
                                                   "section": section.section_code}])
            changed = True
    finally:
        if changed:
            vector_store.save_index()
