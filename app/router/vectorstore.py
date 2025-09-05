import json, asyncio

from fastapi import APIRouter

from app.core.constants import MilvusCollectionName
from app.dep.milvus import MilvusChapterKnowledgeDep, MilvusHeadingKnowledgeDep
from app.dep.db import SessionDep
from app.init.embeddings_init import build_chapter_knowledge_collection, build_heading_knowledge_collection
from app.llm.embedding import default_embeddings_service
from app.model.milvus.knowledge_model import ChapterKnowledge, HeadingKnowledge

vector_store_router = APIRouter()


@vector_store_router.get("/search_related_chapters")
async def search_related_chapters(async_milvus_client: MilvusChapterKnowledgeDep,
                                  query_text: str, k: int = 5):
    return await async_milvus_client.search(collection_name=MilvusCollectionName.KNOWLEDGE_CHAPTER.value,
                                            data=[await default_embeddings_service.get_embeddings_for_str(query_text)],
                                            anns_field="content_vector",
                                            limit=k,
                                            output_fields=["content"])


@vector_store_router.get("/search_related_headings")
async def search_related_headings(async_milvus_client: MilvusHeadingKnowledgeDep,
                                  query_text: str, k: int = 5):
    return await async_milvus_client.search(collection_name=MilvusCollectionName.KNOWLEDGE_HEADING.value,
                                            data=[await default_embeddings_service.get_embeddings_for_str(query_text)],
                                            anns_field="heading_description_vector",
                                            limit=k,
                                            output_fields=["heading_code", "heading_title", "chapter_code"])


@vector_store_router.post("/init_chapter_knowledge")
async def init_chapter_knowledge(session: SessionDep,
                                 async_milvus_client: MilvusChapterKnowledgeDep):
    """
    初始化章节知识向量
    """
    await build_chapter_knowledge_collection(session, async_milvus_client)
    return "init success"


@vector_store_router.post("/init_heading_knowledge")
async def init_chapter_knowledge(session: SessionDep,
                                 async_milvus_client: MilvusHeadingKnowledgeDep):
    """
    初始化章节知识向量
    """
    await build_heading_knowledge_collection(session, async_milvus_client)
    return "init success"


@vector_store_router.post("/transfer_old_chapter_to_new")
async def transfer_old_chapter_to_new(async_milvus_client: MilvusChapterKnowledgeDep):
    """
    将旧版章节知识向量数据迁移到新版本
    """
    response = await async_milvus_client.query(collection_name="hts_knowledge_chapter", limit=1000,
                                               output_fields=["chapter_code", "chapter_title", "section_code",
                                                              "includes", "common_examples", "content",
                                                              "content_vector"])
    for record in response:
        chapter = ChapterKnowledge(**record)
        await async_milvus_client.insert(collection_name="hts_knowledge_chapter_temp", data=[chapter.model_dump()])
    return "transfer finish"


@vector_store_router.post("/transfer_old_heading_to_new")
async def transfer_old_heading_to_new(async_milvus_client: MilvusHeadingKnowledgeDep):
    """
    将旧版章节知识向量数据迁移到新版本
    """
    response = await async_milvus_client.query(collection_name="hts_knowledge_heading_temp",
                                               filter="heading_title=='[deleted]'",
                                               limit=10000,
                                               output_fields=["id", "heading_code", "heading_title", "heading_includes",
                                                              "heading_common_examples", "heading_description",
                                                              "chapter_code", "chapter_title", "chapter_description"])
    tasks = []
    for record in response:
        await async_milvus_client.delete(collection_name="hts_knowledge_heading_temp", ids=record["id"])
        record["id"] = None
        record["heading_includes"] = []
        record["heading_common_examples"] = []
        record["heading_description"] = json.dumps({
            "heading_title": record["heading_title"],
            "includes": [],
            "common_examples": []
        }, ensure_ascii=False)
        record["heading_description_vector"] = await default_embeddings_service.get_embeddings_for_str(
            record.get("heading_description"))
        heading = HeadingKnowledge(**record)
        tasks.append(
            async_milvus_client.insert(collection_name="hts_knowledge_heading_temp", data=[heading.model_dump()]))
        if len(tasks) == 50:
            await asyncio.gather(*tasks)
            tasks = []
    if tasks:
        await asyncio.gather(*tasks)
    return "transfer finish"
