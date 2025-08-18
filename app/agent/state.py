from typing import TypedDict, Annotated

from langgraph.graph import MessagesState

from app.schema.llm.llm import SubheadingDetermineResponse, HeadingDetermineResponseDetail, \
    HeadingDetermineResponse, SubheadingDetermineResponseDetail, RateLineDetermineResponse, ItemRewriteResponse, \
    ChapterDetermineResponse


class HtsClassifyAgentState(MessagesState):
    # 用户录入商品信息
    item: str
    # 当前所处的agent
    current_agent: str
    # 下一个agent
    next_agent: str
    # 商品重写
    hit_rewrite_cache: bool
    rewrite_llm_response: ItemRewriteResponse
    rewrite_success: bool
    rewritten_item: dict[str, str]
    # 文档检索
    current_document_type: str
    chapter_documents: list[str]
    heading_documents: str
    subheading_documents: str
    rate_line_documents: str
    # 确定章节
    hit_chapter_cache: bool
    determine_chapter_llm_response: ChapterDetermineResponse
    determine_chapter_success: bool
    determine_chapter_fail_reason: str
    main_chapter: dict
    alternative_chapters: list[dict]
    # 确定类目
    hit_heading_cache: bool
    determine_heading_llm_response: HeadingDetermineResponse
    determine_heading_success: bool
    determine_heading_fail_reason: str
    main_heading: dict
    alternative_headings: list[dict]
    # 确定子目
    hit_subheading_cache: bool
    determine_subheading_llm_response: SubheadingDetermineResponse
    determine_subheading_success: bool
    main_subheading: dict
    alternative_subheadings: list[dict]
    # 确定税率线
    main_rate_line: RateLineDetermineResponse
    es_search_results: list
    evaluation: dict
    final_output: dict
    unexpected_error: BaseException
    unexpected_error_message: str


def state_has_error(state: HtsClassifyAgentState) -> bool:
    return state.get("unexpected_error") is not None
