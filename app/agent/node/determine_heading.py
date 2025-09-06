"""
确定所属类目
"""
import logging, json

from langgraph.graph.state import CompiledStateGraph
from langgraph.graph import START, StateGraph, END

from app.agent.constants import DetermineHeadingNodes
from app.agent.state import HtsClassifyAgentState
from app.agent.constants import HtsAgents
from app.agent.util.exception_handler import safe_raise_exception_node
from app.core.llm import base_qwen_llm
from app.service.determine_heading_service import DetermineHeadingService

logger = logging.getLogger(__name__)

determine_heading_service = DetermineHeadingService(llm=base_qwen_llm, embeddings=base_qwen_llm)


def start_determine_heading(state: HtsClassifyAgentState):
    return {"current_agent": HtsAgents.DETERMINE_HEADING.code}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def get_from_cache(state: HtsClassifyAgentState, config):
    """
    从缓存获取
    """
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    if is_for_evaluation:
        return {"hit_heading_cache": False}
    else:
        cache = await determine_heading_service.get_simil_cache(rewritten_item=state.get("rewritten_item"),
                                                                chapter_codes=get_determined_chapter_codes(state))
        return cache


@safe_raise_exception_node(logger=logger)
async def ask_llm_to_determine_heading(state: HtsClassifyAgentState):
    heading_documents = state.get("heading_documents")
    input_message, output_message, llm_response = await determine_heading_service.determine_use_llm(
        state.get("rewritten_item"), heading_documents)

    return {"messages": [input_message, output_message], "determine_heading_llm_response": llm_response}


@safe_raise_exception_node(logger=logger)
def process_llm_response(state: HtsClassifyAgentState):
    determine_heading_response = state.get("determine_heading_llm_response")
    # 过滤掉置信度低于10的heading
    final_alternative_headings = [
        heading.model_dump() for heading in determine_heading_response.alternative_headings
        if heading.confidence_score > 10
    ]

    if final_alternative_headings:
        return {
            "determine_heading_success": True,
            "alternative_headings": final_alternative_headings
        }
    else:
        return {
            "determine_heading_success": False
        }


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_llm_confirm_heading_for_evaluation(state: HtsClassifyAgentState, config):
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    evaluate_version = config["configurable"].get("evaluate_version", "-1")
    if is_for_evaluation:
        await determine_heading_service.save_for_evaluation(evaluate_version=evaluate_version,
                                                            origin_item_name=state.get("item"),
                                                            heading_documents=state.get("heading_documents"),
                                                            llm_response=state.get("determine_heading_llm_response"),
                                                            actual_heading=config["configurable"].get("hscode", "")[:4])


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_layered_heading_cache(state: HtsClassifyAgentState):
    """
    保存heading层缓存
    """
    determine_heading_success = state.get("determine_heading_success")
    if determine_heading_success:
        await determine_heading_service.save_simil_cache(origin_item_name=state.get("item"),
                                                         rewritten_item=state.get("rewritten_item"),
                                                         chapter_codes=get_determined_chapter_codes(state),
                                                         alternative_headings=state.get("alternative_headings"))
    return {}


def after_get_cache_edge(state: HtsClassifyAgentState):
    if state.get("hit_heading_cache"):
        return [END]
    else:
        return [DetermineHeadingNodes.ASK_LLM_TO_DETERMINE_HEADING.value]


def after_llm_response_edge(state: HtsClassifyAgentState):
    if state.get("unexpected_error"):
        return [END]
    else:
        return [DetermineHeadingNodes.PROCESS_LLM_RESPONSE.value,
                DetermineHeadingNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION.value]


def after_process_llm_response_edge(state: HtsClassifyAgentState, config):
    # 如果是评估请求，则禁写缓存
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    if is_for_evaluation:
        return END

    determine_heading_success = state.get("determine_heading_success")
    if determine_heading_success:
        return DetermineHeadingNodes.SAVE_LAYERED_HEADING_CACHE.value
    return END


def get_determined_chapter_codes(state: HtsClassifyAgentState):
    """
    从state中获取上一环节确定的章节编码列表
    """
    heading_documents = state.get("heading_documents")
    chapter_details_dict = json.loads(heading_documents)
    return [chapter_description.split(":")[0] for chapter_description in chapter_details_dict]


def build_determine_heading_graph() -> CompiledStateGraph:
    """
    构建确定所属类目的图
    """
    graph_builder = StateGraph(HtsClassifyAgentState)
    graph_builder.add_node(DetermineHeadingNodes.ENTER_DETERMINE_HEADING, start_determine_heading)
    graph_builder.add_node(DetermineHeadingNodes.GET_HEADING_FROM_CACHE, get_from_cache)
    graph_builder.add_node(DetermineHeadingNodes.ASK_LLM_TO_DETERMINE_HEADING, ask_llm_to_determine_heading)
    graph_builder.add_node(DetermineHeadingNodes.PROCESS_LLM_RESPONSE, process_llm_response)
    graph_builder.add_node(DetermineHeadingNodes.SAVE_LAYERED_HEADING_CACHE, save_layered_heading_cache)
    graph_builder.add_node(DetermineHeadingNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION,
                           save_llm_confirm_heading_for_evaluation)

    graph_builder.add_edge(START, DetermineHeadingNodes.ENTER_DETERMINE_HEADING)
    graph_builder.add_edge(DetermineHeadingNodes.ENTER_DETERMINE_HEADING,
                           DetermineHeadingNodes.GET_HEADING_FROM_CACHE)
    graph_builder.add_conditional_edges(DetermineHeadingNodes.GET_HEADING_FROM_CACHE,
                                        after_get_cache_edge,
                                        {
                                            END: END,
                                            DetermineHeadingNodes.ASK_LLM_TO_DETERMINE_HEADING.value:
                                                DetermineHeadingNodes.ASK_LLM_TO_DETERMINE_HEADING,
                                        })
    graph_builder.add_conditional_edges(DetermineHeadingNodes.ASK_LLM_TO_DETERMINE_HEADING,
                                        after_llm_response_edge,
                                        {
                                            END: END,
                                            DetermineHeadingNodes.PROCESS_LLM_RESPONSE.value:
                                                DetermineHeadingNodes.PROCESS_LLM_RESPONSE,
                                            DetermineHeadingNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION.value:
                                                DetermineHeadingNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION,
                                        })
    graph_builder.add_conditional_edges(DetermineHeadingNodes.PROCESS_LLM_RESPONSE,
                                        after_process_llm_response_edge,
                                        {
                                            END: END,
                                            DetermineHeadingNodes.SAVE_LAYERED_HEADING_CACHE.value:
                                                DetermineHeadingNodes.SAVE_LAYERED_HEADING_CACHE
                                        })
    return graph_builder.compile()
