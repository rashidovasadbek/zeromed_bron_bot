# -*- coding: utf-8 -*-
"""Kirish nazorati.

farm_botda kim bo'lsa ham /start bosib buyurtma qila olardi — bu yerda
faqat app_user jadvalidagi faol xodimlar. Har handlerda tekshirish o'rniga
bitta middleware: topilgan xodim `user` nomi bilan handlerga uzatiladi.
"""
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineQuery, Message, TelegramObject

from db import repo

logger = logging.getLogger(__name__)

DENY_TEXT = (
    "⛔️ Sizda bu botdan foydalanish huquqi yo'q.\n\n"
    "Ruxsat olish uchun administratorga murojaat qiling va "
    "quyidagi ID raqamingizni yuboring:\n"
    "<code>{user_id}</code>"
)

BLOCKED_TEXT = "🚫 Hisobingiz vaqtincha bloklangan. Administratorga murojaat qiling."


class AuthMiddleware(BaseMiddleware):
    def __init__(self, bootstrap_admin_id: int | None = None):
        self.bootstrap_admin_id = bootstrap_admin_id
        self._bootstrap_done = False

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return None

        user = await repo.get_user(tg_user.id)

        # Birinchi ishga tushirish: bazada admin yo'q bo'lsa, .env dagi
        # BOOTSTRAP_ADMIN_ID admin qilib yoziladi. Bir marta tekshiriladi.
        if user is None and not self._bootstrap_done and self.bootstrap_admin_id:
            if tg_user.id == self.bootstrap_admin_id:
                created = await repo.ensure_bootstrap_admin(
                    tg_user.id, tg_user.full_name or "Bosh admin"
                )
                self._bootstrap_done = True
                if created:
                    logger.info("Bosh admin yaratildi: %s", tg_user.id)
                    user = await repo.get_user(tg_user.id)

        if user is None:
            return await self._deny(event, DENY_TEXT.format(user_id=tg_user.id))
        if not user["active"]:
            return await self._deny(event, BLOCKED_TEXT)

        role = user["role"]
        data["user"] = user
        data["is_admin"] = role == "admin"
        data["can_pay"] = role in ("admin", "buxgalter")
        data["can_manage_pharmacy"] = role in ("admin", "buxgalter")
        # Bosh menyuda «⚙️ Panel» tugmasi ko'rinadimi
        data["has_panel"] = role in ("admin", "buxgalter")
        return await handler(event, data)

    @staticmethod
    async def _deny(event: TelegramObject, text: str) -> None:
        """Rad javobi. Guruhda jim qolamiz — begonalarga javob bermaymiz."""
        try:
            if isinstance(event, CallbackQuery):
                await event.answer(
                    text.replace("<code>", "").replace("</code>", ""), show_alert=True
                )
            elif isinstance(event, Message):
                if event.chat.type == "private":
                    await event.answer(text, parse_mode="HTML")
            elif isinstance(event, InlineQuery):
                await event.answer([], cache_time=1, is_personal=True)
        except Exception as e:  # noqa: BLE001 — rad javobi hech qachon botni yiqitmasin
            logger.warning("Rad javobini yuborib bo'lmadi: %s", e)
        return None
