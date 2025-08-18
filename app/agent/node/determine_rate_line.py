"""
确定所属税率线
"""
import logging

from langgraph.graph.state import CompiledStateGraph
from langgraph.graph import START, StateGraph, END

from app.agent.constants import DetermineRateLineNodes
from app.agent.state import HtsClassifyAgentState
from app.agent.constants import HtsAgents
from app.agent.util.exception_handler import safe_raise_exception_node
from app.core.llm import base_qwen_llm
from app.llm.embedding.qwen import default_qwen_embeddings
from app.service.determine_rate_line_service import DetermineRateLineService

logger = logging.getLogger(__name__)

determine_rate_line_service = DetermineRateLineService(llm=base_qwen_llm, embeddings=default_qwen_embeddings)


def start_determine_rate_line(state: HtsClassifyAgentState):
    return {"current_agent": HtsAgents.DETERMINE_RATE_LINE.code}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def get_from_cache(state: HtsClassifyAgentState, config):
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    if is_for_evaluation:
        return {"hit_rate_line_cache": False}
    else:
        cache = await determine_rate_line_service.get_simil_cache(rewritten_item=state.get("rewritten_item"),
                                                                  subheading_codes=get_confirmed_subheading_codes(
                                                                      state))
        return cache


@safe_raise_exception_node(logger=logger)
async def ask_llm_to_determine_rate_line(state: HtsClassifyAgentState):
    input_message, output_message, llm_response = await determine_rate_line_service.determine_use_llm(
        rewritten_item=state.get("rewritten_item"), rate_line_documents=state.get("rate_line_documents"))
    return {"messages": [input_message, output_message], "determine_rate_line_llm_response": llm_response}


@safe_raise_exception_node(logger=logger)
def process_llm_response(state: HtsClassifyAgentState):
    determine_subheading_response = state.get("determine_rate_line_llm_response")
    if determine_subheading_response.rate_line_code:
        return {
            "determine_rate_line_success": True,
            "main_rate_line": determine_subheading_response.model_dump(),
        }
    else:
        return {"determine_rate_line_success": False}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_layered_rate_line_cache(state: HtsClassifyAgentState):
    """
    保存分层的税率线缓存
    """
    await determine_rate_line_service.save_simil_cache(origin_item_name=state.get("item"),
                                                       rewritten_item=state.get("rewritten_item"),
                                                       subheading_codes=get_confirmed_subheading_codes(state),
                                                       rate_line_result=state.get("main_rate_line"))
    return {}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_for_evaluation(state: HtsClassifyAgentState, config):
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    evaluate_version = config["configurable"].get("evaluate_version", "-1")
    if is_for_evaluation:
        await determine_rate_line_service.save_for_evaluation(
            evaluate_version=evaluate_version,
            origin_item_name=state.get("item"),
            rate_line_documents=state.get("rate_line_documents"),
            llm_response=state.get("determine_rate_line_llm_response")
        )
    return {}


def after_get_cache_edge(state: HtsClassifyAgentState):
    hit_rate_line_cache = state.get("hit_rate_line_cache")
    if hit_rate_line_cache:
        return [END]
    else:
        return [DetermineRateLineNodes.ASK_LLM_TO_DETERMINE_RATE_LINE.value]


def after_llm_response_edge(state: HtsClassifyAgentState):
    if state.get("unexpected_error"):
        return END
    else:
        return [DetermineRateLineNodes.PROCESS_LLM_RESPONSE.value,
                DetermineRateLineNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION.value]


def after_process_llm_response_edge(state: HtsClassifyAgentState, config):
    # 如果是评估请求，则禁写缓存
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    if is_for_evaluation:
        return END

    if state.get("determine_rate_line_success"):
        return DetermineRateLineNodes.SAVE_LAYERED_RATE_LINE_CACHE.value
    else:
        return END


def get_confirmed_subheading_codes(state: HtsClassifyAgentState):
    """
    获取上一环节确定的子目编码列表
    """
    main_subheading = state.get("main_subheading")
    subheading_codes = [main_subheading.get("subheading_code")]
    alternative_subheadings = state.get("alternative_subheadings")
    if alternative_subheadings:
        subheading_codes.extend([subheading.get("subheading_code") for subheading in alternative_subheadings])
    return subheading_codes


def build_determine_subheading_graph() -> CompiledStateGraph:
    """
    构建确定所属税率线的图
    """
    graph_builder = StateGraph(HtsClassifyAgentState)
    graph_builder.add_node(DetermineRateLineNodes.ENTER_DETERMINE_RATE_LINE, start_determine_rate_line)
    graph_builder.add_node(DetermineRateLineNodes.GET_RATE_LINE_FROM_CACHE, get_from_cache)
    graph_builder.add_node(DetermineRateLineNodes.ASK_LLM_TO_DETERMINE_RATE_LINE, ask_llm_to_determine_rate_line)
    graph_builder.add_node(DetermineRateLineNodes.PROCESS_LLM_RESPONSE, process_llm_response)
    graph_builder.add_node(DetermineRateLineNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION, save_for_evaluation)
    graph_builder.add_node(DetermineRateLineNodes.SAVE_LAYERED_RATE_LINE_CACHE, save_layered_rate_line_cache)

    graph_builder.add_edge(START, DetermineRateLineNodes.ENTER_DETERMINE_RATE_LINE)
    graph_builder.add_edge(DetermineRateLineNodes.ENTER_DETERMINE_RATE_LINE,
                           DetermineRateLineNodes.GET_RATE_LINE_FROM_CACHE)
    graph_builder.add_conditional_edges(DetermineRateLineNodes.GET_RATE_LINE_FROM_CACHE,
                                        after_get_cache_edge,
                                        {
                                            END: END,
                                            DetermineRateLineNodes.ASK_LLM_TO_DETERMINE_RATE_LINE.value:
                                                DetermineRateLineNodes.ASK_LLM_TO_DETERMINE_RATE_LINE,
                                        })
    graph_builder.add_conditional_edges(DetermineRateLineNodes.ASK_LLM_TO_DETERMINE_RATE_LINE,
                                        after_llm_response_edge,
                                        {
                                            END: END,
                                            DetermineRateLineNodes.PROCESS_LLM_RESPONSE.value:
                                                DetermineRateLineNodes.PROCESS_LLM_RESPONSE,
                                            DetermineRateLineNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION.value:
                                                DetermineRateLineNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION,
                                        })
    graph_builder.add_conditional_edges(DetermineRateLineNodes.PROCESS_LLM_RESPONSE,
                                        after_process_llm_response_edge,
                                        {
                                            END: END,
                                            DetermineRateLineNodes.SAVE_LAYERED_RATE_LINE_CACHE.value:
                                                DetermineRateLineNodes.SAVE_LAYERED_RATE_LINE_CACHE
                                        })
    return graph_builder.compile()
