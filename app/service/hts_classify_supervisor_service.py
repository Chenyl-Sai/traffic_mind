"""
HTS分类监督者服务
"""
from app.db.session import AsyncSessionLocal
from app.repo.hts_classify_cache_repo import select_e2e_cache


class HtsClassifySupervisorService:

    def __init__(self):
        pass

    async def get_e2e_exact_cache(self, item: str):
        # 获取精确缓存
        async with AsyncSessionLocal() as session:
            cache = await select_e2e_cache(session, item)
            if cache:
                return {
                    "hit_e2e_exact_cache": True,
                    "final_rate_line_code": cache.rate_line_code,
                    "final_description": cache.final_output_reason
                }
        return {
            "hit_e2e_exact_cache": False,
        }