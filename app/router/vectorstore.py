from fastapi import APIRouter

from app.dep.llm import ChapterVectorStoreDep

vector_store_router = APIRouter()


@vector_store_router.get("/search_related_chapters")
async def search_related_chapters(chapter_vector_store: ChapterVectorStoreDep,
                                  query_text: str, k: int = 5):
    return await chapter_vector_store.search(query_text=query_text, filter={"type": "chapter"}, k=k)
