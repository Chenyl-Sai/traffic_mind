import json

from datetime import datetime, timezone

from app.service.vector_store_service import FAISSVectorStore
from app.core.opensearch import get_async_opensearch_client
from app.core.constants import IndexName
from app.service.wco_hs_service import get_heading_detail_by_chapter_codes, get_subheading_detail_by_heading_codes, \
    get_subheading_dict_by_subheading_codes
from app.service.hts_service import get_rate_lines_by_wco_subheadings


class RetrieveDocumentsService:

    def __init__(self, chapter_vectorstore: FAISSVectorStore):
        self.chapter_vectorstore = chapter_vectorstore

    async def retrieve_chapter_documents(self, rewritten_item: dict):
        """
        从向量数据库中检索相关章节
        """
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
        async with get_async_opensearch_client() as async_client:
            await async_client.index(index=IndexName.EVALUATE_RETRIEVE_CHAPTER, body=document)

    async def retrieve_heading_documents(self, chapter_codes: list[str]) -> str:
        """
        根据章节编码检索heading信息
        """
        chapter_detail_dict = await get_heading_detail_by_chapter_codes(chapter_codes)
        return json.dumps(chapter_detail_dict, ensure_ascii=False)

    async def retrieve_subheading_documents(self, heading_codes: list[str]) -> str:
        """
        根据heading编码检索subheading信息
        """
        heading_detail_dict = await get_subheading_detail_by_heading_codes(heading_codes)
        return json.dumps(heading_detail_dict, ensure_ascii=False)

    async def retrieve_rate_line_documents(self, subheading_codes: list[str]) -> str:
        """
        检索子目下面的税率线信息
        """
        sub_heading_tree = await get_subheading_dict_by_subheading_codes(subheading_codes)
        sub_heading_detail_dict = await get_rate_lines_by_wco_subheadings(subheading_codes)
        for chapter_key, chapter_details in sub_heading_tree.items():
            for heading_key, heading_details in chapter_details.items():
                for subheading_key, _ in heading_details.items():
                    sub_heading_code = subheading_key.split(":")[0]
                    subheading_details = sub_heading_detail_dict.get(sub_heading_code)
                    heading_details.update({subheading_key: subheading_details})
        return json.dumps(sub_heading_tree, ensure_ascii=False)
