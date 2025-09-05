import logging
import uuid
import pandas as pd
import asyncio

from fastapi import Request
from langgraph.graph.state import CompiledStateGraph

from app.core.constants import IndexName
from app.core.opensearch import get_async_opensearch_client

logger = logging.getLogger(__name__)


async def run_ignore_output(input: dict, graph, config):
    async for step in graph.astream(input, config, stream_mode="updates", subgraphs=True):
        pass


async def do_batch_hts_classify_evaluation(request: Request, evaluate_version: str, evaluate_count: int):
    graph: CompiledStateGraph = request.app.state.hts_graph
    df = pd.read_csv("app/data/evaluate_processed.tsv", sep="\t", dtype=str)
    tasks = []
    evaluate_batch_size = 10
    count = 0
    for row in df.itertuples():
        item = row.item_en
        hscode = row.hscode
        config = {"configurable": {"thread_id": str(uuid.uuid4()), "is_for_evaluation": True,
                                   "evaluate_version": evaluate_version, "hscode": hscode}}
        tasks.append(run_ignore_output({"item": item}, graph, config))
        count += 1
        if count % evaluate_batch_size == 0:
            await asyncio.gather(*tasks)
            tasks = []
        if count == evaluate_count:
            break
    if tasks:
        await asyncio.gather(*tasks)


async def get_hts_classify_evaluation_result(evaluate_version: str):
    """
    获取商品分类评估结果
    """
    results = await asyncio.gather(get_heading_document_recall_rate(evaluate_version),
                                   get_determine_heading_accuracy_rate(evaluate_version),
                                   get_determine_subheading_accuracy_rate(evaluate_version))
    (heading_document_total, heading_document_hit, heading_document_recall_rate), \
        (determine_heading_total, determine_heading_hit, determine_heading_accuracy), \
        (determine_subheading_total, determine_subheading_hit, determine_subheading_accuracy) = results
    return {
        "heading_document_total": heading_document_total,
        "heading_document_hit": heading_document_hit,
        "heading_document_recall_rate": heading_document_recall_rate,
        "determine_heading_total": determine_heading_total,
        "determine_heading_hit": determine_heading_hit,
        "determine_heading_accuracy": determine_heading_accuracy,
        "determine_subheading_total": determine_subheading_total,
        "determine_subheading_hit": determine_subheading_hit,
        "determine_subheading_accuracy": determine_subheading_accuracy
    }

async def get_heading_document_recall_rate(evaluate_version: str):
    async with get_async_opensearch_client() as async_client:
        total_count = 0
        hit_count = 0
        recall_rate = 0
        page_size = 10
        page = 0
        while True:
            response = await async_client.search(index=IndexName.EVALUATE_RETRIEVE_HEADING.value, body={
                "size": page_size,
                "from": page * page_size,
                "query": {
                    "term": {
                        "evaluate_version": {
                            "value": evaluate_version
                        }
                    }
                },
                "sort": [
                    {"_id": "asc"}
                ]
            })
            if response["hits"]["total"]["value"] > 0:
                hits = response["hits"]["hits"]
                for hit in hits:
                    total_count += 1
                    matches = hit["_source"]["matches"]
                    if matches:
                        hit_count += 1

                # 检查是否达到最后一页
                if len(hits) < page_size:
                    break
            else:
                # 一条数据都没有
                break

            page += 1
            # 安全限制，避免意外无限循环
            if page > 1000:
                break

        if total_count > 0:
            recall_rate = hit_count / total_count
    return total_count, hit_count, recall_rate


async def get_determine_heading_accuracy_rate(evaluate_version: str):
    async with get_async_opensearch_client() as async_client:
        total_count = 0
        hit_count = 0
        accuracy_rate = 0
        page_size = 10
        page = 0
        while True:
            response = await async_client.search(index=IndexName.EVALUATE_LLM_CONFIRM_HEADING.value, body={
                "size": page_size,
                "from": page * page_size,
                "query": {
                    "term": {
                        "evaluate_version": {
                            "value": evaluate_version
                        }
                    }
                },
                "sort": [
                    {"_id": "asc"}
                ]
            })
            if response["hits"]["total"]["value"] > 0:
                hits = response["hits"]["hits"]
                for hit in hits:
                    total_count += 1
                    actual_heading = hit["_source"]["actual_heading"]
                    main_heading = hit["_source"]["llm_response"]["main_heading"]
                    alternative_headings = hit["_source"]["llm_response"]["alternative_headings"]
                    all_headings = [main_heading] + (alternative_headings if alternative_headings else [])
                    heading_codes = [heading["heading_code"] for heading in all_headings]
                    if actual_heading in heading_codes:
                        hit_count += 1

                # 检查是否达到最后一页
                if len(hits) < page_size:
                    break
            else:
                # 一条数据都没有
                break

            page += 1
            # 安全限制，避免意外无限循环
            if page > 1000:
                break
        if total_count > 0:
            accuracy_rate = hit_count / total_count
    return total_count, hit_count, accuracy_rate


async def get_determine_subheading_accuracy_rate(evaluate_version: str):
    async with get_async_opensearch_client() as async_client:
        total_count = 0
        hit_count = 0
        accuracy_rate = 0
        page_size = 10
        page = 0
        while True:
            response = await async_client.search(index=IndexName.EVALUATE_LLM_CONFIRM_SUBHEADING.value, body={
                "size": page_size,
                "from": page * page_size,
                "query": {
                    "term": {
                        "evaluate_version": {
                            "value": evaluate_version
                        }
                    }
                },
                "sort": [
                    {"_id": "asc"}
                ]
            })
            if response["hits"]["total"]["value"] > 0:
                hits = response["hits"]["hits"]
                for hit in hits:
                    total_count += 1
                    actual_subheading = hit["_source"]["actual_subheading"]
                    main_subheading = hit["_source"]["llm_response"]["main_subheading"]
                    alternative_subheadings = hit["_source"]["llm_response"]["alternative_subheadings"]
                    all_subheadings = [main_subheading] + (alternative_subheadings if alternative_subheadings else [])
                    subheading_codes = [subheading["subheading_code"] for subheading in all_subheadings]
                    if actual_subheading in subheading_codes:
                        hit_count += 1

                # 检查是否达到最后一页
                if len(hits) < page_size:
                    break
            else:
                # 一条数据都没有
                break

            page += 1
            # 安全限制，避免意外无限循环
            if page > 1000:
                break
        if total_count > 0:
            accuracy_rate = hit_count / total_count
    return total_count, hit_count, accuracy_rate
