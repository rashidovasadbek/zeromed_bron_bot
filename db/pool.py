# -*- coding: utf-8 -*-
"""asyncpg pool — butun bot uchun bitta.

farm_botda pool va alohida connect() aralash ishlatilardi (api.py har
so'rovda yangi ulanish ochardi). Bu yerda faqat pool bor.
"""
import asyncpg

from config import Settings

_pool: asyncpg.Pool | None = None


async def init_pool(settings: Settings) -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            **settings.db_config,
            min_size=1,
            max_size=10,
            command_timeout=30,
        )
    return _pool


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Pool hali ochilmagan — avval init_pool() chaqiring")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
