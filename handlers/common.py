# -*- coding: utf-8 -*-
"""Bosh menyu, /start, /help va umumiy yordamchilar."""
from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext

from db import repo
from keyboards import inline as ikb
from keyboards import reply as kb
from keyboards.inline import CB_NOOP
from services.render import esc

router = Router(name="common")

# Bu router guruhlarda ham ishlaydigan yagona message handler (/id) ni
# saqlaydi, shuning uchun filtr router darajasida emas — har handlerda.
PRIVATE = F.chat.type == "private"

HELP_TEXT = (
    "📖 <b>Botdan foydalanish</b>\n\n"
    "1️⃣ <b>📋 Bron</b> → aptekani qidiring va tanlang\n"
    "2️⃣ Dorilarni tanlab, har biriga miqdor kiriting\n"
    "3️⃣ <b>🛒 Hisoblash</b> → spesifikatsiyani ko'ring\n"
    "4️⃣ <b>✅ Tasdiqlash</b> → Excel sizga keladi, bron guruhga tushadi\n\n"
    "🆘 Muammo bo'lsa administratorga murojaat qiling."
)


@router.message(CommandStart(), PRIVATE)
async def start(message: types.Message, state: FSMContext, user, has_panel: bool):
    await state.clear()
    await message.answer(
        f"👋 Assalomu alaykum, <b>{user['full_name']}</b>!\n\nBo'limni tanlang:",
        parse_mode="HTML",
        reply_markup=kb.main_menu(has_panel),
    )


@router.message(Command("admin"), PRIVATE)
@router.message(F.text == kb.BTN_ADMIN, PRIVATE)
async def panel(message: types.Message, state: FSMContext, user, has_panel: bool):
    """Panel: adminga to'liq, buxgalterga aptekalar bo'limi."""
    if not has_panel:
        return await message.answer("❌ Sizda panelga kirish huquqi yo'q.")
    await state.clear()
    await message.answer("🛠 Panel:", reply_markup=kb.admin_menu(user["role"]))


@router.message(Command("help"), PRIVATE)
@router.message(F.text == kb.BTN_HELP, PRIVATE)
async def help_handler(message: types.Message):
    await message.answer(HELP_TEXT, parse_mode="HTML")


@router.message(F.text == kb.BTN_MAIN_MENU, PRIVATE)
async def main_menu(message: types.Message, state: FSMContext, has_panel: bool):
    await state.clear()
    await message.answer("👋 Bo'limni tanlang:", reply_markup=kb.main_menu(has_panel))


@router.message(Command("id"))
async def whoami(message: types.Message, user):
    # Ataylab guruhlarda ham ishlaydi: yangi guruh ochilganda uning
    # chat ID sini bilishning eng oson yo'li. Menyuda ko'rinmaydi.
    await message.answer(
        f"🆔 Sizning ID: <code>{message.from_user.id}</code>\n"
        f"👤 {user['full_name']}  |  Rol: <b>{user['role']}</b>\n"
        f"💬 Bu chat ID: <code>{message.chat.id}</code>",
        parse_mode="HTML",
    )


@router.callback_query(F.data == CB_NOOP)
async def noop(callback: types.CallbackQuery):
    """Faqat ko'rsatish uchun qo'yilgan tugmalar."""
    await callback.answer()


# Eng oxirgi handler: bu routerdan keyin hech narsa yo'q.
# Shuning uchun bu fayldagi barcha handlerlardan KEYIN turishi shart.
@router.message(PRIVATE, F.text)
async def fallback_search(message: types.Message, company, has_panel: bool):
    """Hech bir handlerga tushmagan matnni apteka qidiruvi deb qabul qiladi.

    Ilgari bunday matn hech qayerga tushmasdi va bot umuman javob
    bermasdi — foydalanuvchiga «qidiruv ishlamayapti» bo'lib ko'rinardi.
    Buning eng ko'p uchraydigan sababi: FSM holati xotirada saqlanadi,
    bot qayta ishga tushganda (deploy, server reboot) «📋 Bron» bosilgani
    unutiladi va menejer yozgan apteka nomi holatsiz kelib qoladi.

    Endi holat bor-yo'qligidan qat'i nazar qidiriladi.
    """
    query = (message.text or "").strip()
    if len(query) < 2:
        return await message.answer(
            "👋 Bo'limni tanlang:", reply_markup=kb.main_menu(has_panel)
        )

    rows = await repo.search_pharmacies(company["id"], query, limit=20)
    rows = [r for r in rows if r["contract_id"]]  # shartnomasiz bron qilib bo'lmaydi
    if not rows:
        return await message.answer(
            f"❓ <b>{esc(query)}</b> bo'yicha apteka topilmadi.\n\n"
            f"Apteka nomini, INN yoki shartnoma raqamini yozing "
            f"(masalan <code>S1/70/03</code>).",
            reply_markup=kb.main_menu(has_panel),
        )

    await message.answer(
        f"🔎 <b>{len(rows)} ta natija</b> — kerakligini tanlang:",
        reply_markup=ikb.pharmacy_results(rows),
    )
