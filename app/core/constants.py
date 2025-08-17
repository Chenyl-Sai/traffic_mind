from enum import Enum

DEFAULT_EMBEDDINGS_DIMENSION : int = 2048

class IndexName(str, Enum):
    ITEM_REWRITE = "traffic_mind_item_rewrite"
    CHAPTER_CLASSIFY = "traffic_mind_chapter_classify"
    HEADING_CLASSIFY = "traffic_mind_heading_classify"

    EVALUATE_RETRIEVE_CHAPTER = "evaluate_traffic_mind_retrieve_chapter"
    EVALUATE_LLM_CONFIRM_CHAPTER = "evaluate_traffic_mind_llm_confirm_chapter"
    EVALUATE_LLM_CONFIRM_HEADING = "evaluate_traffic_mind_llm_confirm_heading"


class RedisKeyPrefix(str, Enum):
    REWRITTEN_ITEM_EMBEDDINGS = "rewritten_item_embeddings"