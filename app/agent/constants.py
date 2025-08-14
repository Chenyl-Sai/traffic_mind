from enum import Enum

class HtsAgents(Enum):
    SUPERVISOR = ("supervisor", "监视器", "顶层Agent，负责调度各个Agent")
    REWRITE_ITEM = ("rewrite_item", "商品重写", "负责商品信息的补充与扩写")
    RETRIEVE_DOCUMENTS = ("retrieve_documents", "文档检索", "根据语义相似度，查找与重写商品相近的Chapter、Heading、Subheading、RateLine信息")
    DETERMINE_CHAPTER = ("determine_chapter", "确定章节", "根据检索到的相关章节说明文档和重写后的商品信息，由LLM决定所属章节")
    DETERMINE_HEADING = ("determine_heading", "确定类目", "根据检索到的相关章节说明文档和重写后的商品信息，由LLM决定所属类目")
    DETERMINE_SUBHEADING = ("determine_subheading", "确定子目", "根据检索到的相关章节说明文档和重写后的商品信息，由LLM决定所属子母")
    DETERMINE_RATE_LINE = ("determine_rate_line", "确定RateLine", "根据检索到的相关章节说明文档和重写后的商品信息，由LLM决定所属RateLine")
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


class RewriteItemNodes(str, Enum):
    ENTER_REWRITE_ITEM = "enter_rewrite_item"
    GET_REWRITE_ITEM_FROM_CACHE = "get_rewrite_item_from_cache"
    GET_LLM_REWRITE_ITEM_RESPONSE = "get_llm_rewrite_item_response"
    REWRITE_ITEM = "rewrite_item"
    SAVE_EXACT_REWRITE_CACHE = "save_exact_rewrite_cache"
    SAVE_SIMIL_REWRITE_CACHE = "save_simil_rewrite_cache"

class RetrieveDocumentsNodes(str, Enum):
    ENTER_RETRIEVE_DOCUMENTS = "enter_retrieve_documents"
    RETRIEVE_DOCUMENTS = "retrieve_documents"
    SAVE_RETRIEVE_RESULT_FOR_EVALUATION = "save_retrieve_result_for_evaluation"

class DetermineChapterNodes(str, Enum):
    ENTER_DETERMINE_CHAPTER = "enter_determine_chapter"
    ASK_LLM_TO_DETERMINE_CHAPTER = "ask_llm_to_determine_chapter"
    DETERMINE_CHAPTER = "determine_chapter"

class DetermineHeadingNodes(str, Enum):
    ENTER_DETERMINE_HEADING = "enter_determine_heading"
    ASK_LLM_TO_DETERMINE_HEADING = "ask_llm_to_determine_heading"
    DETERMINE_HEADING = "determine_heading"

class DetermineSubheadingNodes(str, Enum):
    ENTER_DETERMINE_SUBHEADING = "enter_determine_subheading"
    ASK_LLM_TO_DETERMINE_SUBHEADING = "ask_llm_to_determine_subheading"
    DETERMINE_SUBHEADING = "determine_subheading"

class DetermineRateLineNodes(str, Enum):
    ENTER_DETERMINE_RATE_LINE = "enter_determine_rate_line"
    ASK_LLM_TO_DETERMINE_RATE_LINE = "ask_llm_to_determine_rate_line"
    DETERMINE_RATE_LINE = "determine_rate_line"

class GenerateFinalOutputNodes(str, Enum):
    ENTER_GENERATE_FINAL_OUTPUT = "enter_generate_final_output"
    ASK_LLM_TO_GENERATE_FINAL_OUTPUT = "ask_llm_to_generate_final_output"
    # GENERATE_FINAL_OUTPUT = "generate_final_output"