"""
确定子目服务
"""
from datetime import datetime, timezone

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.opensearch import get_async_client
from app.llm.prompt.prompt_template import determine_subheading_template
from app.schema.llm.llm import SubheadingDetermineResponse
from app.service.rewrite_item_service import RewriteItemEmbeddingsService
from app.core.constants import IndexName


class DetermineSubheadingService:

    def __init__(self, llm: BaseChatModel, embeddings: Embeddings):
        self.llm = llm
        self.embeddings = embeddings
        self.rewrite_item_embeddings_service = RewriteItemEmbeddingsService(embeddings=self.embeddings)

    async def determine_use_llm(self, rewritten_item: dict, subheading_documents: str):
        """
        使用llm确定子目
        """

        parser = PydanticOutputParser(pydantic_object=SubheadingDetermineResponse)
        format_instructions = parser.get_format_instructions()
        prompt = PromptTemplate(template=determine_subheading_template,
                                input_variables=["item", "subheading_list"],
                                partial_variables={"format_instructions": format_instructions})

        human_message = prompt.invoke({"item": rewritten_item,
                                       "subheading_list": subheading_documents}).to_messages()[0]

        output = await self.llm.ainvoke(input=[human_message])

        return human_message, output, parser.parse(output.content)

    async def save_simil_cache(self, origin_item_name: str, rewritten_item: dict,
                               heading_codes: list[str],
                               main_subheading: dict,
                               alternative_subheadings: list[dict] | None):
        """
        保存缓存
        """
        sorted_heading_codes = str(sorted(heading_codes))
        document = {
            "origin_item_name": origin_item_name,
            "rewritten_item": rewritten_item,
            "rewritten_item_vector": await self.rewrite_item_embeddings_service.get_rewritten_item_embeddings(
                rewritten_item),
            "heading_codes": sorted_heading_codes,
            "main_subheading": main_subheading,
            "alternative_subheadings": alternative_subheadings,
            "created_at": datetime.now(timezone.utc)
        }
        async with get_async_client() as async_client:
            await async_client.index(index=IndexName.SUBHEADING_CLASSIFY.value, body=document)

    async def get_simil_cache(self, rewritten_item: dict, heading_codes: list[str]):
        """
        获取缓存
        """
        sorted_heading_codes = str(sorted(heading_codes))
        rewritten_item_vector = await self.rewrite_item_embeddings_service.get_rewritten_item_embeddings(
            rewritten_item)
        async with get_async_client() as async_client:
            response = await async_client.search(index=IndexName.SUBHEADING_CLASSIFY.value, body={
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
                            {"term": {"heading_codes": sorted_heading_codes}}
                        ]
                    }
                }
            })
            if response["hits"]["total"]["value"] > 0:
                score = response["hits"]["hits"][0]["_score"]
                print(f"Subheading cache similarity score:{score}")
                # 相似度得分达到指定阈值的，直接返回结果，否则流程继续向下流转
                if score > 0.95:
                    return {
                        "hit_subheading_cache": True,
                        "main_subheading": response["hits"]["hits"][0]["_source"]["main_subheading"],
                        "alternative_subheadings": response["hits"]["hits"][0]["_source"]["alternative_subheadings"],
                    }
            return {"hit_subheading_cache": False}

    async def save_for_evaluation(self, evaluate_version: str, origin_item_name: str, subheading_documents: str,
                                  llm_response: SubheadingDetermineResponse):
        """
        保存用于评估的信息
        """
        document = {
            "evaluate_version": evaluate_version,
            "origin_item_name": origin_item_name,
            "subheading_documents": subheading_documents,
            "llm_response": llm_response.model_dump(),
            "created_at": datetime.now(timezone.utc)
        }
        async with get_async_client() as async_client:
            await async_client.index(index=IndexName.EVALUATE_LLM_CONFIRM_SUBHEADING, body=document)
