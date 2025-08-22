import os
import faiss
from langchain_community.docstore import InMemoryDocstore
from langchain_community.vectorstores import FAISS


class FAISSVectorStore:
    def __init__(self, index_dir: str, index_name: str, embeddings, dimension: int = 768):
        self.index_dir = index_dir
        self.index_name = index_name
        self.dimension = dimension
        self.embeddings = embeddings
        self.index = self._initialize_index()

    def _initialize_index(self) -> FAISS:
        """初始化或加载FAISS索引"""
        faiss_file_path = os.path.join(self.index_dir, f'{self.index_name}.faiss')
        if os.path.exists(faiss_file_path):
            print(f"Loading existing index from {self.index_dir}")
            return FAISS.load_local(folder_path=self.index_dir,
                                    index_name=self.index_name,
                                    embeddings=self.embeddings,
                                    allow_dangerous_deserialization=True)
        else:
            print(f"Creating new index at {self.index_dir}")
            os.makedirs(self.index_dir, exist_ok=True)
            # 创建空的 FAISS 索引
            index = faiss.IndexFlatL2(self.dimension)
            # 创建空的 vectorstore
            return FAISS(embedding_function=self.embeddings, index=index, docstore=InMemoryDocstore(),
                         index_to_docstore_id={})
            # return FAISS.from_documents([], self.embeddings)

    def save_index(self):
        """保存索引到文件"""
        self.index.save_local(self.index_dir, self.index_name)
        print(f"Index saved to {self.index_dir}")

    async def add_texts(self, texts, metadatas):
        """添加向量到索引"""
        await self.index.aadd_texts(texts=texts, metadatas=metadatas)

    async def search(self, query_text, filter, search_type="similarity", k=5, fetch_k=20):
        """搜索相似向量"""
        if search_type == "similarity":
            return await self.index.asimilarity_search(query=query_text, k=k, fetch_k=fetch_k, filter=filter)
        elif search_type == "mmr":
            return await self.index.amax_marginal_relevance_search(query=query_text, k=k, fetch_k=fetch_k,
                                                                   filter=filter)
        else:
            raise ValueError(f"Invalid search type: {search_type}")
