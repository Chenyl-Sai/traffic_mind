from typing import Annotated
from fastapi import Depends

from pymilvus import AsyncMilvusClient
from app.core.constants import MilvusCollectionName
from app.core.milvus import get_knowledge_client, get_cache_client

def get_milvus_client(client_type: str, collection_name: MilvusCollectionName):
    async def __get_client():
        if client_type == "knowledge":
            return await get_knowledge_client(collection_name)
        if client_type == "cache":
            return await get_cache_client(collection_name)
        raise "Invalid client_type params for get_milvus_client method"

    return __get_client


MilvusChapterKnowledgeDep = Annotated[
    AsyncMilvusClient, Depends(get_milvus_client("knowledge", MilvusCollectionName.KNOWLEDGE_CHAPTER))]
MilvusHeadingKnowledgeDep = Annotated[
    AsyncMilvusClient, Depends(get_milvus_client("knowledge", MilvusCollectionName.KNOWLEDGE_HEADING))]
