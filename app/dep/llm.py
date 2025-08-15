from typing import Annotated
from fastapi import Depends

from app.core.config import settings
from app.service.vector_store_service import FAISSVectorStore
from app.llm.embedding.qwen import default_qwen_embeddings


def get_chapter_vector_store():
    return FAISSVectorStore(index_dir=settings.VECTOR_STORE_INDEX_DIR,
                            index_name=settings.VECTOR_STORE_INDEX_NAME,
                            embeddings=default_qwen_embeddings, dimension=2048)

ChapterVectorStoreDep = Annotated[FAISSVectorStore, Depends(get_chapter_vector_store)]