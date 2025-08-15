from typing import Annotated

from fastapi import APIRouter, Request, Header
from fastapi.params import Header

from langgraph.graph.state import CompiledStateGraph

from app.service.evaluation_service import get_hts_classify_evaluation_result
evaluation_router = APIRouter()


@evaluation_router.post("/hts_classify")
async def hts_classify_evaluation(request: Request,
                                  item_name: str,
                                  evaluate_version: str,
                                  thread_id: Annotated[str, Header()]):
    """
    对商品分类进行评估
    """
    graph: CompiledStateGraph = request.app.state.hts_graph
    config = {"configurable": {"thread_id": thread_id, "is_for_evaluation": True, "evaluate_version": evaluate_version}}
    stream = graph.astream({"item": item_name}, config, stream_mode="updates", subgraphs=True)
    result = ""
    async for step in stream:
        result += str(step) + "\n"
    return result


@evaluation_router.get("hts_classify_result")
async def hts_classify_evaluation_result(evaluate_version: str):
    """
    获取商品分类评估结果
    """
    return await get_hts_classify_evaluation_result(evaluate_version)