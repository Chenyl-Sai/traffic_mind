import json

from datetime import datetime, timezone

from app.db.session import AsyncSessionLocal
from app.service.vector_store_service import FAISSVectorStore
from app.core.opensearch import get_async_opensearch_client
from app.core.constants import IndexName
from app.service.wco_hs_service import get_heading_detail_by_chapter_codes, get_subheading_detail_by_heading_codes, \
    get_subheading_dict_by_subheading_codes, get_headings_by_heading_codes, get_chapters_by_chapter_codes
from app.service.hts_service import get_rate_lines_by_wco_subheadings


class RetrieveDocumentsService:

    def __init__(self, vectorstore: FAISSVectorStore):
        self.vectorstore = vectorstore

    async def retrieve_chapter_documents(self, rewritten_item: dict):
        """
        从向量数据库中检索相关章节
        """
        query_text = json.dumps(rewritten_item)
        chapter_documents = await self.vectorstore.search(query_text=query_text,
                                                          search_type="similarity",
                                                          filter={"type": "chapter"},
                                                          k=10)
        chapters = [document.page_content for document in chapter_documents] if chapter_documents else []
        chapter_codes = [json.loads(chapter).get("chapter_code") for chapter in chapters]
        return chapters, chapter_codes

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

    async def retrieve_heading_documents(self, rewritten_item: dict, chapter_codes: list[str]):
        """
        根据章节编码检索heading信息
        """
        # 查询LLM决策的章节下的heading信息
        chapter_detail_dict = await get_heading_detail_by_chapter_codes(chapter_codes)
        # 增加根据语义相似度获取到的heading信息
        query_text = json.dumps(rewritten_item)
        heading_documents = await self.vectorstore.search(query_text=query_text,
                                                          search_type="similarity",
                                                          filter={"type": "heading"},
                                                          k=10,
                                                          fetch_k=100)
        simil_heading_chapter_codes = [heading_document.metadata.get("chapter_code") for heading_document in
                                       heading_documents]
        async with AsyncSessionLocal() as session:
            simil_chapters = await get_chapters_by_chapter_codes(session, simil_heading_chapter_codes)
            simil_chapter_key_dict = {chapter.chapter_code: (chapter.chapter_code + ":" + chapter.chapter_title)
                                      for chapter in simil_chapters}
            for heading_document in heading_documents:
                heading = json.loads(heading_document.page_content)
                chapter_key = simil_chapter_key_dict.get(heading_document.metadata.get("chapter_code"))
                if chapter_key in chapter_detail_dict:
                    exists_heading = next((chapter_detail for chapter_detail in chapter_detail_dict.get(chapter_key) if
                                           chapter_detail.get("heading_code") == heading.get("heading_code")), None)
                    if not exists_heading:
                        chapter_detail_dict.get(chapter_key).append(heading)
                else:
                    chapter_detail_dict[chapter_key] = [heading]

        candidate_heading_codes = {}
        for chapter_code_and_title, chapter_detail in chapter_detail_dict.items():
            chapter_code = chapter_code_and_title.split(":")[0]
            heading_codes = [heading.get("heading_code") for heading in chapter_detail]
            candidate_heading_codes[chapter_code] = heading_codes
        return json.dumps(chapter_detail_dict, ensure_ascii=False), candidate_heading_codes

    async def retrieve_subheading_documents(self, heading_codes: list[str]):
        """
        根据heading编码检索subheading信息
        """
        heading_detail_dict = await get_subheading_detail_by_heading_codes(heading_codes)
        candidate_subheading_codes = {}
        for chapter_code_and_title, chapter_details in heading_detail_dict.items():
            for heading_code_and_title, heading_details in chapter_details.items():
                heading_code = heading_code_and_title.split(":")[0]
                subheading_codes = [subheading.get("subheading_code") for subheading in heading_details]
                candidate_subheading_codes[heading_code] = subheading_codes
        return json.dumps(heading_detail_dict, ensure_ascii=False), candidate_subheading_codes

    async def retrieve_rate_line_documents(self, subheading_codes: list[str]):
        """
        检索子目下面的税率线信息
        """
        sub_heading_tree = await get_subheading_dict_by_subheading_codes(subheading_codes)
        sub_heading_detail_dict = await get_rate_lines_by_wco_subheadings(subheading_codes)
        candidate_rate_line_codes = {}
        for chapter_key, chapter_details in sub_heading_tree.items():
            for heading_key, heading_details in chapter_details.items():
                for subheading_key, _ in heading_details.items():
                    subheading_code = subheading_key.split(":")[0]
                    subheading_details = sub_heading_detail_dict.get(subheading_code)
                    heading_details.update({subheading_key: subheading_details})
                    codes = []
                    self.get_rate_line_codes(subheading_details, codes)
                    candidate_rate_line_codes[subheading_code] = codes
        return json.dumps(sub_heading_tree, ensure_ascii=False), candidate_rate_line_codes

    def get_rate_line_codes(self, subheading_details: list, codes: []):
        for subheading_detail in subheading_details:
            # 叶子节点：包含 rate_line_code
            if isinstance(subheading_detail, dict) and "rate_line_code" in subheading_detail:
                codes.append(subheading_detail["rate_line_code"])

            # 分组节点：key 是描述字符串，value 是子列表
            elif isinstance(subheading_detail, dict):
                for key, value in subheading_detail.items():
                    if isinstance(value, list):
                        self.get_rate_line_codes(value, codes)
