from langchain_core.language_models import BaseChatModel

from app.db.session import AsyncSessionLocal
from app.model.hts_classify_cache_model import ItemRewriteCache
from app.repo.hts_classify_cache_repo import insert_item_rewrite_cache, select_item_rewrite_cache
from app.core.opensearch import get_async_opensearch_client
from app.core.constants import IndexName, RedisKeyPrefix
from app.schema.llm.llm import ItemRewriteResponse
from app.llm.prompt.prompt_template import rewrite_item_template
from app.util.hash_utils import md5_hash
from app.core.redis import get_async_redis

from datetime import datetime, timezone
from collections import OrderedDict
from langchain.embeddings.base import Embeddings
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

import json


class ItemRewriteCacheService:

    def __init__(self, embeddings: Embeddings, llm: BaseChatModel, backup_llm: BaseChatModel ):
        self.embeddings = embeddings
        self.llm = llm
        self.backup_llm = backup_llm


    async def get_from_cache(self, item:str):
        """
        从缓存获取之前的改写结果
        """
        # 首先使用原始名称从数据库精确查询
        async with AsyncSessionLocal() as session:
            cache = await select_item_rewrite_cache(session, item)
            if cache:
                return {
                    "hit_rewrite_cache": True,
                    "is_real_item": cache.is_real_item,
                    "rewritten_item": cache.rewritten_item
                }

        # 如果精确查询没有匹配，使用向量字段进行相似度查询
        async with get_async_opensearch_client() as async_client:
            item_vector = self.embeddings.embed_query(item)
            # 中文相似度
            response = await async_client.search(index=IndexName.ITEM_REWRITE.value, body={
                "query": {
                    "knn": {
                        "origin_item_ch_name_vector": {
                            "vector": item_vector,
                            "k": 1
                        }
                    }
                }
            })
            if response["hits"]["total"]["value"] > 0:
                score = response["hits"]["hits"][0]["_score"]
                print(f"Chinese similarity score:{score}")
                # 相似度得分达到指定阈值的，直接返回结果，否则流程继续向下流转
                if score > 0.95:
                    return {
                        "hit_rewrite_cache": True,
                        "is_real_item": True,
                        "rewritten_item": response["hits"]["hits"][0]["_source"]["rewritten_item"]
                    }

            # 英文相似度
            response = await async_client.search(index=IndexName.ITEM_REWRITE.value, body={
                "query": {
                    "knn": {
                        "origin_item_en_name_vector": {
                            "vector": item_vector,
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
                        "hit_rewrite_cache": True,
                        "is_real_item": True,
                        "rewritten_item": response["hits"]["hits"][0]["_source"]["rewritten_item"]
                    }

    async def save_exact_cache(self, item: str, rewrite_success: bool, rewritten_item: dict[str, str]):
        """
        保存精确的缓存信息
        """
        cache = ItemRewriteCache(origin_item_name=item, is_real_item=rewrite_success, rewritten_item=rewritten_item)
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await insert_item_rewrite_cache(session, cache)


    async def save_simil_cache(self, item: str, rewritten_item: dict[str, str], config: dict):
        """
        保存相似度匹配用缓存
        """
        ch_name = rewritten_item.get("cn_name", item)
        en_name = rewritten_item.get("en_name", item)
        ch_name_vector = await self.embeddings.aembed_query(ch_name)
        en_name_vector = await self.embeddings.aembed_query(en_name)
        document = {
            "origin_item_name": item,
            "origin_item_ch_name": ch_name,
            "origin_item_ch_name_vector": ch_name_vector,
            "origin_item_en_name": en_name,
            "origin_item_en_name_vector": en_name_vector,
            "rewritten_item": rewritten_item,
            "user_id": config.get("configurable", {}).get("user_id", ""),
            "thread_id": config.get("configurable", {}).get("thread_id", ""),
            "created_at": datetime.now(timezone.utc),
        }
        async with get_async_opensearch_client() as async_client:
            await async_client.index(index=IndexName.ITEM_REWRITE.value, body=document)


    async def rewrite_use_llm(self, item: str):
        """
        调用llm重写商品信息

        Return:
            tuple: (HumanMessage入参，AIMessage出参，ItemRewriteResponse结构化响应转换的Pydantic实体)
        """
        parser = PydanticOutputParser(pydantic_object=ItemRewriteResponse)
        format_instructions = parser.get_format_instructions()
        prompt = PromptTemplate(template=rewrite_item_template,
                                input_variables=["item"],
                                partial_variables={"format_instructions": format_instructions})

        human_message = prompt.invoke({"item": item}).to_messages()[0]

        output = await self.llm.ainvoke(input=[human_message])

        rewrite_result: ItemRewriteResponse = parser.parse(output.content)

        # 如果改写失败了，使用备选llm重试一下
        if self.backup_llm and rewrite_result.rewrite_success == False:
            output = await self.backup_llm.ainvoke(input=[human_message])
            rewrite_result = parser.parse(output.content)

        return human_message, output, rewrite_result



class RewriteItemEmbeddingsService:

    def __init__(self, embeddings: Embeddings):
        self.embeddings = embeddings

    async def get_rewritten_item_embeddings(self, rewritten_item: dict) -> list[float]:
        """
        获取改写商品的embeddings，优先使用redis缓存，如果没有走接口获取，然后缓存到redis中
        """
        rewritten_item_vector = None
        ordered_rewritten_item = OrderedDict(sorted(rewritten_item.items()))
        rewritten_item_json = json.dumps(ordered_rewritten_item, ensure_ascii=False)
        redis_hash_key = f"{RedisKeyPrefix.REWRITTEN_ITEM_EMBEDDINGS.value}:{md5_hash(rewritten_item_json)}"
        async_redis = await get_async_redis()
        vector_json = await async_redis.get(redis_hash_key)
        if vector_json:
            rewritten_item_vector = json.loads(vector_json)
        if rewritten_item_vector is None:
            rewritten_item_vector = await self.embeddings.aembed_query(rewritten_item_json)
            # 将llm返回的embedding缓存到redis
            await async_redis.set(redis_hash_key, json.dumps(rewritten_item_vector, ensure_ascii=False))
        return rewritten_item_vector