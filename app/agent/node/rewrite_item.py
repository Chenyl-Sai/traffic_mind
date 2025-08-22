"""
问题重写节点
"""
import logging

from datetime import datetime

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt
from langgraph.graph import START, StateGraph, END

from app.agent.node.final_output import final_output_service
from app.agent.state import HtsClassifyAgentState, OutputMessage
from app.agent.util.exception_handler import safe_raise_exception_node
from app.core.llm import base_qwen_llm
from app.llm.embedding.qwen import default_qwen_embeddings
from app.agent.constants import HtsAgents, RewriteItemNodes
from app.service.rewrite_item_service import ItemRewriteCacheService

logger = logging.getLogger(__name__)

item_rewrite_cache_service = ItemRewriteCacheService(embeddings=default_qwen_embeddings, llm=base_qwen_llm)


def start_rewrite_node(state: HtsClassifyAgentState):
    return {"current_agent": HtsAgents.REWRITE_ITEM.code,
            "current_output_message": OutputMessage(type="message", message="正在进行商品改写...")}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def get_from_cache_node(state: HtsClassifyAgentState):
    """
    从OpenSearch中查询缓存信息
    """
    item = state.get("item")
    cache = await item_rewrite_cache_service.get_from_cache(item)
    if cache and cache.get("hit_rewrite_cache", False):
        if cache.get("is_real_item", False):
            return {"hit_rewrite_cache": True, "rewrite_success": True, "rewritten_item": cache.get("rewritten_item"),
                    "current_output_message": OutputMessage(type="message", message="成功获取商品改写缓存...")}
        else:
            return {"hit_rewrite_cache": True, "rewrite_success": False}
    return {"hit_rewrite_cache": False,
            "current_output_message": OutputMessage(type="message", message="为获取到商品重写缓存...")}


@safe_raise_exception_node(logger=logger)
async def use_llm_to_rewrite_node(state: HtsClassifyAgentState):
    """
    获取商品信息重写节点
    """
    input_message, output_message, rewritten_response = await item_rewrite_cache_service.rewrite_use_llm(
        state.get("item"))

    return {"messages": [input_message, output_message], "rewrite_llm_response": rewritten_response,
            "current_output_message": OutputMessage(type="message", message="获取LLM改写商品结果...")}


@safe_raise_exception_node(logger=logger)
def process_llm_response_node(state: HtsClassifyAgentState):
    """
    重写用户输入的商品信息，
    """
    rewrite_response = state.get("rewrite_llm_response")

    if rewrite_response.rewrite_success:
        rewritten_item = rewrite_response.model_dump()
        del (rewritten_item["rewrite_success"])
        del (rewritten_item["need_other_messages"])
        # 返回重写后的信息
        return {"rewrite_success": True, "rewritten_item": rewritten_item,
                "current_output_message": OutputMessage(type="message", message="LLM改写商品成功...")}
    elif rewrite_response.need_other_messages:
        # 需要用户补充关键信息，流程变成人工介入
        additional_messages = interrupt({
            "need_other_messages": rewrite_response.need_other_messages
        })
        # 用户补充完成后，将补充信息添加到item中，重新再调用llm获取重写的商品信息
        return {"item": state.get("item") + "\n" + additional_messages}
    else:
        # 重写失败，流程结束
        return {"rewrite_success": False,
                "current_output_message": OutputMessage(type="message", message="LLM改写商品失败...")}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_exact_rewrite_cache_node(state: HtsClassifyAgentState):
    """
    保存精确匹配的缓存结果，即使改写失败也会记录到数据库
    """
    await item_rewrite_cache_service.save_exact_cache(item=state.get("item"),
                                                      rewrite_success=state.get("rewrite_success"),
                                                      rewritten_item=state.get("rewritten_item"))
    return {}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_simil_rewrite_cache_node(state: HtsClassifyAgentState, config):
    """
    保存语义匹配使用的缓存, 只有明确改写成功了才会执行到这个node
    """
    await item_rewrite_cache_service.save_simil_cache(item=state.get("item"),
                                                      rewritten_item=state.get("rewritten_item"),
                                                      config=config)
    return {}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def get_simil_e2e_cache(state: HtsClassifyAgentState, config):
    """
    改写之后，根据语义相似度获取e2e缓存
    """
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    if is_for_evaluation:
        return {"hit_e2e_simil_cache": False}
    return await final_output_service.get_e2e_simil_cache(state.get("rewritten_item"))


def after_query_cache_edge(state: HtsClassifyAgentState):
    hit_rewrite_cache = state.get("hit_rewrite_cache")
    if hit_rewrite_cache:
        return [RewriteItemNodes.GET_SIMIL_E2E_CACHE.value]
    else:
        return [RewriteItemNodes.USE_LLM_TO_REWRITE_ITEM.value]


def after_rewrite_edge(state: HtsClassifyAgentState):
    rewrite_success = state.get("rewrite_success")
    # 中断恢复，没有设置是否改写成功
    if rewrite_success is None:
        return [RewriteItemNodes.USE_LLM_TO_REWRITE_ITEM.value]
    # 明确改写成功
    elif rewrite_success:
        return [RewriteItemNodes.SAVE_EXACT_REWRITE_CACHE.value,
                RewriteItemNodes.SAVE_SIMIL_REWRITE_CACHE.value,
                RewriteItemNodes.GET_SIMIL_E2E_CACHE.value]
    # 改写失败了
    else:
        return [RewriteItemNodes.SAVE_EXACT_REWRITE_CACHE.value, END]


def build_rewrite_item_graph() -> CompiledStateGraph:
    graph_builder = StateGraph(HtsClassifyAgentState)
    graph_builder.add_node(RewriteItemNodes.ENTER_REWRITE_ITEM, start_rewrite_node)
    graph_builder.add_node(RewriteItemNodes.GET_REWRITE_ITEM_FROM_CACHE, get_from_cache_node)
    graph_builder.add_node(RewriteItemNodes.USE_LLM_TO_REWRITE_ITEM, use_llm_to_rewrite_node)
    graph_builder.add_node(RewriteItemNodes.PROCESS_LLM_RESPONSE, process_llm_response_node)
    graph_builder.add_node(RewriteItemNodes.SAVE_EXACT_REWRITE_CACHE, save_exact_rewrite_cache_node)
    graph_builder.add_node(RewriteItemNodes.SAVE_SIMIL_REWRITE_CACHE, save_simil_rewrite_cache_node)
    graph_builder.add_node(RewriteItemNodes.GET_SIMIL_E2E_CACHE, get_simil_e2e_cache)

    graph_builder.add_edge(START, RewriteItemNodes.ENTER_REWRITE_ITEM)
    graph_builder.add_edge(RewriteItemNodes.ENTER_REWRITE_ITEM, RewriteItemNodes.GET_REWRITE_ITEM_FROM_CACHE)
    graph_builder.add_conditional_edges(RewriteItemNodes.GET_REWRITE_ITEM_FROM_CACHE,
                                        after_query_cache_edge,
                                        {
                                            RewriteItemNodes.USE_LLM_TO_REWRITE_ITEM.value:
                                                RewriteItemNodes.USE_LLM_TO_REWRITE_ITEM,
                                            RewriteItemNodes.GET_SIMIL_E2E_CACHE.value:
                                                RewriteItemNodes.GET_SIMIL_E2E_CACHE
                                        })
    graph_builder.add_conditional_edges(RewriteItemNodes.USE_LLM_TO_REWRITE_ITEM,
                                        lambda state: "error" if state.get("unexpected_error") else "normal",
                                        {"error": END, "normal": RewriteItemNodes.PROCESS_LLM_RESPONSE})
    graph_builder.add_conditional_edges(RewriteItemNodes.PROCESS_LLM_RESPONSE,
                                        after_rewrite_edge,
                                        {
                                            RewriteItemNodes.USE_LLM_TO_REWRITE_ITEM.value: RewriteItemNodes.USE_LLM_TO_REWRITE_ITEM,
                                            RewriteItemNodes.SAVE_EXACT_REWRITE_CACHE.value: RewriteItemNodes.SAVE_EXACT_REWRITE_CACHE,
                                            RewriteItemNodes.SAVE_SIMIL_REWRITE_CACHE.value: RewriteItemNodes.SAVE_SIMIL_REWRITE_CACHE,
                                            RewriteItemNodes.GET_SIMIL_E2E_CACHE.value: RewriteItemNodes.GET_SIMIL_E2E_CACHE,
                                            END: END
                                        })
    return graph_builder.compile()
