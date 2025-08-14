from enum import Enum

DEFAULT_EMBEDDINGS_DIMENSION : int = 2048

class IndexName(str, Enum):
    ITEM_REWRITE = "traffic_mind_item_rewrite"
    CHAPTER_CLASSIFY = "traffic_mind_chapter_classify"

    EVALUATE_RETRIEVE_CHAPTER = "evaluate_traffic_mind_retrieve_chapter"
    EVALUATE_LLM_CONFIRM_CHAPTER = "evaluate_traffic_mind_llm_confirm_chapter"