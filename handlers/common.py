# -*- coding: utf-8 -*-
"""Bosh menyu, /start, /help va umumiy yordamchilar."""
from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext

from keyboards import reply as kb
from keyboards.inline import CB_NOOP

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
