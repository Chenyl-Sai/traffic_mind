from langchain_core.language_models import BaseChatModel

from app.db.session import AsyncSessionLocal
from app.model.hts_classify_cache_model import ItemRewriteCache
from app.repo.hts_classify_cache_repo import insert_item_rewrite_cache
from app.core.opensearch import get_async_client
from app.core.constants import IndexName
from app.schema.llm.llm import ItemRewriteResponse
from app.llm.prompt.prompt_template import rewrite_item_template

from datetime import datetime
from langchain.embeddings.base import Embeddings
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate


class ItemRewriteCacheService:

    def __init__(self, embeddings: Embeddings, llm: BaseChatModel, ):
        self.embeddings = embeddings
        self.llm = llm


    async def save_exact_cache(self, item: str, rewrite_success: bool, rewritten_item: dict[str, str]):
        """
        保存精确的缓存信息
        """
        cache = ItemRewriteCache(origin_item_name=item, is_real_item=rewrite_success, rewrite_item=rewritten_item)
        async with AsyncSessionLocal() as session:
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
            "rewrite_result": rewritten_item,
            "user_id": config.get("configurable", {}).get("user_id", ""),
            "thread_id": config.get("configurable", {}).get("thread_id", ""),
            "created_at": datetime.now(),
        }
        async with get_async_client() as async_client:
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

        return human_message, output, parser.parse(output.content)