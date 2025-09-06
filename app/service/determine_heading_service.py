"""
确定类目服务
"""
from langchain_core.embeddings import Embeddings
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.language_models import BaseChatModel

from app.core.opensearch import get_async_opensearch_client
from app.llm.prompt.prompt_template import determine_heading_template
from app.schema.llm.llm import HeadingDetermineResponse, HeadingDetermineResponseDetail
from app.service.rewrite_item_service import RewriteItemEmbeddingsService
from app.core.constants import IndexName

from datetime import datetime, timezone


class DetermineHeadingService:

    def __init__(self, llm: BaseChatModel, embeddings: Embeddings):
        self.llm = llm
        self.embeddings = embeddings
        self.rewritten_item_embeddings_service = RewriteItemEmbeddingsService(embeddings=embeddings)

    async def determine_use_llm(self, rewritten_item, heading_documents: str):
        """
        由LLM确定所属类目
        """
        parser = PydanticOutputParser(pydantic_object=HeadingDetermineResponse)
        format_instructions = parser.get_format_instructions()
        prompt = PromptTemplate(template=determine_heading_template,
                                input_variables=["item", "heading_scope"],
                                partial_variables={"format_instructions": format_instructions})

        human_message = prompt.invoke({"item": rewritten_item,
                                       "heading_scope": heading_documents}).to_messages()[0]

        output = await self.llm.ainvoke(input=[human_message])

        return human_message, output, parser.parse(output.content)

    async def save_simil_cache(self, origin_item_name: str, rewritten_item: dict, chapter_codes: list[str],
                               alternative_headings: list[dict] | None):
        """
        保存语义相似度缓存
        """
        rewritten_item_vector = await self.rewritten_item_embeddings_service.get_rewritten_item_embeddings(
            rewritten_item)
        document = {
            "origin_item_name": origin_item_name,
            "rewritten_item": rewritten_item,
            "rewritten_item_vector": rewritten_item_vector,
            "chapter_codes": str(sorted(chapter_codes)),
            "alternative_headings": alternative_headings,
            "created_at": datetime.now(timezone.utc)
        }
        async with get_async_opensearch_client() as async_client:
            await async_client.index(index=IndexName.HEADING_CLASSIFY, body=document)

    async def get_simil_cache(self, rewritten_item: dict, chapter_codes: list[str], ):
        """
        获取语义相似度缓存
        """
        sorted_chapter_codes = str(sorted(chapter_codes))
        rewritten_item_vector = await self.rewritten_item_embeddings_service.get_rewritten_item_embeddings(
            rewritten_item)
        async with get_async_opensearch_client() as async_client:
            response = await async_client.search(index=IndexName.HEADING_CLASSIFY, body={
                "query": {
                    "bool": {
                        "must": [
                            {
                                "knn": {
                                    "rewritten_item_vector": {
                                        "vector": rewritten_item_vector,
                                        "k": 100
                                    }
                                }
                            }
                        ],
                        "filter": [
                            {"term": {"chapter_codes": sorted_chapter_codes}}
                        ]
                    }
                }
            })
            if response["hits"]["total"]["value"] > 0:
                score = response["hits"]["hits"][0]["_score"]
                print(f"Heading cache similarity score:{score}")
                # 相似度得分达到指定阈值的，直接返回结果，否则流程继续向下流转
                if score > 0.95:
                    return {
                        "hit_heading_cache": True,
                        "alternative_headings": response["hits"]["hits"][0]["_source"]["alternative_headings"],
                    }
            return {"hit_heading_cache": False}

    async def save_for_evaluation(self,
                                  evaluate_version: str,
                                  origin_item_name: str,
                                  heading_documents: str,
                                  llm_response: HeadingDetermineResponse,
                                  actual_heading: str):
        """
        保存评估过程信息
        """
        determine_heading_codes = [heading.heading_code for heading in llm_response.alternative_headings]
        document = {
            "evaluate_version": evaluate_version,
            "origin_item_name": origin_item_name,
            "heading_documents": heading_documents,
            "llm_response": llm_response.model_dump(),
            "actual_heading": actual_heading,
            "matches": actual_heading in determine_heading_codes,
            "created_at": datetime.now(timezone.utc),
        }
        async with get_async_opensearch_client() as async_client:
            await async_client.index(index=IndexName.EVALUATE_LLM_CONFIRM_HEADING, body=document)
