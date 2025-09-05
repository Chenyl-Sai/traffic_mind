"""
获取相关文档
"""
import json, logging
from xml.dom.minidom import DocumentType

from langgraph.graph.state import CompiledStateGraph
from langgraph.graph import START, StateGraph

from app.agent.constants import RetrieveDocumentsNodes, DocumentTypes
from app.agent.state import HtsClassifyAgentState, state_has_error
from app.agent.constants import HtsAgents
from app.agent.util.exception_handler import safe_raise_exception_node
from app.core.milvus import get_async_milvus_client
from app.service.retrieve_documents_service import RetrieveDocumentsService

logger = logging.getLogger(__name__)

retrieve_service = RetrieveDocumentsService(async_milvus_client=get_async_milvus_client())


def start_retrieve_documents(state: HtsClassifyAgentState):
    return {"current_agent": HtsAgents.RETRIEVE_DOCUMENTS.code,
            "current_document_type": state.get("current_document_type")}


@safe_raise_exception_node(logger=logger)
async def retrieve_documents(state: HtsClassifyAgentState):
    if state.get("current_document_type") == DocumentTypes.HEADING:
        heading_documents, candidate_heading_codes = await retrieve_service.retrieve_heading_documents(
            state.get("rewritten_item"))
        return {"heading_documents": heading_documents, "candidate_heading_codes": candidate_heading_codes}
    if state.get("current_document_type") == DocumentTypes.SUBHEADING:
        # 从数据库获取heading下subheading信息
        heading_codes = [state.get("main_heading").get("heading_code")]
        alternative_headings = state.get("alternative_headings")
        if alternative_headings:
            heading_codes.extend(
                [alternative_heading.get("heading_code") for alternative_heading in alternative_headings])
        subheading_documents, candidate_subheading_codes = await retrieve_service.retrieve_subheading_documents(
            heading_codes)
        return {"subheading_documents": subheading_documents, "candidate_subheading_codes": candidate_subheading_codes}
    if state.get("current_document_type") == DocumentTypes.RATE_LINE:
        subheading_codes = [state.get("main_subheading").get("subheading_code")]
        alternative_subheadings = state.get("alternative_subheadings")
        if alternative_subheadings:
            subheading_codes.extend(
                [alternative_subheading.get("subheading_code") for alternative_subheading in alternative_subheadings])
        rate_line_document, candidate_rate_line_codes = await retrieve_service.retrieve_rate_line_documents(
            subheading_codes)
        return {"rate_line_documents": rate_line_document, "candidate_rate_line_codes": candidate_rate_line_codes}


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def save_retrieve_result_for_evaluation(state: HtsClassifyAgentState, config):
    # 有异常直接返回
    if state_has_error(state):
        return {}
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    evaluate_version = config["configurable"].get("evaluate_version", "-1")
    # 只有评估请求才记录
    if is_for_evaluation:
        if state.get("current_document_type") == DocumentTypes.HEADING:
            candidate_heading_codes_dict = state.get("candidate_heading_codes")
            candidate_heading_codes = [code for code_list in candidate_heading_codes_dict.values() for code in
                                       code_list]
            await retrieve_service.save_heading_retrieve_evaluation(
                evaluate_version,
                origin_item_name=state.get("item"),
                rewritten_item=state.get("rewritten_item"),
                candidate_heading_codes=candidate_heading_codes,
                actual_heading=config["configurable"].get("hscode", "")[:4]
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
