# -*- coding: utf-8 -*-
"""Kompaniyani har handlerga uzatuvchi middleware."""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from services import company as company_service


class CompanyMiddleware(BaseMiddleware):
    def __init__(self, company_code: str):
        self.company_code = company_code

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["company"] = await company_service.get(self.company_code)
        return await handler(event, data)
