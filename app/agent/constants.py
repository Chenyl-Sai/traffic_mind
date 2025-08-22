from enum import Enum


class HtsAgents(Enum):
    SUPERVISOR = ("supervisor", "监视器", "顶层Agent，负责调度各个Agent")
    REWRITE_ITEM = ("rewrite_item", "商品重写", "负责商品信息的补充与扩写")
    RETRIEVE_DOCUMENTS = (
    "retrieve_documents", "文档检索", "根据语义相似度，查找与重写商品相近的Chapter、Heading、Subheading、RateLine信息")
    DETERMINE_CHAPTER = (
    "determine_chapter", "确定章节", "根据检索到的相关章节说明文档和重写后的商品信息，由LLM决定所属章节")
    DETERMINE_HEADING = (
    "determine_heading", "确定类目", "根据检索到的相关章节说明文档和重写后的商品信息，由LLM决定所属类目")
    DETERMINE_SUBHEADING = (
    "determine_subheading", "确定子目", "根据检索到的相关章节说明文档和重写后的商品信息，由LLM决定所属子母")
    DETERMINE_RATE_LINE = (
    "determine_rate_line", "确定RateLine", "根据检索到的相关章节说明文档和重写后的商品信息，由LLM决定所属RateLine")
    GENERATE_FINAL_OUTPUT = ("generate_final_output", "生成最终输出", "根据所有历史消息，由LLM总结生成最终的输出")

    def __init__(self, code, name, description):
        self._code = code
        self._name = name
        self._description = description

    @property
    def code(self):
        return self._code

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return self._description

    # 字符串转枚举
    @classmethod
    def str_to_enum(cls, code_str):
        for member in HtsAgents:
            if member.code == code_str:  # 按枚举名匹配
                return member
        raise ValueError(f"Invalid enum code: {code_str}")


class DocumentTypes(Enum):
    CHAPTER = ("chapter", "章节")
    HEADING = ("heading", "类目")
    SUBHEADING = ("subheading", "子目")
    RATE_LINE = ("rate_line", "税率线")

    def __init__(self, code, name):
        self._code = code
        self._name = name

    @property
    def code(self):
        return self._code

    @property
    def name(self):
        return self._name


class SupervisorNodes(str, Enum):
    GET_FROM_CACHE = "get_from_cache"
    AGENT_ROUTER = "agent_router"


class RewriteItemNodes(str, Enum):
    ENTER_REWRITE_ITEM = "enter_rewrite_item"
    GET_REWRITE_ITEM_FROM_CACHE = "get_rewrite_item_from_cache"
    USE_LLM_TO_REWRITE_ITEM = "use_llm_to_rewrite_item"
    PROCESS_LLM_RESPONSE = "process_llm_response"
    SAVE_EXACT_REWRITE_CACHE = "save_exact_rewrite_cache"
    SAVE_SIMIL_REWRITE_CACHE = "save_simil_rewrite_cache"
    GET_SIMIL_E2E_CACHE = "get_simil_e2e_cache"


class RetrieveDocumentsNodes(str, Enum):
    ENTER_RETRIEVE_DOCUMENTS = "enter_retrieve_documents"
    RETRIEVE_DOCUMENTS = "retrieve_documents"
    SAVE_RETRIEVE_RESULT_FOR_EVALUATION = "save_retrieve_result_for_evaluation"


class DetermineChapterNodes(str, Enum):
    ENTER_DETERMINE_CHAPTER = "enter_determine_chapter"
    GET_CHAPTER_FROM_CACHE = "get_chapter_from_cache"
    USE_LLM_TO_DETERMINE_CHAPTER = "use_llm_to_determine_chapter"
    PROCESS_LLM_RESPONSE = "process_llm_response"
    SAVE_LLM_RESPONSE_FOR_EVALUATION = "save_llm_response_for_evaluation"
    SAVE_EXACT_CHAPTER_CACHE = "save_exact_chapter_cache"
    SAVE_SIMIL_CHAPTER_CACHE = "save_simil_chapter_cache"


class DetermineHeadingNodes(str, Enum):
    ENTER_DETERMINE_HEADING = "enter_determine_heading"
    GET_HEADING_FROM_CACHE = "get_heading_from_cache"
    ASK_LLM_TO_DETERMINE_HEADING = "ask_llm_to_determine_heading"
    PROCESS_LLM_RESPONSE = "process_llm_response"
    SAVE_LLM_RESPONSE_FOR_EVALUATION = "save_llm_response_for_evaluation"
    SAVE_LAYERED_HEADING_CACHE = "save_layered_heading_cache"


class DetermineSubheadingNodes(str, Enum):
    ENTER_DETERMINE_SUBHEADING = "enter_determine_subheading"
    GET_SUBHEADING_FROM_CACHE = "get_subheading_from_cache"
    ASK_LLM_TO_DETERMINE_SUBHEADING = "ask_llm_to_determine_subheading"
    PROCESS_LLM_RESPONSE = "process_llm_response"
    SAVE_LLM_RESPONSE_FOR_EVALUATION = "save_llm_response_for_evaluation"
    SAVE_LAYERED_SUBHEADING_CACHE = "save_layered_subheading_cache"


class DetermineRateLineNodes(str, Enum):
    ENTER_DETERMINE_RATE_LINE = "enter_determine_rate_line"
    GET_RATE_LINE_FROM_CACHE = "get_rate_line_from_cache"
    ASK_LLM_TO_DETERMINE_RATE_LINE = "ask_llm_to_determine_rate_line"
    PROCESS_LLM_RESPONSE = "process_llm_response"
    SAVE_LLM_RESPONSE_FOR_EVALUATION = "save_llm_response_for_evaluation"
    SAVE_LAYERED_RATE_LINE_CACHE = "save_layered_rate_line_cache"


class GenerateFinalOutputNodes(str, Enum):
    ENTER_GENERATE_FINAL_OUTPUT = "enter_generate_final_output"
    ASK_LLM_TO_GENERATE_FINAL_OUTPUT = "ask_llm_to_generate_final_output"
    PROCESS_LLM_RESPONSE = "process_llm_response"
    SAVE_EXACT_E2E_CACHE = "save_exact_e2e_cache"
    SAVE_SIMIL_E2E_CACHE = "save_simil_e2e_cache"
