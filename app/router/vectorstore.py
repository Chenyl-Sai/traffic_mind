from fastapi import APIRouter

from app.core.constants import MilvusCollectionName
from app.dep.milvus import MilvusChapterKnowledgeDep, MilvusHeadingKnowledgeDep

vector_store_router = APIRouter()


@vector_store_router.get("/search_related_chapters")
async def search_related_chapters(async_milvus_client: MilvusChapterKnowledgeDep,
                                  query_text: str, k: int = 5):
    return await async_milvus_client.search(collection_name=MilvusCollectionName.KNOWLEDGE_CHAPTER.value,
                                            data=[query_text],
                                            anns_field="content_vector",
                                            limit=k,
                                            output_fields=["content"])


@vector_store_router.get("/search_related_headings")
async def search_related_headings(async_milvus_client: MilvusHeadingKnowledgeDep,
                                  query_text: str, k: int = 5):
    return await async_milvus_client.search(collection_name=MilvusCollectionName.KNOWLEDGE_HEADING.value,
                                            data=[query_text],
                                            anns_field="title_vector",
                                            limit=k,
                                            output_fields=["heading_code", "heading_title", "chapter_code"])
