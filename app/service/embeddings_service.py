import json

from langchain.embeddings.base import Embeddings
from collections import OrderedDict

from app.core.constants import RedisKeyPrefix
from app.util.hash_utils import md5_hash
from app.core.redis import get_async_redis


class EmbeddingsService:
    def __init__(self, embeddings: Embeddings, embeddings_name: str, dimension: int):
        self.embeddings = embeddings
        self.embeddings_name = embeddings_name
        self.dimension = dimension

    async def get_rewritten_item_embeddings(self, rewritten_item: dict) -> list[float]:
        """
        获取改写商品的embeddings，优先使用redis缓存，如果没有走接口获取，然后缓存到redis中
        """
        rewritten_item_vector = None
        ordered_rewritten_item = OrderedDict(sorted(rewritten_item.items()))
        rewritten_item_json = json.dumps(ordered_rewritten_item, ensure_ascii=False)
        redis_hash_key = (f"{RedisKeyPrefix.REWRITTEN_ITEM_EMBEDDINGS.value}"
                          f":{self.embeddings_name}"
                          f":{self.dimension}"
                          f":{md5_hash(rewritten_item_json)}")
        async_redis = await get_async_redis()
        vector_json = await async_redis.get(redis_hash_key)
        if vector_json:
            rewritten_item_vector = json.loads(vector_json)
        if rewritten_item_vector is None:
            rewritten_item_vector = await self.embeddings.aembed_query(rewritten_item_json)
            # 将llm返回的embedding缓存到redis
            await async_redis.set(redis_hash_key, json.dumps(rewritten_item_vector, ensure_ascii=False))
        return rewritten_item_vector

    async def get_embeddings_for_str(self, text: str, use_cache: bool = True) -> list[float]:
        rewritten_item_vector = None
        async_redis = await get_async_redis()
        redis_hash_key = (f"{RedisKeyPrefix.USER_INPUT_EMBEDDINGS.value}"
                          f":{self.embeddings_name}"
                          f":{self.dimension}"
                          f":{md5_hash(text)}")
        if use_cache:
            vector_json = await async_redis.get(redis_hash_key)
            if vector_json:
                rewritten_item_vector = json.loads(vector_json)
        if rewritten_item_vector is None:
            rewritten_item_vector = await self.embeddings.aembed_query(text)
            # 将llm返回的embedding缓存到redis
            if use_cache:
                await async_redis.set(redis_hash_key, json.dumps(rewritten_item_vector, ensure_ascii=False))
        return rewritten_item_vector

    async def get_embeddings_for_list(self, texts: list[str], use_cache: bool = True) -> list[list[float]]:
        result = []
        # 需要使用模型获取embedding的列表
        texts_to_process = []
        indices_to_process = []
        async_redis = await get_async_redis()

        # 从缓存中获取embedding
        for index, text in enumerate(texts):
            cache_result = None
            if use_cache:
                for text in texts:
                    redis_hash_key = (f"{RedisKeyPrefix.USER_INPUT_EMBEDDINGS.value}"
                                      f":{self.embeddings_name}"
                                      f":{self.dimension}"
                                      f":{md5_hash(text)}")
                    cache_result = await async_redis.get(redis_hash_key)
            if cache_result:
                result[index] = json.loads(cache_result)
            else:
                texts_to_process.append(text)
                indices_to_process.append(index)
        # 缓存中不存在的使用模型获取
        if texts_to_process:
            new_embeddings = await self.embeddings.aembed_documents(texts_to_process)
            for idx, embedding in zip(indices_to_process, new_embeddings):
                result[idx] = embedding
                if use_cache:
                    redis_hash_key = (f"{RedisKeyPrefix.USER_INPUT_EMBEDDINGS.value}"
                                      f":{self.embeddings_name}"
                                      f":{self.dimension}"
                                      f":{md5_hash(texts[idx])}")
                    await async_redis.set(redis_hash_key, json.dumps(embedding, ensure_ascii=False))

        return result
