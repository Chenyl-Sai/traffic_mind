"""
获取相关文档
"""
import json, logging

from datetime import datetime, timezone

from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.graph import START, StateGraph

from app.agent.constants import RetrieveDocumentsNodes
from app.agent.state import HtsClassifyAgentState, state_has_error
from app.agent.constants import HtsAgents
from app.agent.util.exception_handler import safe_raise_exception_node
from app.core.constants import IndexName
from app.core.opensearch import get_async_client
from app.dep.llm import get_vector_store
from app.service.hts_service import get_rate_lines_by_wco_subheadings
from app.service.wco_hs_service import get_heading_detail_by_chapter_codes, get_subheading_detail_by_heading_codes, \
    get_subheading_dict_by_subheading_codes

logger = logging.getLogger(__name__)


def start_retrieve_documents(state: HtsClassifyAgentState):
    return {"current_agent": HtsAgents.RETRIEVE_DOCUMENTS.code,
            "current_document_type": state.get("current_document_type")}


@safe_raise_exception_node(logger=logger)
async def retrieve_documents(state: HtsClassifyAgentState, config, store: BaseStore):
    vectorstore = get_vector_store()
    if state.get("current_document_type") == "chapter":
        chapter_documents = vectorstore.search(query_text=state.get("item"),
                                               search_type="similarity",
                                               filter={"type": "chapter"},
                                               k=10)
        if chapter_documents:
            return {"chapter_documents": [document.page_content for document in chapter_documents]}
        else:
            return {"chapter_documents": []}
    elif state.get("current_document_type") == "heading":
        # 从数据库获取chapter下heading信息
        chapter_codes = [state.get("main_chapter").chapter_code]
        alternative_chapters = state.get("alternative_chapters")
        if alternative_chapters:
            chapter_codes.extend([alternative_chapter.chapter_code for alternative_chapter in alternative_chapters])
        chapter_detail_dict = await get_heading_detail_by_chapter_codes(chapter_codes)
        return {"heading_documents": json.dumps(chapter_detail_dict, ensure_ascii=False)}
    elif state.get("current_document_type") == "subheading":
        # 从数据库获取heading下subheading信息
        heading_codes = [state.get("main_heading").heading_code]
        alternative_headings = state.get("alternative_headings")
        if alternative_headings:
            heading_codes.extend([alternative_heading.heading_code for alternative_heading in alternative_headings])
        heading_detail_dict = await get_subheading_detail_by_heading_codes(heading_codes)
        return {"subheading_documents": json.dumps(heading_detail_dict, ensure_ascii=False)}
    elif state.get("current_document_type") == "rate-line":
        subheading_codes = [state.get("main_subheading").subheading_code]
        alternative_subheadings = state.get("alternative_subheadings")
        if alternative_subheadings:
            subheading_codes.extend(
                [alternative_subheading.subheading_code for alternative_subheading in alternative_subheadings])
        sub_heading_tree = await get_subheading_dict_by_subheading_codes(subheading_codes)
        sub_heading_detail_dict = await get_rate_lines_by_wco_subheadings(subheading_codes)
        for chapter_key, chapter_details in sub_heading_tree.items():
            for heading_key, heading_details in chapter_details.items():
                for subheading_key, _ in heading_details.items():
                    sub_heading_code = subheading_key.split(":")[0]
                    subheading_details = sub_heading_detail_dict.get(sub_heading_code)
                    heading_details.update({subheading_key: subheading_details})
        return {"rate_line_documents": json.dumps(sub_heading_tree, ensure_ascii=False)}


async def save_retrieve_result_for_evaluation(state: HtsClassifyAgentState, config, store: BaseStore):
    try:
        is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
        evaluate_version = config["configurable"].get("evaluate_version", "-1")
        if is_for_evaluation:
            # 有异常直接返回
            if state_has_error(state):
                return {}
            if state.get("current_document_type") == "chapter":
                # 保存一下获取的chapter信息用于评估准确性
                document = {
                    "evaluate_version": evaluate_version,
                    "origin_item_name": state.get("item"),
                    "rewritten_item": state.get("rewritten_item"),
                    "chapter_documents": state.get("chapter_documents"),
                    "created_at": datetime.now(timezone.utc),
                }
                async with get_async_client() as async_client:
                    await async_client.index(index=IndexName.EVALUATE_RETRIEVE_CHAPTER, body=document)
    except Exception as e:
        logger.exception("Save retrieve chapter result failed", exc_info=e)
    return {}


def build_retrieve_documents_graph() -> CompiledStateGraph:
    graph_builder = StateGraph(HtsClassifyAgentState)
    graph_builder.add_node(RetrieveDocumentsNodes.ENTER_RETRIEVE_DOCUMENTS, start_retrieve_documents)
    graph_builder.add_node(RetrieveDocumentsNodes.RETRIEVE_DOCUMENTS, retrieve_documents)
    graph_builder.add_node(RetrieveDocumentsNodes.SAVE_RETRIEVE_RESULT_FOR_EVALUATION,
                           save_retrieve_result_for_evaluation)

    graph_builder.add_edge(START, RetrieveDocumentsNodes.ENTER_RETRIEVE_DOCUMENTS)
    graph_builder.add_edge(RetrieveDocumentsNodes.ENTER_RETRIEVE_DOCUMENTS,
                           RetrieveDocumentsNodes.RETRIEVE_DOCUMENTS)
    graph_builder.add_edge(RetrieveDocumentsNodes.RETRIEVE_DOCUMENTS,
                           RetrieveDocumentsNodes.SAVE_RETRIEVE_RESULT_FOR_EVALUATION)
    return graph_builder.compile()
