"""
确定所属子目
"""
import logging

from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.graph import START, StateGraph, END

from app.agent.constants import DetermineSubheadingNodes
from app.agent.state import HtsClassifyAgentState
from app.agent.constants import HtsAgents
from app.agent.util.exception_handler import safe_raise_exception_node
from app.core.llm import base_qwen_llm
from app.llm.embedding.qwen import default_qwen_embeddings
from app.service.determine_subheading_service import DetermineSubheadingService

logger = logging.getLogger(__name__)

determine_subheading_service = DetermineSubheadingService(llm=base_qwen_llm, embeddings=default_qwen_embeddings)


def start_determine_subheading(state: HtsClassifyAgentState):
    return {"current_agent": HtsAgents.DETERMINE_SUBHEADING.code}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def get_from_cache(state: HtsClassifyAgentState, config):
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    if is_for_evaluation:
        return {"hit_subheading_cache": False}
    else:
        cache = await determine_subheading_service.get_simil_cache(rewritten_item=state.get("rewritten_item"),
                                                                   heading_codes=get_confirmed_heading_codes(state))
        return cache


@safe_raise_exception_node(logger=logger)
async def ask_llm_to_determine_subheading(state: HtsClassifyAgentState):
    input_message, output_message, llm_response = await determine_subheading_service.determine_use_llm(
        rewritten_item=state.get("rewritten_item"), subheading_documents=state.get("subheading_documents"))
    return {"messages": [input_message, output_message], "determine_subheading_llm_response": llm_response}


@safe_raise_exception_node(logger=logger)
def process_llm_response(state: HtsClassifyAgentState, config, store: BaseStore):
    determine_subheading_response = state.get("determine_subheading_llm_response")
    if determine_subheading_response.main_subheading:
        alternative_subheadings = determine_subheading_response.alternative_subheadings
        final_alternative_subheadings = [
            heading.model_dump() for heading in (alternative_subheadings if alternative_subheadings else [])
            # if heading.confidence_score > 5
        ]

        return {
            "determine_subheading_success": True,
            "main_subheading": determine_subheading_response.main_subheading.model_dump(),
            "alternative_subheadings": final_alternative_subheadings
        }
    else:
        return {"determine_subheading_success": False}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_simil_cache(state: HtsClassifyAgentState):
    """
    保存语义匹配使用的缓存
    """
    await determine_subheading_service.save_simil_cache(origin_item_name=state.get("item"),
                                                        rewritten_item=state.get("rewritten_item"),
                                                        heading_codes=get_confirmed_heading_codes(state),
                                                        main_subheading=state.get("main_subheading"),
                                                        alternative_subheadings=state.get("alternative_subheadings"))
    return {}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_for_evaluation(state: HtsClassifyAgentState, config):
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    evaluate_version = config["configurable"].get("evaluate_version", "-1")
    if is_for_evaluation:
        await determine_subheading_service.save_for_evaluation(
            evaluate_version=evaluate_version,
            origin_item_name=state.get("item"),
            subheading_documents=state.get("subheading_documents"),
            llm_response=state.get("determine_subheading_llm_response"),
            actual_subheading=config["configurable"].get("hscode", "")[:6]
        )
    return {}


def after_get_from_cache_edge(state: HtsClassifyAgentState):
    if state.get("hit_subheading_cache"):
        return [END]
    else:
        return [DetermineSubheadingNodes.ASK_LLM_TO_DETERMINE_SUBHEADING.value]


def after_llm_response_edge(state: HtsClassifyAgentState):
    if state.get("unexpected_error"):
        return [END]
    else:
        return [DetermineSubheadingNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION,
                DetermineSubheadingNodes.PROCESS_LLM_RESPONSE]


def after_process_llm_response(state: HtsClassifyAgentState, config):
    # 如果是评估请求，则禁写缓存
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    if is_for_evaluation:
        return END

    if state.get("determine_subheading_success"):
        return [DetermineSubheadingNodes.SAVE_LAYERED_SUBHEADING_CACHE.value]
    else:
        return [END]


def get_confirmed_heading_codes(state: HtsClassifyAgentState):
    """
    获取上一环节确定的类目编码列表
    """
    main_heading = state.get("main_heading")
    heading_codes = [main_heading.get("heading_code")]
    alternative_headings = state.get("alternative_headings")
    if alternative_headings:
        heading_codes.extend([heading.get("heading_code") for heading in alternative_headings])
    return sorted(heading_codes)


def build_determine_subheading_graph() -> CompiledStateGraph:
    """
    构建确定所属子目的图
    """
    graph_builder = StateGraph(HtsClassifyAgentState)
    graph_builder.add_node(DetermineSubheadingNodes.ENTER_DETERMINE_SUBHEADING, start_determine_subheading)
    graph_builder.add_node(DetermineSubheadingNodes.GET_SUBHEADING_FROM_CACHE, get_from_cache)
    graph_builder.add_node(DetermineSubheadingNodes.ASK_LLM_TO_DETERMINE_SUBHEADING, ask_llm_to_determine_subheading)
    graph_builder.add_node(DetermineSubheadingNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION, save_for_evaluation)
    graph_builder.add_node(DetermineSubheadingNodes.PROCESS_LLM_RESPONSE, process_llm_response)
    graph_builder.add_node(DetermineSubheadingNodes.SAVE_LAYERED_SUBHEADING_CACHE, save_simil_cache)

    graph_builder.add_edge(START, DetermineSubheadingNodes.ENTER_DETERMINE_SUBHEADING)
    graph_builder.add_edge(DetermineSubheadingNodes.ENTER_DETERMINE_SUBHEADING,
                           DetermineSubheadingNodes.GET_SUBHEADING_FROM_CACHE)
    graph_builder.add_conditional_edges(DetermineSubheadingNodes.GET_SUBHEADING_FROM_CACHE,
                                        after_get_from_cache_edge,
                                        {
                                            END: END,
                                            DetermineSubheadingNodes.ASK_LLM_TO_DETERMINE_SUBHEADING.value:
                                                DetermineSubheadingNodes.ASK_LLM_TO_DETERMINE_SUBHEADING,
                                        })
    graph_builder.add_conditional_edges(DetermineSubheadingNodes.ASK_LLM_TO_DETERMINE_SUBHEADING,
                                        after_llm_response_edge,
                                        {
                                            END: END,
                                            DetermineSubheadingNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION.value:
                                                DetermineSubheadingNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION,
                                            DetermineSubheadingNodes.PROCESS_LLM_RESPONSE.value:
                                                DetermineSubheadingNodes.PROCESS_LLM_RESPONSE,
                                        })
    graph_builder.add_conditional_edges(DetermineSubheadingNodes.PROCESS_LLM_RESPONSE,
                                        after_process_llm_response,
                                        {
                                            END: END,
                                            DetermineSubheadingNodes.SAVE_LAYERED_SUBHEADING_CACHE.value:
                                                DetermineSubheadingNodes.SAVE_LAYERED_SUBHEADING_CACHE
                                        })
    return graph_builder.compile()
