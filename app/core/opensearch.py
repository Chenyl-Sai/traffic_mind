import logging
from typing import AsyncGenerator, Generator

from opensearchpy import AsyncOpenSearch, OpenSearch

from app.core.config import settings
from app.core.constants import IndexName, DEFAULT_EMBEDDINGS_DIMENSION

logger = logging.getLogger(__name__)


def get_async_client() -> AsyncOpenSearch:
    return AsyncOpenSearch(hosts=settings.OPEN_SEARCH_HOSTS,
                           http_auth=(settings.OPEN_SEARCH_USERNAME, settings.OPEN_SEARCH_PASSWORD),
                           use_ssl=True,
                           verify_certs=False)


def get_sync_client() -> OpenSearch:
    return OpenSearch(hosts=settings.OPEN_SEARCH_HOSTS,
                      http_auth=(settings.OPEN_SEARCH_USERNAME, settings.OPEN_SEARCH_PASSWORD),
                      use_ssl=True,
                      verify_certs=False)


def init_indices(app):
    init_item_rewrite_index()
    init_evaluate_retrieve_chapter_index()
    init_chapter_classify_result_index()


rewritten_item_body = {
    "properties": {
        "name": {"type": "text"},
        "cn_name": {"type": "text"},
        "en_name": {"type": "text"},
        "classification_name": {"type": "keyword"},
        "brand": {"type": "keyword"},
        "materials": {"type": "text"},
        "purpose": {"type": "text"},
        "specifications": {"type": "text"},
        "processing_state": {"type": "keyword"},
        "special_properties": {"type": "text"},
        "other_notes": {"type": "text"},
    }
}


def init_item_rewrite_index():
    """
    初始化重写商品索引
    """
    index_name = IndexName.ITEM_REWRITE.value
    with get_sync_client() as sync_client:
        if sync_client.indices.exists(index=index_name):
            logger.info(f"OpenSearch索引{index_name}已存在")
        else:
            body = {
                "settings": {
                    "index": {
                        "number_of_shards": 1,
                        "number_of_replicas": 1,
                        "knn": True
                    }
                },
                "mappings": {
                    "properties": {
                        "origin_item_name": {
                            "type": "keyword",
                        },
                        "origin_item_ch_name": {
                            "type": "text",
                            "analyzer": "ik_smart"
                        },
                        "origin_item_ch_name_vector": {
                            "type": "knn_vector",
                            "dimension": DEFAULT_EMBEDDINGS_DIMENSION,
                            "space_type": "cosinesimil",
                        },
                        "origin_item_en_name": {
                            "type": "text",
                            "analyzer": "standard"
                        },
                        "origin_item_en_name_vector": {
                            "type": "knn_vector",
                            "dimension": DEFAULT_EMBEDDINGS_DIMENSION,
                            "space_type": "cosinesimil",
                        },
                        "rewritten_item": rewritten_item_body,
                        "user_id": {
                            "type": "keyword"
                        },
                        "thread_id": {
                            "type": "keyword"
                        },
                        "created_at": {
                            "type": "date"
                        }
                    }
                }
            }
            sync_client.indices.create(index=index_name, body=body)
            logger.info(f"OpenSearch索引{index_name}创建成功")


def init_evaluate_retrieve_chapter_index():
    """
    初始化用于评估章节检索是否准确的索引
    """
    index_name = IndexName.EVALUATE_RETRIEVE_CHAPTER.value
    with get_sync_client() as sync_client:
        if sync_client.indices.exists(index=index_name):
            logger.info(f"OpenSearch索引{index_name}已存在")
        else:
            body = {
                "settings": {
                    "index": {
                        "number_of_shards": 1,
                        "number_of_replicas": 1,
                    }
                },
                "mappings": {
                    "properties": {
                        "evaluate_version": {
                            "type": "keyword",
                        },
                        "origin_item_name": {
                            "type": "keyword",
                        },
                        "rewritten_item": rewritten_item_body,
                        "chapter_documents": {
                            "properties": {
                                "chapter_title": {"type": "text"},
                                "includes": {"type": "text"},
                                "common_examples": {"type": "text"},
                                "chapter_code": {"type": "text"},
                            }
                        },
                        "created_at": {
                            "type": "date"
                        }
                    }
                }
            }
            sync_client.indices.create(index=index_name, body=body)
            logger.info(f"OpenSearch索引{index_name}创建成功")


def init_chapter_classify_result_index():
    """
    初始化商品章节分类结果索引
    """
    index_name = IndexName.CHAPTER_CLASSIFY.value
    with get_sync_client() as sync_client:
        if sync_client.indices.exists(index=index_name):
            logger.info(f"OpenSearch索引{index_name}已存在")
        else:
            chapter = {
                "properties": {
                    "chapter_code": {"type": "keyword"},
                    "chapter_title": {"type": "text"},
                    "reason": {"type": "text"},
                    "confidence_score": {"type": "text"},
                }
            }
            body = {
                "settings": {
                    "index": {
                        "number_of_shards": 1,
                        "number_of_replicas": 1,
                        "knn": True
                    }
                },
                "mappings": {
                    "properties": {
                        "origin_item_name": {
                            "type": "keyword",
                        },
                        "rewritten_item": rewritten_item_body,
                        "rewritten_item_vector": {
                            "type": "knn_vector",
                            "dimension": DEFAULT_EMBEDDINGS_DIMENSION,
                            "space_type": "cosinesimil",
                        },
                        "main_chapter": chapter,
                        "alternative_chapters": chapter,
                        "created_at": {
                            "type": "date"
                        }
                    }
                }
            }
            sync_client.indices.create(index=index_name, body=body)
            logger.info(f"OpenSearch索引{index_name}创建成功")
