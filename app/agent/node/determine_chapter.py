"""
确定所属章节
"""
import logging

from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
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
async def get_chapters_from_cache(state: HtsClassifyAgentState):
    """
    从缓存获取
    """
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
def process_llm_response(state: HtsClassifyAgentState):
    determine_chapter_response = state.get("determine_chapter_llm_response")

    main_chapter = determine_chapter_response.main_chapter
    alternative_chapters = determine_chapter_response.alternative_chapters
    fail_reason = determine_chapter_response.reason

    if main_chapter:
        final_alternative_chapters = [
            chapter for chapter in (alternative_chapters if alternative_chapters else [])
        ]

        return {
            "determine_chapter_success": True,
            "main_chapter": determine_chapter_response.main_chapter,
            "alternative_chapters": final_alternative_chapters
        }
    # TODO 改写失败直接先抛出异常
    raise Exception(fail_reason)


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_exact_match_cache(state: HtsClassifyAgentState):
    """
    保存结果
    """
    # TODO 修改文档版本
    rag_version = "2022"
    await determine_chapter_service.save_exact_cache(origin_item=state.get("item"),
                                                     chapter_documents=state.get("chapter_documents"),
                                                     rag_version=rag_version,
                                                     main_chapter=state.get("main_chapter"),
                                                     alternative_chapters=state.get("alternative_chapters"))
    return {}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_layered_chapter_cache(state: HtsClassifyAgentState, config, store: BaseStore):
    """
    保存分层的章节缓存
    """
    await determine_chapter_service.save_simil_cache(origin_item=state.get("item"),
                                                     rewritten_item=state.get("rewritten_item"),
                                                     main_chapter=state.get("main_chapter"),
                                                     alternative_chapters=state.get("alternative_chapters"))
    return {}


def after_get_cache_edge(state: HtsClassifyAgentState):
    hit_chapter_cache = state.get("hit_chapter_cache")
    if hit_chapter_cache:
        return [END]
    else:
        return [DetermineChapterNodes.USE_LLM_TO_DETERMINE_CHAPTER.value]


def after_process_llm_response_edge(state: HtsClassifyAgentState):
    determine_chapter_success = state.get("determine_chapter_success")
    if determine_chapter_success:
        return [DetermineChapterNodes.SAVE_EXACT_CHAPTER_CACHE.value,
                DetermineChapterNodes.SAVE_SIMIL_CHAPTER_CACHE.value, END]
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
                                        lambda state: "error" if state.get("unexpected_error") else "normal",
                                        {"error": END, "normal": DetermineChapterNodes.PROCESS_LLM_RESPONSE})
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
