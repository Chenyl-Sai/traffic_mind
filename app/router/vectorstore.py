from fastapi import APIRouter


from app.dep.llm import VectorStoreDep

vector_store_router = APIRouter()


@vector_store_router.get("/search_related_chapters")
async def search_related_chapters(vector_db: VectorStoreDep,
                                  query_text: str, k: int = 5):
    return vector_db.search(query_text=query_text, filter={"type": "chapter"}, k = k)