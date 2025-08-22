"""
确定所属章节
"""
import logging, json

from langgraph.graph.state import CompiledStateGraph
from langgraph.graph import START, StateGraph, END

from app.agent.constants import DetermineChapterNodes
from app.agent.state import HtsClassifyAgentState
from app.agent.constants import HtsAgents
from app.agent.util.exception_handler import safe_raise_exception_node
from app.core.llm import base_qwen_llm
from app.llm.embedding.qwen import default_qwen_embeddings
from app.service.determine_chapter_service import DetermineChapterService

logger = logging.getLogger(__name__)

determine_chapter_service = DetermineChapterService(llm=base_qwen_llm, embeddings=default_qwen_embeddings)


def start_determine_chapter(state: HtsClassifyAgentState):
    return {"current_agent": HtsAgents.DETERMINE_CHAPTER.code}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def get_chapters_from_cache(state: HtsClassifyAgentState, config):
    """
    从缓存获取
    """
    # 如果是评估请求，则禁用缓存
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    if is_for_evaluation:
        return {"hit_chapter_cache": False}
    # TODO 修改文档版本
    rag_version = "2022"
    return await determine_chapter_service.get_from_cache(origin_item=state.get("item"),
                                                          rag_version=rag_version,
                                                          chapter_documents=state.get("chapter_documents"),
                                                          rewritten_item=state.get("rewritten_item"))


@safe_raise_exception_node(logger=logger)
async def ask_llm_to_determine_chapter(state: HtsClassifyAgentState):
    input_message, output_message, determine_response = await determine_chapter_service.determine_use_llm(
        rewritten_item=state.get("rewritten_item"), chapter_documents=state.get("chapter_documents"))
    return {"messages": [input_message, output_message], "determine_chapter_llm_response": determine_response}


@safe_raise_exception_node(logger=logger)
async def process_llm_response(state: HtsClassifyAgentState):
    return await determine_chapter_service.process_llm_response(state.get("determine_chapter_llm_response"))


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_exact_match_cache(state: HtsClassifyAgentState):
    """
    保存结果
    """
    # TODO 修改文档版本
    rag_version = "2022"

    chapter_codes = [json.loads(document).get("chapter_code") for document in state.get("chapter_documents")]
    sorted_chapter_codes = sorted(chapter_codes)
    await determine_chapter_service.save_exact_cache(origin_item=state.get("item"),
                                                     sorted_chapter_codes=sorted_chapter_codes,
                                                     rag_version=rag_version,
                                                     main_chapter=state.get("main_chapter"),
                                                     alternative_chapters=state.get("alternative_chapters"))
    return {}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_layered_chapter_cache(state: HtsClassifyAgentState):
    """
    保存分层的章节缓存
    """
    chapter_codes = [json.loads(document).get("chapter_code") for document in state.get("chapter_documents")]
    sorted_chapter_codes = sorted(chapter_codes)
    await determine_chapter_service.save_simil_cache(origin_item=state.get("item"),
                                                     rewritten_item=state.get("rewritten_item"),
                                                     sorted_chapter_codes=sorted_chapter_codes,
                                                     main_chapter=state.get("main_chapter"),
                                                     alternative_chapters=state.get("alternative_chapters"))
    return {}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_llm_confirm_result_for_evaluation(state: HtsClassifyAgentState, config):
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    evaluate_version = config["configurable"].get("evaluate_version", "-1")
    if is_for_evaluation:
        retrieved_chapters = state.get("chapter_documents")
        chapter_codes = [json.loads(document).get("chapter_code") for document in retrieved_chapters]
        await determine_chapter_service.save_llm_confirm_result_for_evaluation(
            evaluate_version=evaluate_version, origin_item=state.get("item"),
            rewritten_item=state.get("rewritten_item"),
            retrieved_chapter_codes=chapter_codes, llm_response=state.get("determine_chapter_llm_response")
        )
    return {}


def after_get_cache_edge(state: HtsClassifyAgentState):
    hit_chapter_cache = state.get("hit_chapter_cache")
    if hit_chapter_cache:
        return [END]
    else:
        return [DetermineChapterNodes.USE_LLM_TO_DETERMINE_CHAPTER.value]


def after_llm_response_edge(state: HtsClassifyAgentState):
    if state.get("unexpected_error"):
        return [END]
    else:
        return [DetermineChapterNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION.value,
                DetermineChapterNodes.PROCESS_LLM_RESPONSE.value]


def after_process_llm_response_edge(state: HtsClassifyAgentState, config):
    # 如果是评估请求，则禁写缓存
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    if is_for_evaluation:
        return END

    determine_chapter_success = state.get("determine_chapter_success")
    if determine_chapter_success:
        return [DetermineChapterNodes.SAVE_EXACT_CHAPTER_CACHE.value,
                DetermineChapterNodes.SAVE_SIMIL_CHAPTER_CACHE.value,
                END]
    else:
        return END


def build_determine_chapter_graph() -> CompiledStateGraph:
    """
    构建确定所属章节的图
    """
    graph_builder = StateGraph(HtsClassifyAgentState)
    graph_builder.add_node(DetermineChapterNodes.ENTER_DETERMINE_CHAPTER, start_determine_chapter)
    graph_builder.add_node(DetermineChapterNodes.GET_CHAPTER_FROM_CACHE, get_chapters_from_cache)
    graph_builder.add_node(DetermineChapterNodes.USE_LLM_TO_DETERMINE_CHAPTER, ask_llm_to_determine_chapter)
    graph_builder.add_node(DetermineChapterNodes.PROCESS_LLM_RESPONSE, process_llm_response)
    graph_builder.add_node(DetermineChapterNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION,
                           save_llm_confirm_result_for_evaluation)
    graph_builder.add_node(DetermineChapterNodes.SAVE_EXACT_CHAPTER_CACHE, save_exact_match_cache)
    graph_builder.add_node(DetermineChapterNodes.SAVE_SIMIL_CHAPTER_CACHE, save_layered_chapter_cache)

    graph_builder.add_edge(START, DetermineChapterNodes.ENTER_DETERMINE_CHAPTER)
    graph_builder.add_edge(DetermineChapterNodes.ENTER_DETERMINE_CHAPTER,
                           DetermineChapterNodes.GET_CHAPTER_FROM_CACHE)
    graph_builder.add_conditional_edges(DetermineChapterNodes.GET_CHAPTER_FROM_CACHE,
                                        after_get_cache_edge,
                                        {
                                            END: END,
                                            DetermineChapterNodes.USE_LLM_TO_DETERMINE_CHAPTER.value:
                                                DetermineChapterNodes.USE_LLM_TO_DETERMINE_CHAPTER,
                                        })
    graph_builder.add_conditional_edges(DetermineChapterNodes.USE_LLM_TO_DETERMINE_CHAPTER,
                                        after_llm_response_edge,
                                        {
                                            END: END,
                                            DetermineChapterNodes.PROCESS_LLM_RESPONSE.value:
                                                DetermineChapterNodes.PROCESS_LLM_RESPONSE,
                                            DetermineChapterNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION.value:
                                                DetermineChapterNodes.SAVE_LLM_RESPONSE_FOR_EVALUATION,
                                        })
    graph_builder.add_conditional_edges(DetermineChapterNodes.PROCESS_LLM_RESPONSE,
                                        after_process_llm_response_edge,
                                        {
                                            END: END,
                                            DetermineChapterNodes.SAVE_EXACT_CHAPTER_CACHE.value:
                                                DetermineChapterNodes.SAVE_EXACT_CHAPTER_CACHE,
                                            DetermineChapterNodes.SAVE_SIMIL_CHAPTER_CACHE.value:
                                                DetermineChapterNodes.SAVE_SIMIL_CHAPTER_CACHE,
                                        })
    return graph_builder.compile()
