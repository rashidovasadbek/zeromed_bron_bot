# -*- coding: utf-8 -*-
"""Bron oqimi: apteka → dorilar → hisoblash → tasdiqlash → guruh.

Barcha pul hisobi services/pricing.py da — bu yerda hech qanday
arifmetika yo'q. farm_botda hisob spesifikatsiya va Excel funksiyalarida
alohida-alohida takrorlangan edi.
"""
import logging

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile

from db import repo
from keyboards import inline as ikb
from keyboards import reply as kb
from services.excel import build_spec_excel
from services.pricing import calc_items
from services.render import (
    bron_group_messages, esc, manager_receipt_messages, spec_messages,
)
from states import BronState

logger = logging.getLogger(__name__)

router = Router(name="bron")

MAX_QUANTITY = 1_000_000


# ============================================================
#  YORDAMCHILAR
# ============================================================

async def track(state: FSMContext, message_id: int) -> None:
    """Vaqtinchalik xabar — hisoblashda o'chiriladi."""
    data = await state.get_data()
    ids = data.get("temp_msgs", [])
    ids.append(message_id)
    await state.update_data(temp_msgs=ids)


async def clear_tracked(bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    for msg_id in data.get("temp_msgs", []):
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception:
            pass  # eski xabarni o'chirib bo'lmasligi normal
    await state.update_data(temp_msgs=[])


async def show_drug_menu(bot: Bot, chat_id: int, state: FSMContext) -> None:
    drugs = await repo.get_drugs()
    if not drugs:
        await bot.send_message(
            chat_id,
            "⚠️ Bazada dori yo'q. Administrator dori qo'shishi kerak.",
            reply_markup=kb.cart_actions(),
        )
        return
    sent = await bot.send_message(
        chat_id, "👇 Dori tanlang:", reply_markup=ikb.drugs_list(drugs)
    )
    await track(state, sent.message_id)


# ============================================================
#  APTEKA TANLASH
# ============================================================

@router.message(F.text == kb.BTN_BRON)
async def start_bron(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(BronState.search_pharmacy)
    await message.answer(
        "📋 <b>Aptekani toping</b>\n\n"
        "Apteka nomini, INN yoki shartnoma raqamini yozing.\n"
        "<i>Yoki pastdagi tugma orqali qidiring.</i>",
        reply_markup=kb.cancel(),
    )
    await message.answer("👇", reply_markup=ikb.pharmacy_search_button())


@router.message(BronState.search_pharmacy)
async def search_pharmacy_by_text(message: types.Message, state: FSMContext,
                                  company, has_panel: bool):
    """Matn orqali qidiruv — inline rejim o'chiq bo'lsa ham ishlaydi."""
    # Inline qidiruvdan apteka tanlanganda Telegram chatga tayyor xabar
    # yuboradi (via_bot to'ldirilgan bo'ladi). Uni yangi qidiruv so'rovi
    # deb qabul qilmaymiz — foydalanuvchi xabar tagidagi tugmani bosadi.
    if message.via_bot:
        return

    if message.text in kb.STOP_BUTTONS:
        await state.clear()
        return await message.answer(
            "👋 Bo'limni tanlang:", reply_markup=kb.main_menu(has_panel)
        )

    query = (message.text or "").strip()
    if len(query) < 2:
        return await message.answer("❌ Kamida 2 ta belgi kiriting:")

    rows = await repo.search_pharmacies(company["id"], query, limit=20)
    rows = [r for r in rows if r["contract_id"]]  # shartnomasizlar bron uchun yaroqsiz

    if not rows:
        return await message.answer(
            "❌ Apteka topilmadi. Boshqacha yozib ko'ring "
            "yoki administratordan qo'shishni so'rang:"
        )

    await message.answer(
        f"🔎 <b>{len(rows)} ta natija</b> — kerakligini tanlang:",
        reply_markup=ikb.pharmacy_results(rows),
    )


@router.inline_query()
async def inline_search(query: types.InlineQuery, company):
    rows = await repo.search_pharmacies(company["id"], query.query.strip(), limit=30)

    results = []
    for row in rows:
        # Shartnomasi yo'q apteka bron uchun yaroqsiz — ko'rsatmaymiz
        if not row["contract_id"]:
            continue
        results.append(types.InlineQueryResultArticle(
            id=str(row["id"]),
            title=row["name"],
            description=f"INN: {row['inn']}  |  №{row['contract_no']}  |  {row['region_name']}",
            input_message_content=types.InputTextMessageContent(
                message_text=(
                    f"🏢 <b>{esc(row['name'])}</b>\n"
                    f"📄 Shartnoma №{esc(row['contract_no'])}"
                ),
                parse_mode="HTML",
            ),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
                types.InlineKeyboardButton(
                    text="💊 Dorilarni tanlash",
                    callback_data=f"{ikb.CB_PICK_PHARMACY}{row['id']}",
                )
            ]]),
        ))

    await query.answer(results, cache_time=1, is_personal=True)


@router.callback_query(F.data.startswith(ikb.CB_PICK_PHARMACY))
async def pick_pharmacy(callback: types.CallbackQuery, state: FSMContext, company):
    pharmacy_id = int(callback.data.removeprefix(ikb.CB_PICK_PHARMACY))
    pharmacy = await repo.get_pharmacy(company["id"], pharmacy_id)
    if not pharmacy or not pharmacy["contract_id"]:
        return await callback.answer("⚠️ Apteka yoki shartnoma topilmadi!", show_alert=True)

    await state.clear()
    await state.update_data(pharmacy_id=pharmacy_id)
    await callback.answer()

    # Apteka inline qidiruv orqali guruhda ham tanlanishi mumkin —
    # javobni doim shaxsiy chatga yuboramiz.
    chat_id = callback.from_user.id
    date = pharmacy["contract_date"]
    await callback.bot.send_message(
        chat_id,
        f"🏢 <b>{esc(pharmacy['name'])}</b>\n"
        f"📄 Shartnoma №{esc(pharmacy['contract_no'])}"
        f"  ({date.strftime('%d.%m.%Y') if date else '—'})\n"
        f"📍 {esc(pharmacy['region_name'])}  |  👤 {esc(pharmacy['manager_name'] or '—')}\n\n"
        f"Dorilarni tanlang va miqdorini kiriting:",
        reply_markup=kb.cart_actions(),
    )
    await show_drug_menu(callback.bot, chat_id, state)


# ============================================================
#  SAVAT
# ============================================================

@router.callback_query(F.data.startswith(ikb.CB_ADD_DRUG))
async def ask_quantity(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("pharmacy_id"):
        return await callback.answer("⚠️ Avval aptekani tanlang!", show_alert=True)

    drug_id = int(callback.data.removeprefix(ikb.CB_ADD_DRUG))
    drug = await repo.get_drug(drug_id)
    if not drug or not drug["active"]:
        return await callback.answer("⚠️ Bu dori sotuvda yo'q!", show_alert=True)

    await state.update_data(drug_id=drug_id)
    await state.set_state(BronState.waiting_quantity)
    await track(state, callback.message.message_id)
    await callback.message.edit_text(
        f"💊 <b>{esc(drug['name'])}</b>\n\n🔢 Necha {esc(drug['unit'])} kerak?"
    )
    await callback.answer()


@router.message(BronState.waiting_quantity)
async def save_quantity(message: types.Message, state: FSMContext,
                        company, has_panel: bool):
    text = (message.text or "").strip()

    # Miqdor o'rniga menyu tugmasi bosilsa — o'sha amalni bajaramiz
    if text == kb.BTN_CALC:
        await state.set_state(None)
        return await calculate(message, state, company)
    if text == kb.BTN_RESET:
        await state.set_state(None)
        return await reset_cart(message, state)
    if text == kb.BTN_MAIN_MENU:
        await state.clear()
        return await message.answer(
            "👋 Bo'limni tanlang:", reply_markup=kb.main_menu(has_panel)
        )

    if not text.isdigit() or not 0 < int(text) <= MAX_QUANTITY:
        return await message.answer(
            f"❌ Faqat 1 dan {MAX_QUANTITY:,} gacha butun son kiriting:".replace(",", " ")
        )

    data = await state.get_data()
    total = await repo.cart_add(message.from_user.id, data["drug_id"], int(text))
    await state.set_state(None)
    await track(state, message.message_id)

    drug = await repo.get_drug(data["drug_id"])
    sent = await message.answer(
        f"✅ Savatga qo'shildi: <b>{esc(drug['name'])}</b> — "
        f"{total} {esc(drug['unit'])}",
        reply_markup=kb.cart_actions(),
    )
    await track(state, sent.message_id)
    await show_drug_menu(message.bot, message.chat.id, state)


@router.message(F.text == kb.BTN_RESET)
async def reset_cart(message: types.Message, state: FSMContext):
    await repo.cart_clear(message.from_user.id)
    await message.answer("🔄 Savat tozalandi.", reply_markup=kb.cart_actions())
    await show_drug_menu(message.bot, message.chat.id, state)


@router.message(F.text == kb.BTN_EDIT_CART)
async def edit_cart(message: types.Message, state: FSMContext):
    items = await repo.cart_items(message.from_user.id)
    if not items:
        return await message.answer("⚠️ Savat bo'sh!", reply_markup=kb.cart_actions())

    await message.answer(
        "📝 Savatni tahrirlang yoki yangi dori qo'shing:", reply_markup=kb.cart_actions()
    )
    sent = await message.answer(
        "🗑 O'chirish uchun ❌ bosing:", reply_markup=ikb.cart_edit(items)
    )
    await track(state, sent.message_id)
    await show_drug_menu(message.bot, message.chat.id, state)


@router.callback_query(F.data.startswith(ikb.CB_DEL_ITEM))
async def delete_item(callback: types.CallbackQuery):
    drug_id = int(callback.data.removeprefix(ikb.CB_DEL_ITEM))
    await repo.cart_remove(callback.from_user.id, drug_id)
    items = await repo.cart_items(callback.from_user.id)
    if items:
        await callback.message.edit_reply_markup(reply_markup=ikb.cart_edit(items))
    else:
        await callback.message.edit_text("🗑 Savat bo'shadi.")
    await callback.answer("O'chirildi")


@router.message(F.text == kb.BTN_BACK)
async def back_to_drugs(message: types.Message, state: FSMContext):
    await message.answer("💊 Dorilarni tanlang:", reply_markup=kb.cart_actions())
    await show_drug_menu(message.bot, message.chat.id, state)


# ============================================================
#  HISOBLASH
# ============================================================

@router.message(F.text == kb.BTN_CALC)
async def calculate(message: types.Message, state: FSMContext, company):
    user_id = message.from_user.id
    await clear_tracked(message.bot, message.chat.id, state)

    data = await state.get_data()
    pharmacy_id = data.get("pharmacy_id")
    if not pharmacy_id:
        return await message.answer("⚠️ Apteka tanlanmagan! «📋 Bron» dan boshlang.")

    items = await repo.cart_items(user_id)
    if not items:
        return await message.answer(
            "⚠️ Savat bo'sh! Avval dori qo'shing.", reply_markup=kb.cart_actions()
        )

    pharmacy = await repo.get_pharmacy(company["id"], pharmacy_id)
    if not pharmacy:
        return await message.answer("⚠️ Apteka topilmadi!")

    totals = calc_items(items)
    parts = spec_messages(pharmacy, totals)
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        await message.answer(part, reply_markup=kb.spec_actions() if last else None)

    await state.update_data(calculated=True)


# ============================================================
#  TASDIQLASH
# ============================================================

@router.message(F.text == kb.BTN_CONFIRM)
async def confirm(message: types.Message, state: FSMContext, user, company,
                  has_panel: bool, settings):
    data = await state.get_data()
    if not data.get("pharmacy_id"):
        return await message.answer("⚠️ Apteka tanlanmagan!", reply_markup=kb.main_menu(has_panel))
    if not data.get("calculated"):
        return await message.answer("⚠️ Avval «🛒 Hisoblash» tugmasini bosing.")

    user_id = message.from_user.id
    items = await repo.cart_items(user_id)
    if not items:
        return await message.answer("⚠️ Savat bo'sh!", reply_markup=kb.cart_actions())

    pharmacy = await repo.get_pharmacy(company["id"], data["pharmacy_id"])
    if not pharmacy or not pharmacy["contract_id"]:
        return await message.answer("⚠️ Apteka yoki shartnoma topilmadi!")

    totals = calc_items(items)

    try:
        bron_id = await repo.create_bron(user_id, pharmacy, company["id"], totals)
    except Exception:
        logger.exception("Bron yaratishda xato (user=%s)", user_id)
        return await message.answer(
            "❌ Bronni saqlab bo'lmadi. Administratorga xabar bering.",
            reply_markup=kb.main_menu(has_panel),
        )

    await state.clear()

    # --- Menejerga: Excel + qisqa tasdiq ---
    try:
        excel = build_spec_excel(totals, company, pharmacy)
        filename = _safe_filename(pharmacy["name"], bron_id)
        await message.answer_document(
            BufferedInputFile(excel, filename=filename),
            caption=f"📄 Bron №{bron_id} — spesifikatsiya",
        )
    except Exception:
        logger.exception("Excel yasashda xato (bron=%s)", bron_id)
        await message.answer("⚠️ Excel yasab bo'lmadi, lekin bron saqlandi.")

    parts = manager_receipt_messages(company, pharmacy, totals)
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        await message.answer(part, reply_markup=kb.main_menu(has_panel) if last else None)

    # --- Bron guruhiga ---
    await _send_to_bron_group(
        message.bot, settings.bron_group_id, bron_id, pharmacy, totals,
        manager_name=user["full_name"],
    )


def _safe_filename(pharmacy_name: str, bron_id: int) -> str:
    import re
    safe = re.sub(r'[\\/:*?"<>|]', "", pharmacy_name).strip().replace(" ", "_")
    return f"Bron_{bron_id}_{safe or 'apteka'}.xlsx"


async def _send_to_bron_group(bot: Bot, group_id: int, bron_id: int,
                              pharmacy, totals, manager_name: str) -> None:
    """Guruhga yuborish alohida: xato bo'lsa ham bron bazada qoladi."""
    parts = bron_group_messages(bron_id, pharmacy, totals, manager_name)
    try:
        sent = None
        for i, part in enumerate(parts):
            last = i == len(parts) - 1
            sent = await bot.send_message(
                group_id, part,
                reply_markup=ikb.send_to_pay(bron_id) if last else None,
            )
        if sent:
            await repo.set_bron_group_msg(bron_id, sent.message_id)
        logger.info("Bron %s guruhga yuborildi (%s ta xabar)", bron_id, len(parts))
    except Exception:
        logger.exception("Bron %s ni guruhga yuborib bo'lmadi", bron_id)
