import json

from datetime import datetime, timezone
from pymilvus import AsyncMilvusClient, RRFRanker, AnnSearchRequest, WeightedRanker

from app.core.opensearch import get_async_opensearch_client
from app.core.constants import IndexName, MilvusCollectionName
from app.llm.embedding import default_embeddings_service
from app.service.wco_hs_service import  get_subheading_detail_by_heading_codes, \
    get_subheading_dict_by_subheading_codes
from app.service.hts_service import get_rate_lines_by_wco_subheadings


class RetrieveDocumentsService:

    def __init__(self, async_milvus_client: AsyncMilvusClient):
        self.async_milvus_client = async_milvus_client


    async def save_heading_retrieve_evaluation(self, evaluate_version: str, origin_item_name: str, rewritten_item: dict,
                                               candidate_heading_codes: list[str], actual_heading: str):
        # 保存一下获取的chapter信息用于评估准确性
        document = {
            "evaluate_version": evaluate_version,
            "origin_item_name": origin_item_name,
            "rewritten_item": rewritten_item,
            "candidate_heading_codes": candidate_heading_codes,
            "actual_heading": actual_heading,
            "matches": actual_heading in candidate_heading_codes,
            "created_at": datetime.now(timezone.utc),
        }
        async with get_async_opensearch_client() as async_client:
            await async_client.index(index=IndexName.EVALUATE_RETRIEVE_HEADING, body=document)

    async def retrieve_heading_documents(self, rewritten_item: dict):
        """
        直接获取组合后的heading层信息，不先获取chapter层了
        """
        # 增加根据语义相似度获取到的heading信息
        query_text = json.dumps(rewritten_item, ensure_ascii=False)
        query_vector = await default_embeddings_service.get_rewritten_item_embeddings(rewritten_item)
        simil_chapter_codes = set()
        # 采用混合搜索
        sparse_search_params = {"metric_type": "BM25"}
        dense_search_params = {"metric_type": "COSINE"}

        # Heading
        heading_sparse_request = AnnSearchRequest(
            [query_text], "heading_description_sparse_vector", sparse_search_params, limit=10
        )
        heading_dense_request = AnnSearchRequest(
            [query_vector], "heading_description_vector", dense_search_params, limit=10
        )
        heading_response = await self.async_milvus_client.hybrid_search(
            collection_name=MilvusCollectionName.KNOWLEDGE_HEADING.value,
            reqs=[heading_sparse_request, heading_dense_request],
            ranker=RRFRanker(),
            limit=10,
            output_fields=['chapter_code'])
        for hits in heading_response:
            for hit in hits:
                simil_chapter_codes.add(hit["entity"]["chapter_code"])
        # Chapter
        chapter_sparse_request = AnnSearchRequest(
            [query_text], "content_sparse_vector", sparse_search_params, limit=10
        )
        chapter_dense_request = AnnSearchRequest(
            [query_vector], "content_vector", dense_search_params, limit=10
        )
        chapter_response = await self.async_milvus_client.hybrid_search(
            collection_name=MilvusCollectionName.KNOWLEDGE_CHAPTER.value,
            reqs=[chapter_sparse_request, chapter_dense_request],
            ranker=RRFRanker(),
            limit=5,
            output_fields=['chapter_code'])
        for hits in chapter_response:
            for hit in hits:
                simil_chapter_codes.add(hit["entity"]["chapter_code"])

        # 检索chapter下所有heading
        filter_chapter_codes = ", ".join(f"'{item}'" for item in simil_chapter_codes)
        all_heading_response = await self.async_milvus_client.query(
            collection_name=MilvusCollectionName.KNOWLEDGE_HEADING.value,
            filter=f"chapter_code in [{filter_chapter_codes}]",
            limit=1000,
            output_fields=["heading_code", "heading_title", "heading_includes", "heading_common_examples",
                           "chapter_code", "chapter_title"],
        )
        chapter_detail_dict = {}
        candidate_heading_codes = {}
        for hit in all_heading_response:
            heading_code = hit["heading_code"]
            heading_title = hit["heading_title"]
            heading_includes = list(hit["heading_includes"])
            heading_common_examples = list(hit["heading_common_examples"])
            chapter_code = hit["chapter_code"]
            chapter_title = hit["chapter_title"]
            chapter_key = f"{chapter_code}:{chapter_title}"
            if chapter_key in chapter_detail_dict:
                chapter_details = chapter_detail_dict.get(chapter_key)
            else:
                chapter_details = []
                chapter_detail_dict.update({chapter_key: chapter_details})
            chapter_details.append({
                "heading_code": heading_code,
                "heading_title": heading_title,
                "heading_includes": heading_includes,
                "heading_common_examples": heading_common_examples
            })

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
        print(sub_heading_tree)
        print(sub_heading_detail_dict)
        candidate_rate_line_codes = {}
        for chapter_key, chapter_details in sub_heading_tree.items():
            for heading_key, heading_details in chapter_details.items():
                for subheading_key, _ in heading_details.items():
                    subheading_code = subheading_key.split(":")[0]
                    subheading_details = sub_heading_detail_dict.get(subheading_code)
                    heading_details.update({subheading_key: subheading_details})
                    codes = []
                    print(subheading_code)
                    self.get_rate_line_codes(subheading_details, codes)
                    candidate_rate_line_codes[subheading_code] = codes
        return json.dumps(sub_heading_tree, ensure_ascii=False), candidate_rate_line_codes

    def get_rate_line_codes(self, subheading_details: list, codes: []):
        if subheading_details:
            for subheading_detail in subheading_details:
                # 叶子节点：包含 rate_line_code
                if isinstance(subheading_detail, dict) and "rate_line_code" in subheading_detail:
                    codes.append(subheading_detail["rate_line_code"])

                # 分组节点：key 是描述字符串，value 是子列表
                elif isinstance(subheading_detail, dict):
                    for key, value in subheading_detail.items():
                        if isinstance(value, list):
                            self.get_rate_line_codes(value, codes)
