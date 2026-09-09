# -*- coding: utf-8 -*-
"""Bron guruhidagi «To'lov guruhiga yuborish» tugmasi.

farm_botda bu tugmani guruhdagi istalgan odam bosa olardi. Bu yerda
faqat admin va buxgalter — CanPay filtri orqali.
"""
import logging

from aiogram import F, Router, types

from db import repo
from filters import CanPay
from keyboards.inline import CB_SEND_TO_PAY
from services.pricing import stored_items
from services.render import oplata_group_messages

logger = logging.getLogger(__name__)

router = Router(name="groups")


def _bron_id(callback: types.CallbackQuery) -> int | None:
    try:
        return int(callback.data.removeprefix(CB_SEND_TO_PAY))
    except ValueError:
        return None


@router.callback_query(CanPay(), F.data.startswith(CB_SEND_TO_PAY))
async def send_to_oplata(callback: types.CallbackQuery, user, settings):
    bron_id = _bron_id(callback)
    if bron_id is None:
        return await callback.answer("⚠️ Bron raqami noto'g'ri!", show_alert=True)

    bron = await repo.get_bron(bron_id)
    if not bron:
        return await callback.answer("⚠️ Bron bazadan topilmadi!", show_alert=True)

    # Statusni WHERE ichida almashtiramiz: ikki kishi bir vaqtda bossa
    # ham faqat bittasi o'tadi, xabar ikki marta ketmaydi.
    claimed = await repo.mark_sent_to_pay(bron_id, user["telegram_id"])
    if not claimed:
        await _drop_button(callback)
        return await callback.answer(
            "🚫 Bu bron allaqachon to'lov guruhiga yuborilgan!", show_alert=True
        )

    items = await repo.get_bron_items(bron_id)
    totals = stored_items(items)

    try:
        for part in oplata_group_messages(bron, totals):
            await callback.bot.send_message(settings.oplata_group_id, part)
    except Exception:
        logger.exception("Bron %s ni oplata guruhiga yuborib bo'lmadi", bron_id)
        # Statusni orqaga qaytaramiz — qayta urinish mumkin bo'lsin
        await repo.revert_sent_to_pay(bron_id)
        return await callback.answer(
            "❌ To'lov guruhiga yuborib bo'lmadi. Qaytadan urinib ko'ring.",
            show_alert=True,
        )

    await _drop_button(callback)
    logger.info("Bron %s oplata guruhiga yuborildi (%s)", bron_id, user["full_name"])
    await callback.answer("✅ To'lov guruhiga yuborildi!")


@router.callback_query(F.data.startswith(CB_SEND_TO_PAY))
async def send_to_oplata_denied(callback: types.CallbackQuery, user):
    """CanPay o'tmagan holat — tugma jim qolmasin."""
    await callback.answer(
        "⛔️ Bu tugma faqat admin va buxgalter uchun.\n"
        f"Sizning rolingiz: {user['role']}",
        show_alert=True,
    )


async def _drop_button(callback: types.CallbackQuery) -> None:
    """Tugmani olib tashlaydi — qayta bosilmasin."""
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception as e:  # noqa: BLE001 — tugma qolib ketsa ham zarari yo'q
        logger.warning("Tugmani olib tashlab bo'lmadi: %s", e)
