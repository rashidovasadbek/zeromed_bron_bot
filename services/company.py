# -*- coding: utf-8 -*-
"""Kompaniya rekvizitlari keshi.

Rekvizitlar deyarli o'zgarmaydi, lekin har xabar, Excel va guruh xabari
uchun kerak. Har update'da bazaga borish o'rniga bir marta o'qib qo'yamiz;
admin tahrirlaganda invalidate() chaqiriladi.
"""
from db import repo

_cache = None


async def get(code: str):
    global _cache
    if _cache is None:
        _cache = await repo.get_company(code)
        if _cache is None:
            raise RuntimeError(
                f"company jadvalida '{code}' kodli yozuv yo'q — "
                f"migration yugurtirilganmi?"
            )
    return _cache


def invalidate() -> None:
    global _cache
    _cache = None
