import asyncio

from sqlalchemy import text

from .db import engine
from .worker import queue


async def bootstrap():
    async with engine.connect() as connection:
        exists = await connection.scalar(text("SELECT to_regclass('public.procrastinate_jobs')"))
    if not exists:
        async with queue.open_async():
            await queue.schema_manager.apply_schema_async()
    print("Durable queue schema ready")


if __name__ == "__main__":
    asyncio.run(bootstrap())
