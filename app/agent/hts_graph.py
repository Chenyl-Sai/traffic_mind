"""
监督者agent
"""
import logging

from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from psycopg_pool import AsyncConnectionPool

from app.agent.state import HtsClassifyAgentState
from app.agent.node import rewrite_item, retrieve_documents, determine_heading, determine_subheading, \
    determine_rate_line, final_output
from app.agent.util.exception_handler import safe_raise_exception_node
from app.core.config import settings
from app.agent.constants import HtsAgents, SupervisorNodes, DocumentTypes
from app.service.hts_classify_supervisor_service import HtsClassifySupervisorService

logger = logging.getLogger(__name__)

hts_classify_supervisor_service = HtsClassifySupervisorService()


@safe_raise_exception_node(logger=logger, ignore_exception=True)
async def get_from_cache(state: HtsClassifyAgentState, config):
    is_for_evaluation = config["configurable"].get("is_for_evaluation", False)
    if is_for_evaluation:
        return {"hit_e2e_exact_cache": False}
    else:
        return await hts_classify_supervisor_service.get_e2e_exact_cache(state.get("item"))


@safe_raise_exception_node(logger=logger)
async def agent_router(state: HtsClassifyAgentState):
    # 如果有异常了，直接就结束了
    error = state.get("unexpected_error")
    if error:
        return Command(update={"unexpected_error_message": "系统繁忙，请稍后重试"},
                       goto=END)
    # 刚进来，先重写商品
    if state.get("current_agent", HtsAgents.SUPERVISOR.code) == HtsAgents.SUPERVISOR.code:
        return Command(goto=HtsAgents.REWRITE_ITEM.code)

    # 从重写完成返回，判断下一步走向
    if state.get("current_agent", HtsAgents.SUPERVISOR.code) == HtsAgents.REWRITE_ITEM.code:
        # 如果获取到e2e的环境，则直接返回
        if state.get("hit_e2e_simil_cache"):
            return Command(goto=END)
        # 重写完成之后，查看状态数据决定走向
        if state.get("rewrite_success"):
            # 直接使用heading,弃用先chapter再heading，一步到位
            return Command(update={"current_document_type": DocumentTypes.HEADING},
                           goto=HtsAgents.RETRIEVE_DOCUMENTS.code)
        else:
            return Command(update={"final_description": "请输入正确商品信息"}, goto=END)

    # 从文档检索返回，判断下一步走向
    if state.get("current_agent", HtsAgents.SUPERVISOR.code) == HtsAgents.RETRIEVE_DOCUMENTS.code:
        if state.get("current_document_type") == DocumentTypes.HEADING:
            return Command(goto=HtsAgents.DETERMINE_HEADING.code)
        if state.get("current_document_type") == DocumentTypes.SUBHEADING:
            return Command(goto=HtsAgents.DETERMINE_SUBHEADING.code)
        if state.get("current_document_type") == DocumentTypes.RATE_LINE:
            return Command(goto=HtsAgents.DETERMINE_RATE_LINE.code)
    # LLM返回了可能的chapter列表，下一步获取chapter下heading的资料
    if state.get("current_agent", HtsAgents.SUPERVISOR.code) == HtsAgents.DETERMINE_HEADING.code:
        return Command(update={"current_document_type": DocumentTypes.SUBHEADING},
                       goto=HtsAgents.RETRIEVE_DOCUMENTS.code)
    if state.get("current_agent", HtsAgents.SUPERVISOR.code) == HtsAgents.DETERMINE_SUBHEADING.code:
        return Command(update={"current_document_type": DocumentTypes.RATE_LINE},
                       goto=HtsAgents.RETRIEVE_DOCUMENTS.code)
    if state.get("current_agent", HtsAgents.SUPERVISOR.code) == HtsAgents.DETERMINE_RATE_LINE.code:
        return Command(goto=HtsAgents.GENERATE_FINAL_OUTPUT.code)
    if state.get("current_agent", HtsAgents.SUPERVISOR.code) == HtsAgents.GENERATE_FINAL_OUTPUT.code:
        return {}

    # return Command(update={"final_description": "Temp End"}, goto=END)
    # 生成最终输出
    return {}


def after_get_from_cache_edge(state: HtsClassifyAgentState):
    """
    如果获取到精确缓存，流程直接结束了
    """
    if state.get("hit_e2e_exact_cache"):
        return [END]
    else:
        return SupervisorNodes.AGENT_ROUTER.value

def after_rewrite_item_edge(state: HtsClassifyAgentState):
    """
    重写节点返回之后，可能是获取到语义相似度缓存了，直接就可以返回，不用走后续流程了
    """


async def build_hts_classify_graph() -> CompiledStateGraph:
    hts_classify_graph_builder = StateGraph(HtsClassifyAgentState)
    hts_classify_graph_builder.add_node(SupervisorNodes.GET_FROM_CACHE, get_from_cache)
    hts_classify_graph_builder.add_node(SupervisorNodes.AGENT_ROUTER, agent_router)
    sub_graph_rewrite_item = rewrite_item.build_rewrite_item_graph()
    sub_graph_retrieve_documents = retrieve_documents.build_retrieve_documents_graph()
    sub_graph_determine_heading = determine_heading.build_determine_heading_graph()
    sub_graph_determine_subheading = determine_subheading.build_determine_subheading_graph()
    sub_graph_determine_rate_line = determine_rate_line.build_determine_subheading_graph()
    sub_graph_generate_final_output = final_output.build_generate_final_output_graph()
    hts_classify_graph_builder.add_node(HtsAgents.REWRITE_ITEM.code, sub_graph_rewrite_item)
    hts_classify_graph_builder.add_node(HtsAgents.RETRIEVE_DOCUMENTS.code, sub_graph_retrieve_documents)
    hts_classify_graph_builder.add_node(HtsAgents.DETERMINE_HEADING.code, sub_graph_determine_heading)
    hts_classify_graph_builder.add_node(HtsAgents.DETERMINE_SUBHEADING.code, sub_graph_determine_subheading)
    hts_classify_graph_builder.add_node(HtsAgents.DETERMINE_RATE_LINE.code, sub_graph_determine_rate_line)
    hts_classify_graph_builder.add_node(HtsAgents.GENERATE_FINAL_OUTPUT.code, sub_graph_generate_final_output)

    hts_classify_graph_builder.add_edge(START, SupervisorNodes.GET_FROM_CACHE)
    hts_classify_graph_builder.add_conditional_edges(SupervisorNodes.GET_FROM_CACHE,
                                                     after_get_from_cache_edge,
                                                     {
                                                         END: END,
                                                         SupervisorNodes.AGENT_ROUTER.value: SupervisorNodes.AGENT_ROUTER
                                                     })

    hts_classify_graph_builder.add_edge(HtsAgents.REWRITE_ITEM.code, SupervisorNodes.AGENT_ROUTER)
    hts_classify_graph_builder.add_edge(HtsAgents.RETRIEVE_DOCUMENTS.code, SupervisorNodes.AGENT_ROUTER)
    hts_classify_graph_builder.add_edge(HtsAgents.DETERMINE_HEADING.code, SupervisorNodes.AGENT_ROUTER)
    hts_classify_graph_builder.add_edge(HtsAgents.DETERMINE_SUBHEADING.code, SupervisorNodes.AGENT_ROUTER)
    hts_classify_graph_builder.add_edge(HtsAgents.DETERMINE_RATE_LINE.code, SupervisorNodes.AGENT_ROUTER)
    hts_classify_graph_builder.add_edge(HtsAgents.GENERATE_FINAL_OUTPUT.code, SupervisorNodes.AGENT_ROUTER)

    # 增加checkpoint
    pool = AsyncConnectionPool(conninfo=str(settings.postgres_database_uri),
                               max_size=10)
    async with await pool.getconn() as conn1:
        await conn1.set_autocommit(True)
        checkpointer = AsyncPostgresSaver(conn1)
        await checkpointer.setup()

    checkpointer = AsyncPostgresSaver(conn=pool)
    return hts_classify_graph_builder.compile(checkpointer=checkpointer)
