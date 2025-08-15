import redis.asyncio

from app.core.config import settings

async_redis: redis.asyncio.Redis | None = None

async def init_async_redis():
    global async_redis
    if async_redis is None:
        async_redis_pool = redis.asyncio.ConnectionPool.from_url(settings.REDIS_CONNECTION_URL)
        async_redis = redis.asyncio.Redis(connection_pool=async_redis_pool)

async def get_async_redis():
    if not async_redis:
        await init_async_redis()
    return async_redis

async def close_async_redis():
    if async_redis:
        await async_redis.close()
        await async_redis.connection_pool.disconnect()