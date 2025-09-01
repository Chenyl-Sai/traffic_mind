import json

from datetime import datetime, timezone

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.constants import IndexName
from app.core.opensearch import get_async_opensearch_client
from app.db.session import AsyncSessionLocal
from app.llm.prompt.prompt_template import determine_chapter_template
from app.model.hts_classify_cache_model import DetermineChapterCache
from app.repo.hts_classify_cache_repo import insert_chapter_determine_cache, select_chapter_determine_cache
from app.schema.llm.llm import ChapterDetermineResponse
from app.service.rewrite_item_service import RewriteItemEmbeddingsService
from app.util.hash_utils import md5_hash


class DetermineChapterService:

    def __init__(self, llm: BaseChatModel, embeddings: Embeddings):
        self.llm = llm
        self.embeddings = embeddings
        self.rewritten_item_embeddings_service = RewriteItemEmbeddingsService(embeddings=embeddings)

    async def determine_use_llm(self, rewritten_item: dict, chapter_documents: list[str]):
        parser = PydanticOutputParser(pydantic_object=ChapterDetermineResponse)
        format_instructions = parser.get_format_instructions()
        prompt = PromptTemplate(template=determine_chapter_template,
                                input_variables=["item", "chapter_list"],
                                partial_variables={"format_instructions": format_instructions})

        human_message = prompt.invoke({
            "item": rewritten_item,
            "chapter_list": chapter_documents
        }).to_messages()[0]

        output = await self.llm.ainvoke(input=[human_message])

        return human_message, output, parser.parse(output.content)

    async def process_llm_response(self, llm_response: ChapterDetermineResponse):
        main_chapter = llm_response.main_chapter
        alternative_chapters = llm_response.alternative_chapters
        fail_reason = llm_response.reason

        if main_chapter:
            final_alternative_chapters = [
                chapter.model_dump() for chapter in (alternative_chapters if alternative_chapters else [])
            ]
            # # 由于分类中存在一些类似96章这种兜底的，语义模糊的章节，容易被rag和llm过滤掉，将这些模糊章节强制添加到候选中
            # exists_codes = ([main_chapter.chapter_code] +
            #                 [alternative_chapter.chapter_code for alternative_chapter in
            #                  (alternative_chapters if alternative_chapters else [])])
            # white_list_codes = []

            return {
                "determine_chapter_success": True,
                "main_chapter": main_chapter.model_dump(),
                "alternative_chapters": final_alternative_chapters
            }
        # TODO 失败直接先抛出异常
        raise Exception(fail_reason)

    async def save_exact_cache(self, origin_item: str, sorted_chapter_codes: list[str], rag_version: str,
                               main_chapter: dict,
                               alternative_chapters: list[dict] | None):
        """
        保存精确匹配的缓存
            1. 相同的用户输入，经过llm改写之后会出现不同的改写结果(即使设置了temperature,还得固定模型快照版本，不利于升级),
            所以精确缓存使用用户原始输入
            2. chapter信息存在变化、更新的可能，所以需要将chapter也添加到缓存key，当chapter过期之后自动过期相应缓存
        @Params:
            origin_item: 用户原始输入
            chapter_documents: 检索结果
            rag_version: rag文档的版本
            determine_result: 确定结果
        """
        # 从检索结果中获取章节编码
        cache_key = f"{origin_item}:{rag_version}:{sorted_chapter_codes}"
        hashed_cache_key = md5_hash(cache_key)
        cache = DetermineChapterCache(origin_item_name=origin_item,
                                      cache_key=cache_key,
                                      hashed_cache_key=hashed_cache_key,
                                      rag_chapter_codes=sorted_chapter_codes,
                                      main_chapter=main_chapter,
                                      alternative_chapters=alternative_chapters)
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await insert_chapter_determine_cache(session, cache=cache)

    async def save_simil_cache(self, origin_item: str, rewritten_item: dict, sorted_chapter_codes: list[str],
                               main_chapter: dict,
                               alternative_chapters: list[dict] | None):
        """
        保存语义模糊缓存
            存储结构化的章节信息的embedding向量信息，然后根据语义相似度获取之前确定的章节结果
        """
        # 先从缓存中获取embeddings
        document = {
            "origin_item_name": origin_item,
            "rewritten_item": rewritten_item,
            "rewritten_item_vector": await self.rewritten_item_embeddings_service.get_rewritten_item_embeddings(
                rewritten_item),
            "rag_chapter_codes": str(sorted_chapter_codes),
            "main_chapter": main_chapter,
            "alternative_chapters": alternative_chapters,
            "created_at": datetime.now(timezone.utc)
        }
        async with get_async_opensearch_client() as async_client:
            await async_client.index(index=IndexName.CHAPTER_CLASSIFY, body=document)

    async def get_from_cache(self, origin_item: str, rag_version: str, chapter_documents: list[str],
                             rewritten_item: dict):
        """
        从缓存获取
        """
        chapter_codes = [json.loads(document).get("chapter_code") for document in chapter_documents]
        sorted_chapter_codes = sorted(chapter_codes)
        cache = await self._get_exact_cache(origin_item, rag_version, sorted_chapter_codes)
        if cache.get("hit_chapter_cache"):
            return cache
        return await self._get_simil_cache(rewritten_item, sorted_chapter_codes)

    async def _get_exact_cache(self, origin_item: str, rag_version: str, sorted_chapter_codes: list[str]):
        """
        获取用户输入精确匹配缓存
        """
        cache_key = f"{origin_item}:{rag_version}:{sorted_chapter_codes}"
        print(f"Exact Search CacheKey:{cache_key}")
        hashed_cache_key = md5_hash(cache_key)
        async with AsyncSessionLocal() as session:
            cache = await select_chapter_determine_cache(session, hashed_cache_key)
            if cache:
                return {
                    "hit_chapter_cache": True,
                    "main_chapter": cache.main_chapter,
                    "alternative_chapters": cache.alternative_chapters
                }
        return {"hit_chapter_cache": False}

    async def _get_simil_cache(self, rewritten_item: dict, sorted_chapter_codes: list[str]):
        """
        获取语义相似缓存
        """
        rewritten_item_vector = await self.rewritten_item_embeddings_service.get_rewritten_item_embeddings(
            rewritten_item)
        # 从opensearch中获取缓存
        async with get_async_opensearch_client() as async_client:
            response = await async_client.search(index=IndexName.CHAPTER_CLASSIFY.value, body={
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"rag_chapter_codes": str(sorted_chapter_codes)}}
                        ],
                        "must": [
                            {
                                "knn": {
                                    "rewritten_item_vector": {
                                        "vector": rewritten_item_vector,
                                        "k": 100
                                    }
                                }}
                        ]
                    },
                }
            })
            if response["hits"]["total"]["value"] > 0:
                score = response["hits"]["hits"][0]["_score"]
                print(f"Chapter cache similarity score:{score}")
                if score > 0.95:
                    return {
                        "hit_chapter_cache": True,
                        "main_chapter": response["hits"]["hits"][0]["_source"]["main_chapter"],
                        "alternative_chapters": response["hits"]["hits"][0]["_source"]["alternative_chapters"]
                    }
        return {"hit_chapter_cache": False}

    async def save_llm_confirm_result_for_evaluation(self,
                                                     evaluate_version: str,
                                                     origin_item: str,
                                                     rewritten_item: dict,
                                                     retrieved_chapter_codes: list[str],
                                                     llm_response: ChapterDetermineResponse,
                                                     actual_chapter: str):
        """
        保存章节确认结果用于评估
        """
        document = {
            "evaluate_version": evaluate_version,
            "origin_item_name": origin_item,
            "rewritten_item": rewritten_item,
            "retrieved_chapter_codes": retrieved_chapter_codes,
            "llm_response": llm_response.model_dump(),
            "actual_chapter": actual_chapter,
            "created_at": datetime.now(timezone.utc),
        }
        async with get_async_opensearch_client() as async_client:
            await async_client.index(index=IndexName.EVALUATE_LLM_CONFIRM_CHAPTER, body=document)
