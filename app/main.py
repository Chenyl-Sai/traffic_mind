from fastapi import FastAPI, Depends

from app.agent.hts_graph import build_hts_classify_graph
from app.core.config import settings
from app.core.handlers import init_exception_handlers
from app.core.opensearch import init_indices
from app.db.session import get_async_session
from app.core.middleware import init_middleware
from app.dep.db import init_db
from contextlib import asynccontextmanager

from app.dep.llm import get_vector_store
from app.init.embeddings_init import build_vector_store
from app.router.agent import agent_router
from app.router.schedule import schedule_router
from app.router.vectorstore import vector_store_router
from app.router.hts import hts_router
import logging
from app.core import logging_config

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("lifespan start")
    # 初始化数据库
    async with await anext(get_async_session()) as session:
        await init_db(session)
        await session.close()
        await build_vector_store(session, get_vector_store())

    # 初始化opensearch索引
    init_indices(app)

    app.state.hts_graph = await build_hts_classify_graph()
    yield
    logger.info("lifespan end")

app = FastAPI(lifespan=lifespan)
init_exception_handlers(app)
init_middleware(app)

@app.get("/hello")
async def say_hello():
    return {"message": "Hello World"}


app.include_router(schedule_router, prefix="/schedule", tags=["schedule"])
app.include_router(vector_store_router, prefix="/vector-store", tags=["vector-store"])
app.include_router(agent_router, prefix="/agent", tags=["agent"])
app.include_router(hts_router, prefix="/hts", tags=["hts"])