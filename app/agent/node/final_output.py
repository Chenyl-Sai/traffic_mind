"""
生成最终输出
"""
import logging

from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.graph import START, StateGraph, END

from app.agent.constants import GenerateFinalOutputNodes
from app.agent.state import HtsClassifyAgentState, state_has_error
from app.agent.constants import HtsAgents
from app.agent.util.exception_handler import safe_raise_exception_node
from app.core.llm import base_qwen_llm
from app.llm.embedding.qwen import default_qwen_embeddings
from app.service.final_output_service import FinalOutputService

logger = logging.getLogger(__name__)

final_output_service = FinalOutputService(llm=base_qwen_llm, embeddings=default_qwen_embeddings)


def start_generate_final_output(state: HtsClassifyAgentState):
    return {"current_agent": HtsAgents.GENERATE_FINAL_OUTPUT.code}


@safe_raise_exception_node(logger=logger)
async def ask_llm_to_generate_final_output(state: HtsClassifyAgentState, config, store: BaseStore):
    confirmed_rate_line = state.get("main_rate_line")
    final_rate_line_code = confirmed_rate_line.get("rate_line_code")
    final_subheading_code = final_rate_line_code[:6]
    final_heading_code = final_subheading_code[:4]
    final_chapter_code = final_heading_code[:2]
    final_heading_reason = \
        next((heading.get("reason") for heading in
              ([state.get("main_heading")] + (state.get("alternative_headings") or []))
              if heading.get("heading_code") == final_heading_code), None)
    final_subheading_reason = \
        next((subheading.get("reason") for subheading in
              ([state.get("main_subheading")] + (state.get("alternative_subheadings") or []))
              if subheading.get("subheading_code") == final_subheading_code), None)

    input_message, output_message, llm_response = await final_output_service.get_final_output_from_llm(
        origin_item_name=state["item"],
        rewritten_item=state.get("rewritten_item"),
        heading_candidates=state.get("candidate_heading_codes").get(
            final_chapter_code),
        selected_heading=final_heading_code,
        select_heading_reason=final_heading_reason,
        subheading_candidates=state.get(
            "candidate_subheading_codes").get(final_heading_code),
        selected_subheading=final_subheading_code,
        select_subheading_reason=final_subheading_reason,
        rate_line_candidates=state.get(
            "candidate_rate_line_codes").get(final_subheading_code),
        selected_rate_line=final_rate_line_code,
        select_rate_line_reason=confirmed_rate_line.get("reason"))

    return {"messages": [input_message, output_message], "final_output_llm_response": llm_response}


@safe_raise_exception_node(logger=logger)
async def process_llm_response(state: HtsClassifyAgentState):
    """
    处理llm返回
    """
    response = state.get("final_output_llm_response")
    return {"final_rate_line_code": response.rate_line_code, "final_description": response.final_output_reason}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_exact_e2e_cache(state: HtsClassifyAgentState, config):
    """
    保存精确的e2e缓存
    """
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    if is_for_evaluation:
        return {}
    confirmed_rate_line = state.get("main_rate_line")
    final_rate_line_code = confirmed_rate_line.get("rate_line_code")
    final_subheading_code = final_rate_line_code[:6]
    final_heading_code = final_subheading_code[:4]
    final_chapter_code = final_heading_code[:2]
    final_heading_title = \
        next((heading.get("heading_title") for heading in
              ([state.get("main_heading")] + (state.get("alternative_headings") or []))
              if heading.get("heading_code") == final_heading_code), None)
    final_heading_reason = \
        next((heading.get("reason") for heading in
              ([state.get("main_heading")] + (state.get("alternative_headings") or []))
              if heading.get("heading_code") == final_heading_code), None)
    final_subheading_title = \
        next((subheading.get("subheading_title") for subheading in
              ([state.get("main_subheading")] + (state.get("alternative_subheadings") or []))
              if subheading.get("subheading_code") == final_subheading_code), None)
    final_subheading_reason = \
        next((subheading.get("reason") for subheading in
              ([state.get("main_subheading")] + (state.get("alternative_subheadings") or []))
              if subheading.get("subheading_code") == final_subheading_code), None)
    await final_output_service.save_e2e_exact_cache(origin_item_name=state.get("item"),
                                                    rewritten_item=state.get("rewritten_item"),
                                                    chapter_code=final_chapter_code,
                                                    heading_code=final_heading_code,
                                                    heading_title=final_heading_title,
                                                    heading_reason=final_heading_reason,
                                                    subheading_code=final_subheading_code,
                                                    subheading_title=final_subheading_title,
                                                    subheading_reason=final_subheading_reason,
                                                    rate_line_code=final_rate_line_code,
                                                    rate_line_title=confirmed_rate_line.get("rate_line_title"),
                                                    rate_line_reason=confirmed_rate_line.get("reason"),
                                                    final_output_response=state.get("final_output_llm_response"))
    return {}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_simil_e2e_cache(state: HtsClassifyAgentState, config):
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    if is_for_evaluation:
        return {}

    await final_output_service.save_e2e_simil_cache(origin_item_name=state.get("item"),
                                                    rewritten_item=state.get("rewritten_item"),
                                                    rate_line_code=state.get("main_rate_line").get("rate_line_code"),
                                                    rate_line_title=state.get("main_rate_line").get("rate_line_title"),
                                                    final_output_response=state.get("final_description"))
    return {}


def after_llm_response_edge(state: HtsClassifyAgentState):
    if state_has_error(state):
        return END
    else:
        return GenerateFinalOutputNodes.PROCESS_LLM_RESPONSE


def after_process_llm_response_edge(state: HtsClassifyAgentState):
    if state_has_error(state):
        return END
    else:
        return [GenerateFinalOutputNodes.SAVE_EXACT_E2E_CACHE,
                GenerateFinalOutputNodes.SAVE_SIMIL_E2E_CACHE]


def build_generate_final_output_graph() -> CompiledStateGraph:
    """
    生成最终输出
    """
    graph_builder = StateGraph(HtsClassifyAgentState)

    graph_builder.add_node(GenerateFinalOutputNodes.ENTER_GENERATE_FINAL_OUTPUT,
                           start_generate_final_output)
    graph_builder.add_node(GenerateFinalOutputNodes.ASK_LLM_TO_GENERATE_FINAL_OUTPUT,
                           ask_llm_to_generate_final_output)
    graph_builder.add_node(GenerateFinalOutputNodes.PROCESS_LLM_RESPONSE, process_llm_response)
    graph_builder.add_node(GenerateFinalOutputNodes.SAVE_EXACT_E2E_CACHE, save_exact_e2e_cache)
    graph_builder.add_node(GenerateFinalOutputNodes.SAVE_SIMIL_E2E_CACHE, save_simil_e2e_cache)

    graph_builder.add_edge(START, GenerateFinalOutputNodes.ENTER_GENERATE_FINAL_OUTPUT)
    graph_builder.add_edge(GenerateFinalOutputNodes.ENTER_GENERATE_FINAL_OUTPUT,
                           GenerateFinalOutputNodes.ASK_LLM_TO_GENERATE_FINAL_OUTPUT)
    graph_builder.add_conditional_edges(GenerateFinalOutputNodes.ASK_LLM_TO_GENERATE_FINAL_OUTPUT,
                                        after_llm_response_edge,
                                        {
                                            END: END,
                                            GenerateFinalOutputNodes.PROCESS_LLM_RESPONSE.value:
                                                GenerateFinalOutputNodes.PROCESS_LLM_RESPONSE,
                                        })
    graph_builder.add_conditional_edges(GenerateFinalOutputNodes.PROCESS_LLM_RESPONSE,
                                        after_process_llm_response_edge,
                                        {
                                            END: END,
                                            GenerateFinalOutputNodes.SAVE_EXACT_E2E_CACHE.value:
                                                GenerateFinalOutputNodes.SAVE_EXACT_E2E_CACHE,
                                            GenerateFinalOutputNodes.SAVE_SIMIL_E2E_CACHE.value:
                                                GenerateFinalOutputNodes.SAVE_SIMIL_E2E_CACHE,
                                        })
    return graph_builder.compile()
