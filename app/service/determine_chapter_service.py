import json

from datetime import datetime, timezone
from collections import OrderedDict

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.constants import IndexName, RedisKeyPrefix
from app.core.opensearch import get_async_client
from app.core.redis import get_async_redis
from app.db.session import AsyncSessionLocal
from app.llm.prompt.prompt_template import determine_chapter_template
from app.model.hts_classify_cache_model import DetermineChapterCache
from app.repo.hts_classify_cache_repo import insert_chapter_determine_cache, select_chapter_determine_cache
from app.schema.llm.llm import ChapterDetermineResponse, ChapterDetermineResponseDetail
from app.util.hash_utils import md5_hash


class DetermineChapterService:

    def __init__(self, llm: BaseChatModel, embeddings: Embeddings):
        self.llm = llm
        self.embeddings = embeddings

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

    async def save_exact_cache(self, origin_item: str, chapter_documents: list[str], rag_version: str,
                               main_chapter: ChapterDetermineResponseDetail,
                               alternative_chapters: list[ChapterDetermineResponseDetail] | None):
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
        chapter_codes = [json.loads(document).get("chapter_code") for document in chapter_documents]
        sorted_chapter_codes = sorted(chapter_codes)
        cache_key = f"{origin_item}:{rag_version}:{sorted_chapter_codes}"
        hashed_cache_key = md5_hash(cache_key)
        main_chapter = main_chapter.model_dump()
        alternative_chapters = [chapter.model_dump() for chapter in
                                (alternative_chapters if alternative_chapters else [])]
        cache = DetermineChapterCache(origin_item_name=origin_item,
                                      cache_key=cache_key,
                                      hashed_cache_key=hashed_cache_key,
                                      rag_chapter_codes=sorted_chapter_codes,
                                      main_chapter=main_chapter,
                                      alternative_chapters=alternative_chapters)
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await insert_chapter_determine_cache(session, cache=cache)

    async def save_simil_cache(self, origin_item: str, rewritten_item: dict,
                               main_chapter: ChapterDetermineResponseDetail,
                               alternative_chapters: list[ChapterDetermineResponseDetail] | None):
        """
        保存语义模糊缓存
            存储结构化的章节信息的embedding向量信息，然后根据语义相似度获取之前确定的章节结果
        """
        # 先从缓存中获取embeddings
        document = {
            "origin_item_name": origin_item,
            "rewritten_item": rewritten_item,
            "rewritten_item_vector": await self._get_rewritten_item_embeddings(rewritten_item),
            "main_chapter": main_chapter.model_dump(),
            "alternative_chapters": [chapter.model_dump() for chapter in
                                     (alternative_chapters if alternative_chapters else [])],
            "created_at": datetime.now(timezone.utc)
        }
        async with get_async_client() as async_client:
            await async_client.index(index=IndexName.CHAPTER_CLASSIFY, body=document)

    async def get_from_cache(self, origin_item: str, rag_version: str, chapter_documents: list[str],
                             rewritten_item: dict):
        """
        从缓存获取
        """
        cache = await self._get_exact_cache(origin_item, rag_version, chapter_documents)
        if cache.get("hit_chapter_cache"):
            return cache
        return await self._get_simil_cache(rewritten_item)

    async def _get_exact_cache(self, origin_item: str, rag_version: str, chapter_documents: list[str]):
        """
        获取用户输入精确匹配缓存
        """
        chapter_codes = [json.loads(document).get("chapter_code") for document in chapter_documents]
        sorted_chapter_codes = sorted(chapter_codes)
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

    async def _get_simil_cache(self, rewritten_item: dict):
        """
        获取语义相似缓存
        """
        rewritten_item_vector = await self._get_rewritten_item_embeddings(rewritten_item)
        # 从opensearch中获取缓存
        async with get_async_client() as async_client:
            response = await async_client.search(index=IndexName.CHAPTER_CLASSIFY.value, body={
                "query": {
                    "knn": {
                        "rewritten_item_vector": {
                            "vector": rewritten_item_vector,
                            "k": 1
                        }
                    }
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

    async def _get_rewritten_item_embeddings(self, rewritten_item: dict) -> list[float]:
        """
        获取改写商品的embeddings，优先使用redis缓存，如果没有走接口获取，然后缓存到redis中
        """
        rewritten_item_vector = None
        ordered_rewritten_item = OrderedDict(sorted(rewritten_item.items()))
        rewritten_item_json = json.dumps(ordered_rewritten_item)
        redis_hash_key = f"{RedisKeyPrefix.REWRITTEN_ITEM_EMBEDDINGS.value}:{md5_hash(rewritten_item_json)}"
        async_redis = await get_async_redis()
        vector_json = await async_redis.get(redis_hash_key)
        if vector_json:
            rewritten_item_vector = json.loads(vector_json)
        if rewritten_item_vector is None:
            rewritten_item_vector = await self.embeddings.aembed_query(rewritten_item_json)
            # 将llm返回的embedding缓存到redis
            await async_redis.set(redis_hash_key, json.dumps(rewritten_item_vector))
        return rewritten_item_vector
