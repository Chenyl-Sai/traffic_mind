from langchain.embeddings.base import Embeddings
from typing import List
import dashscope

from app.core.config import settings
from app.core import constants


class QwenEmbeddings(Embeddings):
    def __init__(self, api_key: str, model_name: str = "text-embedding-v4", dimension: int = 1024):
        dashscope.api_key = api_key
        self.model_name = model_name
        self.dimension = dimension

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量生成文本的 Embeddings"""
        embeddings = []
        group_size = 10
        grouped_texts = [texts[i:i + group_size] for i in range(0, len(texts), group_size)]
        for grouped in grouped_texts:
            resp = dashscope.TextEmbedding.call(
                model=self.model_name,
                input=grouped,
                dimension=self.dimension
            )
            if resp.status_code == 200:
                for output_embedding in resp.output["embeddings"]:
                    embeddings.append(output_embedding["embedding"])
            else:
                raise ValueError(f"Embedding 请求失败: {resp.message}")
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """生成单个查询文本的 Embedding"""
        resp = dashscope.TextEmbedding.call(
            model=self.model_name,
            input=text,
            dimension=self.dimension
        )
        if resp.status_code == 200:
            return resp.output["embeddings"][0]["embedding"]
        else:
            raise ValueError(f"Embedding 请求失败: {resp.message}")


default_qwen_embeddings = QwenEmbeddings(api_key=settings.DASHSCOPE_API_KEY,
                                         dimension=constants.DEFAULT_EMBEDDINGS_DIMENSION)
