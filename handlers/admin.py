# -*- coding: utf-8 -*-
"""Admin panel: xodimlar, dorilar, kompaniya rekvizitlari.

Aptekalar bilan ishlash alohida faylda — handlers/pharmacy_admin.py.
Butun router faqat adminlar uchun (IsAdmin filtri router darajasida).
"""
import logging
from decimal import Decimal, InvalidOperation

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from db import repo
from filters import IsAdmin
from keyboards import inline as ikb
from keyboards import reply as kb
from services import company as company_service
from services.render import esc
from states import CompanyState, DrugState, UserState

logger = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ============================================================
#  UMUMIY YORDAMCHILAR
# ============================================================

async def stop_flow(message: types.Message, state: FSMContext,
                    role: str = "admin") -> bool:
    """Bekor qilish tugmalari bosilganini tekshiradi.

    Har FSM handlerining birinchi qatorida chaqiriladi — foydalanuvchi
    istalgan bosqichda chiqib keta olsin.
    """
    if message.text in kb.STOP_BUTTONS:
        await state.clear()
        await message.answer("🛠 Panel:", reply_markup=kb.admin_menu(role))
        return True
    return False


def parse_price(text: str) -> Decimal | None:
    """'45 982,143' / '45982.143' → Decimal. Noto'g'ri bo'lsa None."""
    cleaned = (text or "").replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        value = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    return value if value >= 0 else None


# Panelga kirish handlers/common.py da — u yerga buxgalter ham tushadi.


# ============================================================
#  👤 XODIMLAR
# ============================================================

ROLE_LABEL = {"admin": "👑 Admin", "buxgalter": "💰 Buxgalter", "manager": "👤 Menejer"}


@router.message(F.text == kb.BTN_STAFF)
async def staff_list(message: types.Message, state: FSMContext):
    await state.clear()
    users = await repo.list_users()
    if not users:
        return await message.answer(
            "👤 Hali xodim yo'q.", reply_markup=ikb.users_list([])
        )
    await message.answer(
        f"👤 <b>Xodimlar</b> — {len(users)} ta\n\n"
        f"Tahrirlash uchun ustiga bosing:",
        parse_mode="HTML",
        reply_markup=ikb.users_list(users),
    )


async def render_staff_list(message: types.Message) -> None:
    users = await repo.list_users()
    await message.edit_text(
        f"👤 <b>Xodimlar</b> — {len(users)} ta\n\nTahrirlash uchun ustiga bosing:",
        parse_mode="HTML",
        reply_markup=ikb.users_list(users),
    )


@router.callback_query(F.data == f"{ikb.CB_USER}list")
async def staff_back_to_list(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await render_staff_list(callback.message)
    await callback.answer()


def staff_card_text(u) -> str:
    return (
        f"{ROLE_LABEL.get(u['role'], u['role'])}\n\n"
        f"👤 <b>{esc(u['full_name'])}</b>\n"
        f"🆔 <code>{u['telegram_id']}</code>\n"
        f"📞 {esc(u['phone']) if u['phone'] else '—'}\n"
        f"Holat: {'✅ faol' if u['active'] else '🚫 bloklangan'}"
    )


@router.callback_query(F.data.startswith(f"{ikb.CB_USER}card:"))
async def staff_card(callback: types.CallbackQuery):
    user_id = int(callback.data.split(":")[-1])
    u = await repo.get_user_by_id(user_id)
    if not u:
        return await callback.answer("Xodim topilmadi", show_alert=True)

    await callback.message.edit_text(
        staff_card_text(u), parse_mode="HTML", reply_markup=ikb.user_card(u)
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{ikb.CB_USER}toggle:"))
async def staff_toggle(callback: types.CallbackQuery, user):
    user_id = int(callback.data.split(":")[-1])
    target = await repo.get_user_by_id(user_id)
    if not target:
        return await callback.answer("Xodim topilmadi", show_alert=True)

    # O'zini bloklashdan va oxirgi adminni yo'qotishdan himoya
    if target["telegram_id"] == user["telegram_id"]:
        return await callback.answer("O'zingizni bloklay olmaysiz!", show_alert=True)
    if target["active"] and target["role"] == "admin" and await repo.count_admins() <= 1:
        return await callback.answer(
            "Bu yagona admin — bloklab bo'lmaydi!", show_alert=True
        )

    await repo.set_user_active(user_id, not target["active"])
    await callback.answer("✅ Holat o'zgartirildi")
    await render_staff_list(callback.message)


# --- Rolni o'zgartirish ---

@router.callback_query(F.data.startswith(f"{ikb.CB_USER}chrole:"))
async def staff_role_picker(callback: types.CallbackQuery):
    user_id = int(callback.data.split(":")[-1])
    target = await repo.get_user_by_id(user_id)
    if not target:
        return await callback.answer("Xodim topilmadi", show_alert=True)

    await callback.message.edit_text(
        f"👤 <b>{esc(target['full_name'])}</b>\n"
        f"Hozirgi rol: {ROLE_LABEL.get(target['role'], target['role'])}\n\n"
        f"Yangi rolni tanlang:\n\n"
        f"👑 <b>Admin</b> — hamma narsa: dorilar, aptekalar, xodimlar, "
        f"rekvizitlar, to'lov tasdig'i\n"
        f"💰 <b>Buxgalter</b> — bron qiladi va to'lovni tasdiqlaydi\n"
        f"👤 <b>Menejer</b> — faqat bron qiladi",
        parse_mode="HTML",
        reply_markup=ikb.role_picker_for(user_id, target["role"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{ikb.CB_USER}setrole:"))
async def staff_set_role(callback: types.CallbackQuery, user):
    _, _, role, raw_id = callback.data.split(":")
    user_id = int(raw_id)

    target = await repo.get_user_by_id(user_id)
    if not target:
        return await callback.answer("Xodim topilmadi", show_alert=True)
    if role == target["role"]:
        return await callback.answer("Bu rol allaqachon o'rnatilgan")

    # Oxirgi adminni pastga tushirib, hech kim admin qolmasligining oldini olamiz
    if target["role"] == "admin" and role != "admin" and await repo.count_admins() <= 1:
        return await callback.answer(
            "Bu yagona admin — rolini o'zgartirib bo'lmaydi!", show_alert=True
        )
    if target["telegram_id"] == user["telegram_id"] and role != "admin":
        return await callback.answer(
            "O'z rolingizni pasaytira olmaysiz — boshqa admin bajarsin.", show_alert=True
        )

    await repo.set_user_role(user_id, role)
    updated = await repo.get_user_by_id(user_id)
    await callback.message.edit_text(
        f"✅ Rol o'zgartirildi!\n\n{staff_card_text(updated)}",
        parse_mode="HTML",
        reply_markup=ikb.user_card(updated),
    )
    await callback.answer(f"✅ {ROLE_LABEL.get(role, role)}")


@router.callback_query(F.data == f"{ikb.CB_USER}new")
async def staff_new(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserState.telegram_id)
    await callback.message.answer(
        "🆔 Yangi xodimning <b>Telegram ID</b> raqamini kiriting.\n\n"
        "<i>Xodim botga /start bosganda o'z ID sini ko'radi, "
        "yoki @userinfobot orqali bilib olsa bo'ladi.</i>",
        parse_mode="HTML",
        reply_markup=kb.cancel(),
    )
    await callback.answer()


@router.message(UserState.telegram_id)
async def staff_new_id(message: types.Message, state: FSMContext):
    if await stop_flow(message, state):
        return
    raw = (message.text or "").strip()
    if not raw.lstrip("-").isdigit():
        return await message.answer("❌ ID faqat raqamlardan iborat. Qayta kiriting:")

    tg_id = int(raw)
    existing = await repo.get_user(tg_id)
    if existing:
        await state.clear()
        return await message.answer(
            f"ℹ️ Bu ID allaqachon ro'yxatda:\n"
            f"👤 <b>{esc(existing['full_name'])}</b> — {ROLE_LABEL.get(existing['role'])}\n"
            f"Holat: {'✅ faol' if existing['active'] else '🚫 bloklangan'}",
            parse_mode="HTML",
            reply_markup=kb.admin_menu(),
        )

    await state.update_data(new_tg_id=tg_id)
    await state.set_state(UserState.full_name)
    await message.answer("👤 Xodimning ism-familiyasini kiriting:")


@router.message(UserState.full_name)
async def staff_new_name(message: types.Message, state: FSMContext):
    if await stop_flow(message, state):
        return
    name = (message.text or "").strip()
    if len(name) < 2:
        return await message.answer("❌ Ism juda qisqa. Qayta kiriting:")

    await state.update_data(new_name=name)
    await state.set_state(UserState.role)
    await message.answer("🎭 Rolni tanlang:", reply_markup=ikb.role_picker())


@router.callback_query(UserState.role, F.data.startswith(f"{ikb.CB_USER}role:"))
async def staff_new_role(callback: types.CallbackQuery, state: FSMContext):
    role = callback.data.split(":")[-1]
    if role not in ("admin", "buxgalter", "manager"):
        return await callback.answer("Noma'lum rol", show_alert=True)

    data = await state.get_data()
    tg_id, name = data.get("new_tg_id"), data.get("new_name")
    if not tg_id or not name:
        await state.clear()
        return await callback.answer("Sessiya tugadi, qaytadan boshlang", show_alert=True)

    await repo.add_user(tg_id, name, role)
    await state.clear()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(
        f"✅ Xodim qo'shildi!\n\n"
        f"👤 <b>{esc(name)}</b>\n"
        f"🆔 <code>{tg_id}</code>\n"
        f"🎭 {ROLE_LABEL[role]}\n\n"
        f"<i>Endi u botga /start bosib ishlata oladi.</i>",
        parse_mode="HTML",
        reply_markup=kb.admin_menu(),
    )
    await callback.answer()


# ============================================================
#  💊 DORILAR
# ============================================================

@router.message(F.text == kb.BTN_DRUGS)
async def drugs_list(message: types.Message, state: FSMContext):
    await state.clear()
    drugs = await repo.get_drugs(only_active=False)
    text = (
        f"💊 <b>Dorilar</b> — {len(drugs)} ta\n\nTahrirlash uchun ustiga bosing:"
        if drugs else
        "💊 Hali dori qo'shilmagan."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=ikb.drugs_admin(drugs))


@router.callback_query(F.data == f"{ikb.CB_DRUG_EDIT}list")
async def drugs_back_to_list(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    drugs = await repo.get_drugs(only_active=False)
    await callback.message.edit_text(
        f"💊 <b>Dorilar</b> — {len(drugs)} ta\n\nTahrirlash uchun ustiga bosing:",
        parse_mode="HTML",
        reply_markup=ikb.drugs_admin(drugs),
    )
    await callback.answer()


def drug_card_text(d) -> str:
    cap = f"{d['box_capacity']} ta" if d["box_capacity"] else "belgilanmagan"
    return (
        f"💊 <b>{esc(d['name'])}</b>\n\n"
        f"📏 O'lchov: {esc(d['unit'])}\n"
        f"💰 Narx (NDSsiz): <code>{d['price_no_nds']}</code>\n"
        f"📊 NDS: {d['nds_rate']}%\n"
        f"📦 Quti sig'imi: {cap}\n"
        f"Holat: {'✅ sotuvda' if d['active'] else '🚫 sotuvdan olingan'}"
    )


@router.callback_query(F.data.regexp(rf"^{ikb.CB_DRUG_EDIT}\d+$"))
async def drug_card(callback: types.CallbackQuery):
    drug_id = int(callback.data.removeprefix(ikb.CB_DRUG_EDIT))
    d = await repo.get_drug(drug_id)
    if not d:
        return await callback.answer("Dori topilmadi", show_alert=True)
    await callback.message.edit_text(
        drug_card_text(d), parse_mode="HTML", reply_markup=ikb.drug_card(d)
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{ikb.CB_DRUG_FIELD}toggle:"))
async def drug_toggle(callback: types.CallbackQuery):
    drug_id = int(callback.data.split(":")[-1])
    d = await repo.get_drug(drug_id)
    if not d:
        return await callback.answer("Dori topilmadi", show_alert=True)
    await repo.set_drug_active(drug_id, not d["active"])
    d = await repo.get_drug(drug_id)
    await callback.message.edit_text(
        drug_card_text(d), parse_mode="HTML", reply_markup=ikb.drug_card(d)
    )
    await callback.answer("✅ O'zgartirildi")


FIELD_PROMPT = {
    "name": "✏️ Yangi nomni kiriting:",
    "unit": "📏 O'lchov birligini kiriting (шт, флакон, упак):",
    "price_no_nds": "💰 NDSsiz narxni kiriting (masalan 45982.143):",
    "nds_rate": "📊 NDS stavkasini kiriting (masalan 12):",
    "box_capacity": "📦 Katta qutidagi dona sonini kiriting (0 — o'chirish):",
}


@router.callback_query(F.data.startswith(ikb.CB_DRUG_FIELD))
async def drug_field_prompt(callback: types.CallbackQuery, state: FSMContext):
    _, field, drug_id = callback.data.split(":")
    if field not in FIELD_PROMPT:
        return await callback.answer("Noma'lum maydon", show_alert=True)

    await state.update_data(drug_id=int(drug_id), drug_field=field)
    await state.set_state(DrugState.edit_value)
    await callback.message.answer(FIELD_PROMPT[field], reply_markup=kb.cancel())
    await callback.answer()


@router.message(DrugState.edit_value)
async def drug_field_save(message: types.Message, state: FSMContext):
    if await stop_flow(message, state):
        return
    data = await state.get_data()
    field, drug_id = data.get("drug_field"), data.get("drug_id")
    raw = (message.text or "").strip()

    if field in ("name", "unit"):
        if not raw:
            return await message.answer("❌ Bo'sh bo'lishi mumkin emas. Qayta kiriting:")
        value = raw
    elif field == "price_no_nds":
        value = parse_price(raw)
        if value is None:
            return await message.answer("❌ Narx noto'g'ri. Masalan: 45982.143")
    elif field == "nds_rate":
        if not raw.isdigit():
            return await message.answer("❌ Faqat butun son. Masalan: 12")
        value = int(raw)
    else:  # box_capacity
        if not raw.isdigit():
            return await message.answer("❌ Faqat butun son. 0 — o'chirish uchun.")
        value = int(raw) or None

    await repo.update_drug_field(drug_id, field, value)
    await state.clear()
    d = await repo.get_drug(drug_id)
    await message.answer("✅ Yangilandi!", reply_markup=kb.admin_menu())
    await message.answer(drug_card_text(d), parse_mode="HTML", reply_markup=ikb.drug_card(d))


# --- Yangi dori qo'shish ---

@router.callback_query(F.data == f"{ikb.CB_DRUG_EDIT}new")
async def drug_new(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(DrugState.name)
    await callback.message.answer("💊 Dori nomini kiriting:", reply_markup=kb.cancel())
    await callback.answer()


@router.message(DrugState.name)
async def drug_new_name(message: types.Message, state: FSMContext):
    if await stop_flow(message, state):
        return
    name = (message.text or "").strip()
    if not name:
        return await message.answer("❌ Nom bo'sh. Qayta kiriting:")
    await state.update_data(d_name=name)
    await state.set_state(DrugState.unit)
    await message.answer("📏 O'lchov birligini kiriting (шт, флакон, упак):")


@router.message(DrugState.unit)
async def drug_new_unit(message: types.Message, state: FSMContext):
    if await stop_flow(message, state):
        return
    await state.update_data(d_unit=(message.text or "").strip() or "шт")
    await state.set_state(DrugState.price)
    await message.answer("💰 NDSsiz narxni kiriting (masalan 45982.143):")


@router.message(DrugState.price)
async def drug_new_price(message: types.Message, state: FSMContext):
    if await stop_flow(message, state):
        return
    price = parse_price(message.text or "")
    if price is None:
        return await message.answer("❌ Narx noto'g'ri. Masalan: 45982.143")
    await state.update_data(d_price=str(price))
    await state.set_state(DrugState.nds_rate)
    await message.answer("📊 NDS stavkasi (odatda 12):")


@router.message(DrugState.nds_rate)
async def drug_new_nds(message: types.Message, state: FSMContext):
    if await stop_flow(message, state):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        return await message.answer("❌ Faqat butun son. Masalan: 12")
    await state.update_data(d_nds=int(raw))
    await state.set_state(DrugState.box_capacity)
    await message.answer(
        "📦 Katta qutida nechta dona bor?\n<i>(bilmasangiz yoki kerak bo'lmasa — 0)</i>",
        parse_mode="HTML",
    )


@router.message(DrugState.box_capacity)
async def drug_new_save(message: types.Message, state: FSMContext):
    if await stop_flow(message, state):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        return await message.answer("❌ Faqat butun son. 0 — quti yo'q.")

    data = await state.get_data()
    drug = await repo.add_drug(
        name=data["d_name"],
        unit=data["d_unit"],
        price_no_nds=Decimal(data["d_price"]),
        nds_rate=data["d_nds"],
        box_capacity=int(raw) or None,
    )
    await state.clear()
    await message.answer("✅ Dori qo'shildi!", reply_markup=kb.admin_menu())
    await message.answer(drug_card_text(drug), parse_mode="HTML", reply_markup=ikb.drug_card(drug))


# ============================================================
#  🏦 REKVIZITLAR
# ============================================================

REQ_LABEL = {
    "name": "🏢 Nomi",
    "address": "📍 Manzil",
    "account_no": "💳 H/r",
    "bank_name": "🏦 Bank",
    "inn": "🔢 INN",
    "mfo": "🏛 MFO",
    "director": "👔 Direktor",
}


def requisites_text(c) -> str:
    return (
        f"🏦 <b>Kompaniya rekvizitlari</b>\n\n"
        f"🏢 {esc(c['name'])}\n"
        f"📍 {esc(c['address']) if c['address'] else '❗️ <i>kiritilmagan</i>'}\n"
        f"💳 H/r: <code>{esc(c['account_no'] or '—')}</code>\n"
        f"🏦 Bank: {esc(c['bank_name'] or '—')}\n"
        f"🔢 INN: <code>{esc(c['inn'] or '—')}</code>\n"
        f"🏛 MFO: <code>{esc(c['mfo'] or '—')}</code>\n"
        f"👔 Direktor: {esc(c['director'] or '—')}\n\n"
        f"📄 Shartnoma raqami formati: <code>A/{esc(c['account_code'])}</code>\n"
        f"<i>A — tartib raqami, "
        f"{esc(c['account_code'])} — shu yo'nalishning sho't kodi</i>\n\n"
        f"O'zgartirish uchun maydonni tanlang:"
    )


@router.message(F.text == kb.BTN_REQUISITES)
async def requisites(message: types.Message, state: FSMContext, company):
    await state.clear()
    await message.answer(
        requisites_text(company), parse_mode="HTML",
        reply_markup=ikb.requisites_edit(company),
    )


@router.callback_query(F.data.startswith(ikb.CB_REQ_FIELD))
async def requisites_prompt(callback: types.CallbackQuery, state: FSMContext):
    field = callback.data.removeprefix(ikb.CB_REQ_FIELD)
    if field not in REQ_LABEL:
        return await callback.answer("Noma'lum maydon", show_alert=True)

    await state.update_data(req_field=field)
    await state.set_state(CompanyState.edit_value)
    await callback.message.answer(
        f"{REQ_LABEL[field]} — yangi qiymatni kiriting:", reply_markup=kb.cancel()
    )
    await callback.answer()


@router.message(CompanyState.edit_value)
async def requisites_save(message: types.Message, state: FSMContext, company):
    if await stop_flow(message, state):
        return
    data = await state.get_data()
    field = data.get("req_field")
    value = (message.text or "").strip()
    if not value:
        return await message.answer("❌ Bo'sh bo'lishi mumkin emas. Qayta kiriting:")

    await repo.update_company_field(company["id"], field, value)
    company_service.invalidate()  # keshdagi eski nusxa ishlatilmasin
    await state.clear()
    updated = await repo.get_company(company["code"])
    await message.answer("✅ Rekvizit yangilandi!", reply_markup=kb.admin_menu())
    await message.answer(
        requisites_text(updated), parse_mode="HTML",
        reply_markup=ikb.requisites_edit(updated),
    )
