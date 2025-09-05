import json
from typing_extensions import Annotated

from fastapi import APIRouter, Body

from app.dep.db import SessionDep
from app.service import hts_service

hts_router = APIRouter()

@hts_router.post("/get_rate_lines_by_wco_subheadings")
async def get_rate_lines_by_wco_subheadings(subheading_codes: Annotated[list[str], Body()]):
    return json.dumps(await hts_service.get_rate_lines_by_wco_subheadings(subheading_codes), ensure_ascii=False)