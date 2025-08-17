"""
监督者agent
"""
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from psycopg_pool import AsyncConnectionPool

from app.agent.state import HtsClassifyAgentState
from app.agent.node import rewrite_item, retrieve_documents, determine_chapter, determine_heading, determine_subheading, \
    determine_rate_line, final_output
from app.core.config import settings
from app.agent.constants import HtsAgents


def agent_router(state: HtsClassifyAgentState):
    # 如果有异常了，直接就结束了
    error = state.get("unexpected_error")
    if error:
        return Command(update={"next_agent": END,
                               "unexpected_error_message": str(error)},
                       goto=END)
    # 刚进来，先重写商品
    if state.get("current_agent", HtsAgents.SUPERVISOR.code) == HtsAgents.SUPERVISOR.code:
        return Command(update={"next_agent": HtsAgents.REWRITE_ITEM.code}, goto=HtsAgents.REWRITE_ITEM.code)

    # 从重写完成返回，判断下一步走向
    if state.get("current_agent", HtsAgents.SUPERVISOR.code) == HtsAgents.REWRITE_ITEM.code:
        # 重写完成之后，查看状态数据决定走向
        if state.get("rewrite_success"):
            return Command(update={"next_agent": HtsAgents.RETRIEVE_DOCUMENTS.code, "current_document_type": "chapter"},
                           goto=HtsAgents.RETRIEVE_DOCUMENTS.code)
        else:
            return Command(update={"next_agent": END, "final_output": "请输入正确商品信息"}, goto=END)

    # 从文档检索返回，判断下一步走向
    if state.get("current_agent", HtsAgents.SUPERVISOR.code) == HtsAgents.RETRIEVE_DOCUMENTS.code:
        if state.get("current_document_type") == "chapter":
            return Command(update={"next_agent": HtsAgents.DETERMINE_CHAPTER, }, goto=HtsAgents.DETERMINE_CHAPTER.code)
        if state.get("current_document_type") == "heading":
            return Command(update={"next_agent": HtsAgents.DETERMINE_HEADING, }, goto=HtsAgents.DETERMINE_HEADING.code)
        if state.get("current_document_type") == "subheading":
            return Command(update={"next_agent": HtsAgents.DETERMINE_SUBHEADING, },
                           goto=HtsAgents.DETERMINE_SUBHEADING.code)
        if state.get("current_document_type") == "rate-line":
            return Command(update={"next_agent": HtsAgents.DETERMINE_RATE_LINE, },
                           goto=HtsAgents.DETERMINE_RATE_LINE.code)
    # LLM返回了可能的chapter列表，下一步获取chapter下heading的资料
    if state.get("current_agent", HtsAgents.SUPERVISOR.code) == HtsAgents.DETERMINE_CHAPTER.code:
        return Command(update={"next_agent": HtsAgents.RETRIEVE_DOCUMENTS, "current_document_type": "heading"},
                       goto=HtsAgents.RETRIEVE_DOCUMENTS.code)
    if state.get("current_agent", HtsAgents.SUPERVISOR.code) == HtsAgents.DETERMINE_HEADING.code:
        return Command(update={"next_agent": END, "final_output": "Temp End"}, goto=END)
        # return Command(update={"next_agent": HtsAgents.RETRIEVE_DOCUMENTS, "current_document_type": "subheading"},
        #                goto=HtsAgents.RETRIEVE_DOCUMENTS.code)
    if state.get("current_agent", HtsAgents.SUPERVISOR.code) == HtsAgents.DETERMINE_SUBHEADING.code:
        return Command(update={"next_agent": HtsAgents.RETRIEVE_DOCUMENTS, "current_document_type": "rate-line"},
                       goto=HtsAgents.RETRIEVE_DOCUMENTS.code)
    if state.get("current_agent", HtsAgents.SUPERVISOR.code) == HtsAgents.DETERMINE_RATE_LINE.code:
        return Command(update={"next_agent": HtsAgents.GENERATE_FINAL_OUTPUT},
                       goto=HtsAgents.GENERATE_FINAL_OUTPUT.code)
    if state.get("current_agent", HtsAgents.SUPERVISOR.code) == HtsAgents.GENERATE_FINAL_OUTPUT.code:
        return Command(update={"next_agent": END}, goto=END)

    # 生成最终输出
    return Command(update={"next_agent": END}, goto=END)


async def build_hts_classify_graph() -> CompiledStateGraph:
    hts_classify_graph_builder = StateGraph(HtsClassifyAgentState)
    hts_classify_graph_builder.add_node("agent_router", agent_router)
    sub_graph_rewrite_item = rewrite_item.build_rewrite_item_graph()
    sub_graph_retrieve_documents = retrieve_documents.build_retrieve_documents_graph()
    sub_graph_determine_chapter = determine_chapter.build_determine_chapter_graph()
    sub_graph_determine_heading = determine_heading.build_determine_heading_graph()
    sub_graph_determine_subheading = determine_subheading.build_determine_subheading_graph()
    sub_graph_determine_rate_line = determine_rate_line.build_determine_subheading_graph()
    sub_graph_generate_final_output = final_output.build_generate_final_output_graph()
    hts_classify_graph_builder.add_node(HtsAgents.REWRITE_ITEM.code, sub_graph_rewrite_item)
    hts_classify_graph_builder.add_node(HtsAgents.RETRIEVE_DOCUMENTS.code, sub_graph_retrieve_documents)
    hts_classify_graph_builder.add_node(HtsAgents.DETERMINE_CHAPTER.code, sub_graph_determine_chapter)
    hts_classify_graph_builder.add_node(HtsAgents.DETERMINE_HEADING.code, sub_graph_determine_heading)
    hts_classify_graph_builder.add_node(HtsAgents.DETERMINE_SUBHEADING.code, sub_graph_determine_subheading)
    hts_classify_graph_builder.add_node(HtsAgents.DETERMINE_RATE_LINE.code, sub_graph_determine_rate_line)
    hts_classify_graph_builder.add_node(HtsAgents.GENERATE_FINAL_OUTPUT.code, sub_graph_generate_final_output)

    hts_classify_graph_builder.add_edge(START, "agent_router")

    hts_classify_graph_builder.add_edge(HtsAgents.REWRITE_ITEM.code, "agent_router")
    hts_classify_graph_builder.add_edge(HtsAgents.RETRIEVE_DOCUMENTS.code, "agent_router")
    hts_classify_graph_builder.add_edge(HtsAgents.DETERMINE_CHAPTER.code, "agent_router")
    hts_classify_graph_builder.add_edge(HtsAgents.DETERMINE_HEADING.code, "agent_router")
    hts_classify_graph_builder.add_edge(HtsAgents.DETERMINE_SUBHEADING.code, "agent_router")
    hts_classify_graph_builder.add_edge(HtsAgents.DETERMINE_RATE_LINE.code, "agent_router")
    hts_classify_graph_builder.add_edge(HtsAgents.GENERATE_FINAL_OUTPUT.code, "agent_router")

    # 增加checkpoint
    pool = AsyncConnectionPool(conninfo=str(settings.postgres_database_uri),
                               max_size=10)
    async with await pool.getconn() as conn1:
        await conn1.set_autocommit(True)
        checkpointer = AsyncPostgresSaver(conn1)
        await checkpointer.setup()

    checkpointer = AsyncPostgresSaver(conn=pool)
    return hts_classify_graph_builder.compile(checkpointer=checkpointer)
