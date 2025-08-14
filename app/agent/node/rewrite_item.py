"""
问题重写节点
"""
import logging

from datetime import datetime

from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.types import Command, interrupt
from langgraph.graph import START, StateGraph, END

from app.agent.state import HtsClassifyAgentState
from app.agent.util.exception_handler import safe_node
from app.core.llm import base_qwen_llm
from app.llm.embedding.qwen import default_qwen_embeddings
from app.llm.prompt.prompt_template import rewrite_item_template
from app.schema.llm.llm import ItemRewriteResponse
from app.agent.constants import HtsAgents, RewriteItemNodes
from app.core.opensearch import get_async_client
from app.core.constants import IndexName
from app.service.item_rewrite_service import ItemRewriteCacheService

logger = logging.getLogger(__name__)

item_rewrite_cache_service = ItemRewriteCacheService(embeddings=default_qwen_embeddings, llm=base_qwen_llm)


def start_rewrite(state: HtsClassifyAgentState):
    return {"current_agent": HtsAgents.REWRITE_ITEM.code}


async def get_from_cache(state: HtsClassifyAgentState, config, store: BaseStore):
    """
    从OpenSearch中查询缓存信息
    """
    try:
        # 首先使用原始名称精确查询
        item = state.get("item")
        async with get_async_client() as async_client:
            response = await async_client.search(index=IndexName.ITEM_REWRITE.value, body={
                "query": {
                    "bool": {
                        "filter": {
                            "term": {
                                "origin_item_name": item
                            }
                        }
                    }
                },
                "sort": [{
                    "created_at": {
                        "order": "desc",
                    }
                }],
                "size": 1,
                "_source": ["rewrite_result"]
            })
            if response["hits"]["total"]["value"] > 0:
                return {
                    "hit_cache": True,
                    "rewritten_item": response["hits"]["hits"][0]["_source"]["rewrite_result"]
                }
            # 如果精确查询没有匹配，使用向量字段进行相似度查询
            # 相似度得分达到指定阈值的，直接返回结果，否则流程继续向下流转
            item_vector = default_qwen_embeddings.embed_query(item)
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
                if score > 0.95:
                    return {
                        "hit_cache": True,
                        "rewritten_item": response["hits"]["hits"][0]["_source"]["rewrite_result"]
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
                        "hit_cache": True,
                        "rewritten_item": response["hits"]["hits"][0]["_source"]["rewrite_result"]
                    }
    except Exception as e:
        # 查询报错的话，流程继续向下走LLM
        logger.exception("Get rewrite result from cache failed", exc_info=e)
    return {"hit_cache": False}


@safe_node(logger=logger)
async def get_llm_rewrite_item_response(state: HtsClassifyAgentState):
    """
    获取商品信息重写节点
    """
    input_message, output_message, rewritten_response = item_rewrite_cache_service.rewrite_use_llm(state.get("item"))

    return {"messages": [input_message, output_message], "rewrite_llm_response": rewritten_response}


@safe_node(logger=logger)
def rewrite_item(state: HtsClassifyAgentState, config, store: BaseStore):
    """
    重写用户输入的商品信息，
    """
    last_message = state["messages"][-1]
    parser = PydanticOutputParser(pydantic_object=ItemRewriteResponse)
    rewrite_response = parser.parse(last_message.content)

    if rewrite_response.rewrite_success:
        rewritten_item = rewrite_response.model_dump()
        del (rewritten_item["rewrite_success"])
        del (rewritten_item["need_other_messages"])
        # 返回重写后的信息
        return {"rewrite_success": True, "rewritten_item": rewritten_item}
    elif rewrite_response.need_other_messages:
        # 需要用户补充关键信息，流程变成人工介入
        additional_messages = interrupt({
            "need_other_messages": rewrite_response.need_other_messages
        })
        # 用户补充完成后，将补充信息添加到item中，重新再调用llm获取重写的商品信息
        return {"item": state.get("item") + "\n" + additional_messages}
        # return Command(
        #     update={"item": state.get(("item")) + "\n" + additional_messages},
        #     goto=RewriteItemNodes.GET_LLM_REWRITE_ITEM_RESPONSE,
        # )
    elif rewrite_response.unexpected_error:
        # 获取重写结果时发生异常，流程结束
        return {"rewrite_success": False,
                "unexpected_error": rewrite_response.unexpected_error,
                "unexpected_error_message": rewrite_response.unexpected_error_message}
    else:
        # 重写失败，流程结束
        return {"rewrite_success": False}


async def save_exact_rewrite_cache(state: HtsClassifyAgentState):
    """
    保存精确匹配的缓存结果
    """
    try:
        await item_rewrite_cache_service.save_exact_cache(item=state["item"],
                                                          rewrite_success=state["rewrite_success"],
                                                          rewritten_item=state["rewritten_item"])
    except Exception as e:
        logger.exception("Save exact rewrite cache failed", exc_info=e)
    return {}


async def save_simil_rewrite_cache(state: HtsClassifyAgentState, config):
    """
    保存语义匹配使用的缓存
    """
    try:
        await item_rewrite_cache_service.save_simil_cache(item=state.get("item"),
                                                          rewritten_item=state.get("rewritten_item"),
                                                          config=config)
    except Exception as e:
        logger.exception("Save simil rewrite cache failed", exc_info=e)
    return {}


def after_query_cache_edge(state: HtsClassifyAgentState):
    hit_cache = state.get("hit_cache")
    if hit_cache:
        return [END]
    else:
        return [RewriteItemNodes.GET_LLM_REWRITE_ITEM_RESPONSE.value]


def after_rewrite_edge(state: HtsClassifyAgentState):
    rewrite_success = state.get("rewrite_success")
    # 中断恢复，没有设置是否改写成功
    if rewrite_success is None:
        return [RewriteItemNodes.GET_LLM_REWRITE_ITEM_RESPONSE.value]
    # 明确改写成功
    elif rewrite_success:
        return [RewriteItemNodes.SAVE_EXACT_REWRITE_CACHE.value, RewriteItemNodes.SAVE_SIMIL_REWRITE_CACHE.value, END]
    # 改写失败了
    else:
        return [RewriteItemNodes.SAVE_EXACT_REWRITE_CACHE.value, END]


def build_rewrite_item_graph() -> CompiledStateGraph:
    graph_builder = StateGraph(HtsClassifyAgentState)
    graph_builder.add_node(RewriteItemNodes.ENTER_REWRITE_ITEM, start_rewrite)
    graph_builder.add_node(RewriteItemNodes.GET_REWRITE_ITEM_FROM_CACHE, get_from_cache)
    graph_builder.add_node(RewriteItemNodes.GET_LLM_REWRITE_ITEM_RESPONSE, get_llm_rewrite_item_response)
    graph_builder.add_node(RewriteItemNodes.REWRITE_ITEM, rewrite_item)
    graph_builder.add_node(RewriteItemNodes.SAVE_EXACT_REWRITE_CACHE, save_exact_rewrite_cache())
    graph_builder.add_node(RewriteItemNodes.SAVE_SIMIL_REWRITE_CACHE, save_simil_rewrite_cache)

    graph_builder.add_edge(START, RewriteItemNodes.ENTER_REWRITE_ITEM)
    graph_builder.add_edge(RewriteItemNodes.ENTER_REWRITE_ITEM, RewriteItemNodes.GET_REWRITE_ITEM_FROM_CACHE)
    graph_builder.add_conditional_edges(RewriteItemNodes.GET_REWRITE_ITEM_FROM_CACHE,
                                        after_query_cache_edge,
                                        {
                                            RewriteItemNodes.GET_LLM_REWRITE_ITEM_RESPONSE.value: RewriteItemNodes.GET_LLM_REWRITE_ITEM_RESPONSE,
                                            END: END
                                        })
    graph_builder.add_conditional_edges(RewriteItemNodes.GET_LLM_REWRITE_ITEM_RESPONSE,
                                        lambda state: "error" if state.get("unexpected_error") else "normal",
                                        {"error": END, "normal": RewriteItemNodes.REWRITE_ITEM})
    graph_builder.add_conditional_edges(RewriteItemNodes.REWRITE_ITEM,
                                        after_rewrite_edge,
                                        {
                                            RewriteItemNodes.GET_LLM_REWRITE_ITEM_RESPONSE.value: RewriteItemNodes.GET_LLM_REWRITE_ITEM_RESPONSE,
                                            RewriteItemNodes.SAVE_EXACT_REWRITE_CACHE.value: RewriteItemNodes.SAVE_EXACT_REWRITE_CACHE,
                                            RewriteItemNodes.SAVE_SIMIL_REWRITE_CACHE.value: RewriteItemNodes.SAVE_SIMIL_REWRITE_CACHE,
                                            END: END
                                        })
    return graph_builder.compile()
