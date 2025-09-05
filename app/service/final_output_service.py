from datetime import datetime, timezone

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.opensearch import get_async_opensearch_client
from app.db.session import AsyncSessionLocal
from app.llm.prompt.prompt_template import generate_final_output_template
from app.model.hts_classify_cache_model import HtsClassifyE2ECache
from app.repo.hts_classify_cache_repo import insert_e2e_cache
from app.service.rewrite_item_service import RewriteItemEmbeddingsService
from app.schema.llm.llm import GenerateFinalOutputResponse
from app.core.constants import IndexName


class FinalOutputService:

    def __init__(self, llm: BaseChatModel, embeddings: Embeddings):
        self.llm = llm
        self.embeddings = embeddings
        self.rewrite_item_embeddings_service = RewriteItemEmbeddingsService(embeddings=self.embeddings)

    async def get_final_output_from_llm(self, origin_item_name: str, rewritten_item: dict,
                                        heading_candidates: list, selected_heading: str, select_heading_reason: str,
                                        subheading_candidates: list, selected_subheading: str,
                                        select_subheading_reason: str,
                                        rate_line_candidates: list, selected_rate_line: str,
                                        select_rate_line_reason: str):
        parser = PydanticOutputParser(pydantic_object=GenerateFinalOutputResponse)
        format_instructions = parser.get_format_instructions()

        prompt = PromptTemplate(template=generate_final_output_template,
                                input_variables=["original_item", "rewritten_item",
                                                 "heading_candidates", "selected_heading", "reason_heading",
                                                 "subheading_candidates", "selected_subheading", "reason_subheading",
                                                 "rate_line_candidates", "selected_rate_line", "reason_rate_line",
                                                 "final_code"],
                                partial_variables={"format_instructions": format_instructions})

        human_message = prompt.invoke({"original_item": origin_item_name,
                                       "rewritten_item": rewritten_item,
                                       "heading_candidates": heading_candidates,
                                       "selected_heading": selected_heading,
                                       "reason_heading": select_heading_reason,
                                       "subheading_candidates": subheading_candidates,
                                       "selected_subheading": selected_subheading,
                                       "reason_subheading": select_subheading_reason,
                                       "rate_line_candidates": rate_line_candidates,
                                       "selected_rate_line": selected_rate_line,
                                       "reason_rate_line": select_rate_line_reason,
                                       "final_code": selected_rate_line}).to_messages()[0]

        output = await self.llm.ainvoke(input=[human_message])

        return human_message, output, parser.parse(output.content)

    async def save_e2e_exact_cache(self, origin_item_name: str, rewritten_item: dict,
                                   chapter_code,
                                   heading_code, heading_title, heading_reason,
                                   subheading_code, subheading_title, subheading_reason,
                                   rate_line_code, rate_line_title, rate_line_reason,
                                   final_output_response: GenerateFinalOutputResponse):
        cache = HtsClassifyE2ECache(origin_item_name=origin_item_name,
                                    name_cn=rewritten_item.get("cn_name"),
                                    name_en=rewritten_item.get("en_name"),
                                    classification_name_cn=rewritten_item.get("classification_name_cn"),
                                    classification_name_en=rewritten_item.get("classification_name_en"),
                                    brand=rewritten_item.get("brand"),
                                    material=rewritten_item.get("material"),
                                    purpose=rewritten_item.get("purpose"),
                                    specifications=rewritten_item.get("specifications"),
                                    processing_state=rewritten_item.get("processing_state"),
                                    special_properties=rewritten_item.get("special_properties"),
                                    other_notes=rewritten_item.get("other_notes"),
                                    chapter_code=chapter_code,
                                    heading_code=heading_code,
                                    heading_title=heading_title,
                                    heading_reason=heading_reason,
                                    subheading_code=subheading_code,
                                    subheading_title=subheading_title,
                                    subheading_reason=subheading_reason,
                                    rate_line_code=rate_line_code,
                                    rate_line_title=rate_line_title,
                                    rate_line_reason=rate_line_reason,
                                    final_output_reason=final_output_response.final_output_reason)
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await insert_e2e_cache(session, cache)

    async def save_e2e_simil_cache(self, origin_item_name: str, rewritten_item: dict,
                                   rate_line_code, rate_line_title,
                                   final_output_response: str):
        document = {
            "origin_item_name": origin_item_name,
            "rewritten_item": rewritten_item,
            "rewritten_item_vector": await self.rewrite_item_embeddings_service.get_rewritten_item_embeddings(rewritten_item),
            "rate_line_code": rate_line_code,
            "rate_line_title": rate_line_title,
            "final_description": final_output_response,
            "created_at": datetime.now(timezone.utc)
        }
        async with get_async_opensearch_client() as async_client:
            await async_client.index(index=IndexName.CLASSIFY_E2E_CACHE.value, body=document)

    async def get_e2e_simil_cache(self, rewritten_item: dict):
        async with get_async_opensearch_client() as async_client:
            response = await async_client.search(index=IndexName.CLASSIFY_E2E_CACHE.value, body={
                "query": {
                    "knn": {
                        "rewritten_item_vector": {
                            "vector": await self.rewrite_item_embeddings_service.get_rewritten_item_embeddings(
                                rewritten_item),
                            "k": 1
                        }
                    }
                }
            })
            if response["hits"]["total"]["value"] > 0:
                score = response["hits"]["hits"][0]["_score"]
                print(f"English similarity score:{score}")
                if score > 0.95:
                    return {
                        "hit_e2e_simil_cache": True,
                        "final_rate_line_code": response["hits"]["hits"][0]["_source"]["rate_line_code"],
                        "final_description": response["hits"]["hits"][0]["_source"]["final_description"]
                    }
            return {"hit_e2e_simil_cache": False}
