import json

from datetime import datetime, timezone

from app.service.vector_store_service import FAISSVectorStore
from app.core.opensearch import get_async_client
from app.core.constants import IndexName


class RetrieveDocumentsService:

    def __init__(self, chapter_vectorstore: FAISSVectorStore):
        self.chapter_vectorstore = chapter_vectorstore

    async def retrieve_chapter_documents(self, rewritten_item: dict):
        query_text = json.dumps(rewritten_item)
        chapter_documents = await self.chapter_vectorstore.search(query_text=query_text,
                                                                  search_type="similarity",
                                                                  filter={"type": "chapter"},
                                                                  k=10)
        return [document.page_content for document in chapter_documents] if chapter_documents else []

    async def save_chapter_retrieve_evaluation(self, evaluate_version: str, origin_item_name: str, rewritten_item: dict,
                                               chapter_documents: list[dict]):
        # 保存一下获取的chapter信息用于评估准确性
        document = {
            "evaluate_version": evaluate_version,
            "origin_item_name": origin_item_name,
            "rewritten_item": rewritten_item,
            "chapter_documents": chapter_documents,
            "created_at": datetime.now(timezone.utc),
        }
        async with get_async_client() as async_client:
            await async_client.index(index=IndexName.EVALUATE_RETRIEVE_CHAPTER, body=document)
