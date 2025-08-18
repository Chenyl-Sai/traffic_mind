from fastapi import APIRouter, Request, Body
from fastapi.params import Header
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.graph import END
from langgraph.types import Command
from langgraph.graph.state import CompiledStateGraph

from typing_extensions import Annotated
import json

from app.agent.constants import HtsAgents, RewriteItemNodes, RetrieveDocumentsNodes, DetermineChapterNodes, \
    DetermineHeadingNodes, DetermineSubheadingNodes, DetermineRateLineNodes, GenerateFinalOutputNodes
from app.schema.ask_response import SSEResponse, SSEMessageTypeEnum
from app.util.json_utils import pydantic_to_dict

agent_router = APIRouter()


@agent_router.post("/start_ask")
async def ask_item_hts(request: Request, thread_id: Annotated[str, Header()], message: Annotated[HumanMessage, Body()]):
    # get user & thread_id
    config = {"configurable": {"thread_id": thread_id}}
    graph: CompiledStateGraph = request.app.state.hts_graph
    stream = graph.astream({"item": message.content}, config, stream_mode="updates", subgraphs=True)
    return StreamingResponse(sse_generator(stream), media_type="text/event-stream")


@agent_router.post("/resume_ask")
async def resume_ask_item_hts(request: Request, thread_id: Annotated[str, Header()],
                              additional_messages: Annotated[HumanMessage, Body()]):
    config = {"configurable": {"thread_id": thread_id}}
    graph: CompiledStateGraph = request.app.state.hts_graph
    stream = graph.astream(Command(resume=additional_messages.content), config, stream_mode="updates", subgraphs=True)
    return StreamingResponse(sse_generator(stream), media_type="text/event-stream")


async def sse_generator(stream):
    # yield "retry: 100000\n\n"  # 设置客户端重连等待时间为10秒
    async for step in stream:
        print(step)
        path, updates = step
        # 主图节点
        if not path:
            for node, update_data in updates.items():
                # 中断
                if node == "__interrupt__":
                    for interrupt in update_data:
                        interrupt_value = interrupt.value
                        yield format_response(SSEMessageTypeEnum.INTERRUPT, SSEResponse(
                            message="需人工介入\n",
                            interrupt_reason=interrupt_value.get("interrupt_reason"),
                            expect_fields=interrupt_value.get("need_other_messages")))
                else:
                    error_message = update_data.get("unexpected_error_message")
                    if error_message:
                        yield format_response(SSEMessageTypeEnum.ERROR, SSEResponse(
                            message=f"{error_message}\n"))
                    else:
                        next_agent = update_data.get("next_agent", "")
                        if next_agent:
                            if next_agent == END:
                                yield format_response(SSEMessageTypeEnum.FINAL, SSEResponse(
                                    message=f"{update_data.get("final_output")}\n"))
        else:
            sub_graph_name = path[0].split(":")[0]
            # 商品重写节点
            if sub_graph_name == HtsAgents.REWRITE_ITEM.code:
                for node, update_data in updates.items():
                    if node == "__interrupt__":
                        # 所有子图的中断信息都会pop到主图中，子图中不处理了
                        continue
                    elif node == RewriteItemNodes.ENTER_REWRITE_ITEM:
                        yield format_response(SSEMessageTypeEnum.APPEND, SSEResponse(
                            message=f"正在进行商品重写...\n"))
                    elif node == RewriteItemNodes.PROCESS_LLM_RESPONSE or (
                        node == RewriteItemNodes.GET_REWRITE_ITEM_FROM_CACHE
                        and
                        update_data.get("hit_rewrite_cache")
                    ):
                        rewrite_success = update_data.get("rewrite_success")
                        if rewrite_success:
                            yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(
                                message=f"改写成功，改写结果:{update_data.get("rewritten_item")}\n"))
                        # elif rewrite_success != None:
                        #     yield format_response(SSEMessageTypeEnum.FINAL, SSEResponse(
                        #         message=f"请输入正确的商品信息\n"))
            # 文档检索节点
            if sub_graph_name == HtsAgents.RETRIEVE_DOCUMENTS.code:
                for node, update_data in updates.items():
                    if node == "__interrupt__":
                        # 所有子图的中断信息都会pop到主图中，子图中不处理了
                        continue
                    elif node == RetrieveDocumentsNodes.ENTER_RETRIEVE_DOCUMENTS:
                        document_type = update_data.get("current_document_type")
                        yield format_response(SSEMessageTypeEnum.APPEND, SSEResponse(
                            message=f"正在获取{document_type}相关信息...\n"))
            # 章节确定节点
            if sub_graph_name == HtsAgents.DETERMINE_CHAPTER.code:
                for node, update_data in updates.items():
                    if node == "__interrupt__":
                        # 所有子图的中断信息都会pop到主图中，子图中不处理了
                        continue
                    elif node == DetermineChapterNodes.ENTER_DETERMINE_CHAPTER:
                        yield format_response(SSEMessageTypeEnum.APPEND, SSEResponse(
                            message=f"正在确定章节信息...\n"))
                    elif node == DetermineChapterNodes.PROCESS_LLM_RESPONSE:
                        yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(
                            message=f"最高置信度章节如下:\n"))
                        main_chapter = update_data.get("main_chapter")
                        yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(
                            message=f"编码: {main_chapter.get("chapter_code")}\n"
                                    f"标题: {main_chapter.get("chapter_title")}\n"
                                    f"置信度: {main_chapter.get("confidence_score")}\n"
                                    f"原因:{main_chapter.get("reason")}\n"))
                        alternative_chapters = update_data.get("alternative_chapters")
                        if alternative_chapters:
                            yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(
                                message=f"\n候选章节如下:\n"))
                            for chapter in alternative_chapters:
                                yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(
                                    message=f"编码: {chapter.get("chapter_code")}\n"
                                            f"标题: {chapter.get("chapter_title")}\n"
                                            f"置信度: {chapter.get("confidence_score")}\n"
                                            f"原因:{chapter.get("reason")}\n"))
                                yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(message="\n"))
            # 类目确定节点
            if sub_graph_name == HtsAgents.DETERMINE_HEADING.code:
                for node, update_data in updates.items():
                    if node == "__interrupt__":
                        # 所有子图的中断信息都会pop到主图中，子图中不处理了
                        continue
                    elif node == DetermineHeadingNodes.ENTER_DETERMINE_HEADING:
                        yield format_response(SSEMessageTypeEnum.APPEND, SSEResponse(
                            message=f"正在确定类目信息...\n"))
                    elif node == DetermineHeadingNodes.PROCESS_LLM_RESPONSE:
                        yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(
                            message=f"最高置信度类目如下:\n"))
                        main_heading = update_data.get("main_heading")
                        yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(
                            message=f"编码: {main_heading.get("heading_code")}\n"
                                    f"标题: {main_heading.get("heading_title")}\n"
                                    f"置信度: {main_heading.get("confidence_score")}\n"
                                    f"原因:{main_heading.get("reason")}\n"))
                        alternative_headings = update_data.get("alternative_headings")
                        if alternative_headings:
                            yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(
                                message=f"\n候选类目如下:\n"))
                            for heading in alternative_headings:
                                yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(
                                    message=f"编码: {heading.get("heading_code")}\n"
                                            f"标题: {heading.get("heading_title")}\n"
                                            f"置信度: {heading.get("confidence_score")}\n"
                                            f"原因:{heading.get("reason")}\n"))
                                yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(message="\n"))
            # 子目确定节点
            if sub_graph_name == HtsAgents.DETERMINE_SUBHEADING.code:
                for node, update_data in updates.items():
                    if node == "__interrupt__":
                        # 所有子图的中断信息都会pop到主图中，子图中不处理了
                        continue
                    elif node == DetermineSubheadingNodes.ENTER_DETERMINE_SUBHEADING:
                        yield format_response(SSEMessageTypeEnum.APPEND, SSEResponse(
                            message=f"正在确定子目信息...\n"))
                    elif node == DetermineSubheadingNodes.PROCESS_LLM_RESPONSE:
                        yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(
                            message=f"最高置信度子目如下:\n"))
                        main_subheading = update_data.get("main_subheading")
                        yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(
                            message=f"编码: {main_subheading.get("subheading_code")}\n"
                                    f"标题: {main_subheading.get("subheading_title")}\n"
                                    f"置信度: {main_subheading.get("confidence_score")}\n"
                                    f"原因:{main_subheading.get("reason")}\n"))
                        alternative_subheadings = update_data.get("alternative_subheadings")
                        if alternative_subheadings:
                            yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(
                                message=f"\n候选子目如下:\n"))
                            for subheading in alternative_subheadings:
                                yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(
                                    message=f"编码: {subheading.get("subheading_code")}\n"
                                            f"标题: {subheading.get("subheading_title")}\n"
                                            f"置信度: {subheading.get("confidence_score")}\n"
                                            f"原因:{subheading.get("reason")}\n"))
                                yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(message="\n"))
            # 税率线确定节点
            if sub_graph_name == HtsAgents.DETERMINE_RATE_LINE.code:
                for node, update_data in updates.items():
                    if node == "__interrupt__":
                        # 所有子图的中断信息都会pop到主图中，子图中不处理了
                        continue
                    elif node == DetermineRateLineNodes.ENTER_DETERMINE_RATE_LINE:
                        yield format_response(SSEMessageTypeEnum.APPEND, SSEResponse(
                            message=f"正在确定税率线信息...\n"))
                    elif node == DetermineRateLineNodes.PROCESS_LLM_RESPONSE:
                        yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(
                            message=f"最终确定税率线如下:\n"))
                        main_rate_line = update_data.get("main_rate_line")
                        yield format_response(SSEMessageTypeEnum.HIDDEN, SSEResponse(
                            message=f"编码: {main_rate_line.get("rate_line_code")}\n"
                                    f"标题: {main_rate_line.get("rate_line_title")}\n"
                                    f"置信度: {main_rate_line.get("confidence_score")}\n"
                                    f"原因:{main_rate_line.get("reason")}\n"))
            if sub_graph_name == HtsAgents.GENERATE_FINAL_OUTPUT.code:
                for node, update_data in updates.items():
                    if node == "__interrupt__":
                        # 所有子图的中断信息都会pop到主图中，子图中不处理了
                        continue
                    elif node == GenerateFinalOutputNodes.ENTER_GENERATE_FINAL_OUTPUT:
                        yield format_response(SSEMessageTypeEnum.APPEND, SSEResponse(
                            message=f"正在生成最终输出...\n"))
                    elif node == GenerateFinalOutputNodes.ASK_LLM_TO_GENERATE_FINAL_OUTPUT:
                        yield format_response(SSEMessageTypeEnum.APPEND, SSEResponse(
                            message=f"HTS编码:{update_data.get('final_output').get('rate_line_code')}\n"
                                    f"{update_data.get('final_output').get('final_output_reason')}\n"))


def format_response(message_type: SSEMessageTypeEnum, sse_response: SSEResponse) -> str:
    message = sse_response.model_dump_json()
    return (f"event:{message_type.value}\n"
            f"data: {message}\n\n")


@agent_router.get("/graph_state")
async def get_graph_state(request: Request, thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    graph: CompiledStateGraph = request.app.state.hts_graph
    state_snapshot = await graph.aget_state(config, subgraphs=True)
    return json.dumps(pydantic_to_dict(state_snapshot.values), indent=2)
