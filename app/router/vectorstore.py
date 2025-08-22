from fastapi import APIRouter

from app.dep.llm import VectorStoreDep

vector_store_router = APIRouter()


@vector_store_router.get("/search_related_chapters")
async def search_related_chapters(vector_store: VectorStoreDep,
                                  query_text: str, k: int = 5):
    return await vector_store.search(query_text=query_text, filter={"type": "chapter"}, k=k, fetch_k=20)


@vector_store_router.get("/search_related_headings")
async def search_related_headings(vector_store: VectorStoreDep,
                                  query_text: str, k: int = 5):
    return await vector_store.search(query_text=query_text, filter={"type": "heading"}, k=k, fetch_k=20)