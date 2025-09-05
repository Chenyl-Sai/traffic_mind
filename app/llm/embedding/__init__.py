from app.core.constants import DEFAULT_EMBEDDINGS_DIMENSION
from app.llm.embedding.qwen import default_qwen_embeddings
from app.service.embeddings_service import EmbeddingsService

default_embeddings_service = EmbeddingsService(default_qwen_embeddings, "qwen-text-embedding-v4",
                                               DEFAULT_EMBEDDINGS_DIMENSION)
