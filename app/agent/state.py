from typing import TypedDict, Annotated

from langgraph.graph import MessagesState

from app.agent.constants import DocumentTypes
from app.schema.llm.llm import SubheadingDetermineResponse, HeadingDetermineResponse, RateLineDetermineResponse, \
    ItemRewriteResponse, GenerateFinalOutputResponse

class OutputMessage(TypedDict):
    type: str
    message: str


class HtsClassifyAgentState(MessagesState):
    # 用户录入商品信息
    item: str

    # 输出message信息：
    current_output_message: OutputMessage

    # supervisor
    hit_e2e_exact_cache: bool
    hit_e2e_simil_cache: bool
    current_agent: str
    # 商品重写
    hit_rewrite_cache: bool
    rewrite_llm_response: ItemRewriteResponse
    rewrite_success: bool
    rewritten_item: dict[str, str]
    # 文档检索
    current_document_type: DocumentTypes
    heading_documents: str
    subheading_documents: str
    rate_line_documents: str
    # 确定类目
    hit_heading_cache: bool
    determine_heading_llm_response: HeadingDetermineResponse
    determine_heading_success: bool
    determine_heading_fail_reason: str
    candidate_heading_codes: dict[str, list]
    alternative_headings: list[dict]
    # 确定子目
    hit_subheading_cache: bool
    determine_subheading_llm_response: SubheadingDetermineResponse
    determine_subheading_success: bool
    candidate_subheading_codes: dict[str, list]
    main_subheading: dict
    alternative_subheadings: list[dict]
    # 确定税率线
    hit_rate_line_cache: bool
    determine_rate_line_llm_response: RateLineDetermineResponse
    determine_rate_line_success: bool
    candidate_rate_line_codes: dict[str, list]
    main_rate_line: dict
    # 最终输出
    final_output_llm_response: GenerateFinalOutputResponse
    final_rate_line_code: str
    final_description: str

    # 异常处理
    unexpected_error: BaseException
    unexpected_error_message: str


def state_has_error(state: HtsClassifyAgentState) -> bool:
    return state.get("unexpected_error") is not None
