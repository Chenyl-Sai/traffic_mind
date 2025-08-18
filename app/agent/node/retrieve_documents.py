"""
获取相关文档
"""
import json, logging

from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.graph import START, StateGraph

from app.agent.constants import RetrieveDocumentsNodes
from app.agent.state import HtsClassifyAgentState, state_has_error
from app.agent.constants import HtsAgents
from app.agent.util.exception_handler import safe_raise_exception_node
from app.dep.llm import get_chapter_vector_store
from app.service.hts_service import get_rate_lines_by_wco_subheadings
from app.service.retrieve_documents_service import RetrieveDocumentsService
from app.service.wco_hs_service import get_heading_detail_by_chapter_codes, get_subheading_detail_by_heading_codes, \
    get_subheading_dict_by_subheading_codes

logger = logging.getLogger(__name__)

retrieve_service = RetrieveDocumentsService(chapter_vectorstore=get_chapter_vector_store())


def start_retrieve_documents(state: HtsClassifyAgentState):
    return {"current_agent": HtsAgents.RETRIEVE_DOCUMENTS.code,
            "current_document_type": state.get("current_document_type")}


@safe_raise_exception_node(logger=logger)
async def retrieve_documents(state: HtsClassifyAgentState, config, store: BaseStore):
    if state.get("current_document_type") == "chapter":
        chapter_documents = await retrieve_service.retrieve_chapter_documents(state.get("rewritten_item"))
        return {"chapter_documents": chapter_documents}
    elif state.get("current_document_type") == "heading":
        # 从数据库获取chapter下heading信息
        chapter_codes = [state.get("main_chapter").get("chapter_code")]
        alternative_chapters = state.get("alternative_chapters")
        if alternative_chapters:
            chapter_codes.extend([alternative_chapter.get("chapter_code") for alternative_chapter in alternative_chapters])
        return {"heading_documents": await retrieve_service.retrieve_heading_documents(chapter_codes)}
    elif state.get("current_document_type") == "subheading":
        # 从数据库获取heading下subheading信息
        heading_codes = [state.get("main_heading").get("heading_code")]
        alternative_headings = state.get("alternative_headings")
        if alternative_headings:
            heading_codes.extend([alternative_heading.get("heading_code") for alternative_heading in alternative_headings])
        return {"subheading_documents": await retrieve_service.retrieve_subheading_documents(heading_codes)}
    elif state.get("current_document_type") == "rate-line":
        subheading_codes = [state.get("main_subheading").get("subheading_code")]
        alternative_subheadings = state.get("alternative_subheadings")
        if alternative_subheadings:
            subheading_codes.extend(
                [alternative_subheading.get("subheading_code") for alternative_subheading in alternative_subheadings])
        return {"rate_line_documents": await retrieve_service.retrieve_rate_line_documents(subheading_codes)}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_retrieve_result_for_evaluation(state: HtsClassifyAgentState, config):
    # 有异常直接返回
    if state_has_error(state):
        return {}
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    evaluate_version = config["configurable"].get("evaluate_version", "-1")
    # 只有评估请求才记录
    if is_for_evaluation:
        if state.get("current_document_type") == "chapter":
            documents = state.get("chapter_documents")
            documents_dict_list = [json.loads(document) for document in documents]
            await retrieve_service.save_chapter_retrieve_evaluation(
                evaluate_version,
                origin_item_name=state.get("item"),
                rewritten_item=state.get("rewritten_item"),
                chapter_documents=documents_dict_list
            )
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
