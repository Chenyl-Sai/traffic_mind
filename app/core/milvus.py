"""
milvus向量搜索数据库相关
1. 后台的chapter、heading等相对静态的数据索引搜索
2. 用户查询hts的各个阶段(针对商品rewrite结果的)缓存存储及搜索
3. ...
"""
import logging

from pymilvus import AsyncMilvusClient, utility, DataType, Function, FunctionType
from pymilvus.client.types import LoadState

from app.core.config import settings
from app.core.constants import DEFAULT_EMBEDDINGS_DIMENSION, MilvusCollectionName

logger = logging.getLogger(__name__)

__async_milvus_client: AsyncMilvusClient | None = None


async def init_milvus_client():
    # 初始化静态知识数据索引
    await create_chapter_knowledge_collection()
    await create_heading_knowledge_collection()
    # 初始化用户动态数据索引


def create_embedding_function(function_name: str, input_field_names: list[str], output_field_names: list[str]):
    return Function(
        name=function_name,
        function_type=FunctionType.TEXTEMBEDDING,
        input_field_names=input_field_names,
        output_field_names=output_field_names,
        params={  # Provider-specific embedding parameters
            "provider": "dashscope",
            "model_name": "text-embedding-v4",
            # Optional parameters:
            "dim": DEFAULT_EMBEDDINGS_DIMENSION,
        }
    )


async def create_chapter_knowledge_collection():
    knowledge_client = get_async_milvus_client()
    # 是否存在collection了
    if not await utility.has_collection(MilvusCollectionName.KNOWLEDGE_CHAPTER.value):
        # Create schema
        schema = knowledge_client.create_schema(
            auto_id=True,
            enable_dynamic_field=True,
        )
        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
        schema.add_field(field_name="chapter_code", datatype=DataType.VARCHAR, max_length=10)
        schema.add_field(field_name="chapter_title", datatype=DataType.VARCHAR, max_length=2000)
        schema.add_field(field_name="section_code", datatype=DataType.VARCHAR, max_length=10)
        schema.add_field(field_name="includes", datatype=DataType.ARRAY, element_type=DataType.VARCHAR,
                         max_length=65535, max_capacity=1000)
        schema.add_field(field_name="common_examples", datatype=DataType.ARRAY, element_type=DataType.VARCHAR,
                         max_length=65535, max_capacity=1000)
        schema.add_field(field_name="content_vector", datatype=DataType.FLOAT_VECTOR, dim=DEFAULT_EMBEDDINGS_DIMENSION)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)

        schema.add_function(
            create_embedding_function(function_name="chapter_content_embedding", input_field_names=["content"],
                                      output_field_names=["content_vector"]))

        # Create Index
        index_params = knowledge_client.prepare_index_params()
        index_params.add_index(field_name="content_vector", index_name="idx_vector", index_type="AUTOINDEX",
                               metric_type="COSINE")

        await knowledge_client.create_collection(
            collection_name=MilvusCollectionName.KNOWLEDGE_CHAPTER.value,
            schema=schema,
            index_params=index_params
        )

        if utility.has_collection(MilvusCollectionName.KNOWLEDGE_CHAPTER.value):
            logger.info(f"Milvus索引{MilvusCollectionName.KNOWLEDGE_CHAPTER.value}创建成功")
        else:
            logger.info(f"Milvus索引{MilvusCollectionName.KNOWLEDGE_CHAPTER.value}创建失败")


async def create_heading_knowledge_collection():
    knowledge_client = get_async_milvus_client()
    # 是否存在collection了
    if not await utility.has_collection(MilvusCollectionName.KNOWLEDGE_HEADING.value):
        # Create schema
        schema = knowledge_client.create_schema(
            auto_id=True,
            enable_dynamic_field=True,
        )
        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
        schema.add_field(field_name="heading_code", datatype=DataType.VARCHAR, max_length=10)
        schema.add_field(field_name="heading_title", datatype=DataType.VARCHAR, max_length=2000)
        schema.add_field(field_name="chapter_code", datatype=DataType.VARCHAR, max_length=10)
        schema.add_field(field_name="title_vector", datatype=DataType.FLOAT_VECTOR, dim=DEFAULT_EMBEDDINGS_DIMENSION)

        schema.add_function(
            create_embedding_function(function_name="heading_title_embedding", input_field_names=["heading_title"],
                                      output_field_names=["title_vector"]))

        # Create Index
        index_params = knowledge_client.prepare_index_params()
        index_params.add_index(field_name="title_vector", index_name="idx_vector", index_type="AUTOINDEX",
                               metric_type="COSINE")

        await knowledge_client.create_collection(
            collection_name=MilvusCollectionName.KNOWLEDGE_HEADING.value,
            schema=schema,
            index_params=index_params
        )
        if utility.has_collection(MilvusCollectionName.KNOWLEDGE_HEADING.value):
            logger.info(f"Milvus索引{MilvusCollectionName.KNOWLEDGE_HEADING.value}创建成功")
        else:
            logger.info(f"Milvus索引{MilvusCollectionName.KNOWLEDGE_HEADING.value}创建失败")


def get_async_milvus_client():
    global __async_milvus_client
    if __async_milvus_client is None:
        __async_milvus_client = AsyncMilvusClient(uri=settings.MILVUS_URI, alias="default")
    return __async_milvus_client


async def get_knowledge_client(collection_name: MilvusCollectionName):
    knowledge_client = get_async_milvus_client()
    load_state = await knowledge_client.get_load_state(collection_name.value)
    if load_state not in [LoadState.Loading, LoadState.Loaded]:
        await knowledge_client.load_collection(collection_name=collection_name.value)
    return knowledge_client


async def load_knowledge_collection(client: AsyncMilvusClient, collection_name: MilvusCollectionName):
    load_state = await client.get_load_state(collection_name.value)
    if load_state not in [LoadState.Loading, LoadState.Loaded]:
        await client.load_collection(collection_name=collection_name.value)


async def get_cache_client(collection_name: MilvusCollectionName):
    cache_client = get_async_milvus_client()
    load_state = await cache_client.get_load_state(collection_name.value)
    if load_state not in [LoadState.Loading, LoadState.Loaded]:
        await cache_client.load_collection(collection_name=collection_name.value)
    yield cache_client
    await cache_client.release_collection(collection_name=collection_name.value)
