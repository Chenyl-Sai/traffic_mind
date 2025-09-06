import uuid
from typing import Annotated
import pandas as pd
import asyncio

from fastapi import APIRouter, Request, Header
from fastapi.params import Header

from langgraph.graph.state import CompiledStateGraph

from app.service.evaluation_service import get_hts_classify_evaluation_result, do_batch_hts_classify_evaluation

evaluation_router = APIRouter()


@evaluation_router.post("/hts_classify")
async def hts_classify_evaluation(request: Request,
                                  item_name: str):
    """
    对商品分类进行评估
    """
    graph: CompiledStateGraph = request.app.state.hts_graph
    config = {"configurable": {"thread_id": str(uuid.uuid4()), "is_for_evaluation": True, "evaluate_version": str(uuid.uuid4())}}
    stream = graph.astream({"item": item_name}, config, stream_mode="updates", subgraphs=True)
    result = ""
    async for step in stream:
        result += str(step) + "\n"
    return result


@evaluation_router.post("/batch_hts_classify")
async def batch_hts_classify_evaluation(request: Request, evaluate_version: str, evaluate_count: int = 100):
    await do_batch_hts_classify_evaluation(request, evaluate_version, evaluate_count)
    return "success"

@evaluation_router.get("/hts_classify_result")
async def hts_classify_evaluation_result(evaluate_version: str):
    """
    获取商品分类评估结果
    """
    return await get_hts_classify_evaluation_result(evaluate_version)
