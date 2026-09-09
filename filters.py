# -*- coding: utf-8 -*-
"""Maxsus filtrlar.

AuthMiddleware outer middleware sifatida ishlagani uchun `is_admin` /
`can_pay` filtrlar chaqirilishidan oldin `data` ga tushib bo'ladi va
aiogram ularni filtr argumenti sifatida uzatadi.
"""
from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject, is_admin: bool = False) -> bool:
        return is_admin


class CanPay(BaseFilter):
    """Admin yoki buxgalter — to'lovni tasdiqlash huquqi."""

    async def __call__(self, event: TelegramObject, can_pay: bool = False) -> bool:
        return can_pay


class CanManagePharmacy(BaseFilter):
    """Admin yoki buxgalter — apteka qo'shish va tahrirlash huquqi.

    Dorilar (narx), xodimlar va rekvizitlar bunga kirmaydi — ular
    faqat adminda qoladi.
    """

    async def __call__(self, event: TelegramObject,
                       can_manage_pharmacy: bool = False) -> bool:
        return can_manage_pharmacy
