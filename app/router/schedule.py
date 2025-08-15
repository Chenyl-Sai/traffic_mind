
from fastapi import APIRouter, BackgroundTasks
from app.dep.db import SessionDep

from app.service import wco_hs_service, hts_service

schedule_router = APIRouter()

@schedule_router.post("/check_wco_hs_update")
async def check_wco_hs_update(session: SessionDep, background_tasks: BackgroundTasks):
    """
    检查WCO HS数据是否有更新
    """
    return await wco_hs_service.check_wco_hs_update(session, background_tasks)

@schedule_router.post("/check_hts_update")
async def check_hts_update(session: SessionDep, background_tasks: BackgroundTasks):
    """
    检查HTS数据是否有更新
    """
    return await hts_service.check_hts_update(session, background_tasks)