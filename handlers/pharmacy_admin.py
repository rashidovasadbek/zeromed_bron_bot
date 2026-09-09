# -*- coding: utf-8 -*-
"""Admin panel: aptekalar — qo'shish, tahrirlash, ma'lumot.

Viloyat faqat tugmadan tanlanadi. farm_botda u erkin matn edi va
bazada 58 xil yozuv yig'ilgan ("Xorazim", "Termoz", "Namangann",
"JIZZAX"/"Jizzax"/"jIZZAH"), keyin ularni canon_region() tozalab
yurardi. Bu yerda xom matn umuman kiritilmaydi — tozalash kerak emas.
"""
import logging
from datetime import datetime

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile

from db import repo
from filters import CanManagePharmacy
from handlers.admin import stop_flow
from keyboards import inline as ikb
from keyboards import reply as kb
from services.excel import build_pharmacies_excel
from services.render import chunks, esc, pharmacy_block
from states import InfoState, PharmacyState

logger = logging.getLogger(__name__)

# Admin va buxgalter: buxgalter apteka qo'shadi, tahrirlaydi va ko'radi.
# Dori narxlari, xodimlar va rekvizitlar bu routerda emas — ular
# handlers/admin.py da, faqat admin uchun.
router = Router(name="pharmacy_admin")
router.message.filter(CanManagePharmacy())
router.callback_query.filter(CanManagePharmacy())

LIST_LIMIT = 50


# ============================================================
#  🏢 YANGI APTEKA
# ============================================================

@router.message(F.text == kb.BTN_NEW_PHARMACY)
async def new_pharmacy(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(PharmacyState.inn)
    await message.answer("🔢 Apteka INN raqamini kiriting:", reply_markup=kb.cancel())


@router.message(PharmacyState.inn)
async def new_pharmacy_inn(message: types.Message, state: FSMContext, user):
    if await stop_flow(message, state, user["role"]):
        return
    inn = (message.text or "").strip()
    if not inn.isdigit() or not 9 <= len(inn) <= 14:
        return await message.answer(
            "❌ INN 9–14 xonali raqam bo'lishi kerak. Qayta kiriting:"
        )

    # farm_botda bir INN ikki marta kiritilgan holatlar bor — bu yerda
    # taqiqlamaymiz (bir tashkilot bir nechta shartnoma olishi mumkin),
    # lekin admin bilib turishi uchun ogohlantiramiz.
    existing = await repo.find_pharmacies_by_inn(inn)
    await state.update_data(ph_inn=inn)
    await state.set_state(PharmacyState.name)

    warn = ""
    if existing:
        names = "\n".join(f"   • {esc(r['name'])}" for r in existing[:5])
        warn = (
            f"⚠️ <b>Diqqat:</b> bu INN bazada bor:\n{names}\n\n"
            f"Baribir qo'shmoqchi bo'lsangiz davom eting.\n\n"
        )
    await message.answer(
        f"{warn}🏢 Apteka (tashkilot) nomini kiriting:", parse_mode="HTML"
    )


@router.message(PharmacyState.name)
async def new_pharmacy_name(message: types.Message, state: FSMContext, user):
    if await stop_flow(message, state, user["role"]):
        return
    name = (message.text or "").strip()
    if len(name) < 2:
        return await message.answer("❌ Nom juda qisqa. Qayta kiriting:")

    await state.update_data(ph_name=name)
    await state.set_state(PharmacyState.region)
    regions = await repo.get_regions()
    await message.answer("📍 Viloyatni tanlang:", reply_markup=ikb.regions(regions))


@router.callback_query(PharmacyState.region, F.data.startswith(ikb.CB_REGION))
async def new_pharmacy_region(callback: types.CallbackQuery, state: FSMContext):
    region_id = int(callback.data.removeprefix(ikb.CB_REGION))
    region = await repo.get_region(region_id)
    if not region:
        return await callback.answer("Viloyat topilmadi", show_alert=True)

    await state.update_data(ph_region_id=region_id, ph_region_name=region["name"])
    await state.set_state(PharmacyState.manager)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    managers = await repo.list_managers()
    await callback.message.answer(
        f"📍 {esc(region['name'])} ✅\n\n👤 Menejerni tanlang:",
        parse_mode="HTML",
        reply_markup=ikb.managers(managers),
    )
    await callback.answer()


@router.callback_query(PharmacyState.manager, F.data.startswith(ikb.CB_MANAGER))
async def new_pharmacy_manager(callback: types.CallbackQuery, state: FSMContext):
    manager_id = int(callback.data.removeprefix(ikb.CB_MANAGER)) or None
    await state.update_data(ph_manager_id=manager_id)
    await state.set_state(PharmacyState.phone)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(
        "📞 Apteka telefon raqamini kiriting.\n<i>(majburiy emas)</i>",
        parse_mode="HTML",
        reply_markup=kb.cancel_or_skip(),
    )
    await callback.answer()


@router.message(PharmacyState.phone)
async def new_pharmacy_save(message: types.Message, state: FSMContext,
                            company, user):
    if await stop_flow(message, state, user["role"]):
        return
    phone = None if message.text == kb.BTN_SKIP else (message.text or "").strip() or None

    data = await state.get_data()
    try:
        pharmacy_id, contract = await repo.create_pharmacy_with_contract(
            company_id=company["id"],
            name=data["ph_name"],
            inn=data["ph_inn"],
            region_id=data["ph_region_id"],
            manager_user_id=data.get("ph_manager_id"),
            phone=phone,
            account_code=company["account_code"],
        )
    except Exception as e:
        logger.exception("Apteka qo'shishda xato")
        await state.clear()
        return await message.answer(
            f"❌ Bazaga yozib bo'lmadi: {type(e).__name__}: {e}",
            reply_markup=kb.admin_menu(user["role"]),
        )

    await state.clear()
    seq = contract["seq_no"]
    await message.answer(
        f"✅ <b>Apteka qo'shildi!</b>\n\n"
        f"🏢 {esc(data['ph_name'])}\n"
        f"🔢 INN: <code>{esc(data['ph_inn'])}</code>\n"
        f"📍 {esc(data['ph_region_name'])}\n"
        f"📞 {esc(phone) if phone else '—'}\n"
        f"📄 Shartnoma №<b>{esc(contract['contract_no'])}</b>\n"
        f"   <i>(A={seq} / C={esc(contract['account_code'])})</i>\n"
        f"📅 {contract['contract_date'].strftime('%d.%m.%Y')}",
        parse_mode="HTML",
        reply_markup=kb.admin_menu(user["role"]),
    )


# ============================================================
#  📝 APTEKANI TAHRIRLASH
# ============================================================

EDIT_FIELDS = {
    "✏️ Nomi": "name",
    "🔢 INN": "inn",
    "📞 Telefon": "phone",
}
EDIT_LABEL = {"name": "nomini", "inn": "INN raqamini", "phone": "telefon raqamini"}


def edit_field_kb() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="✏️ Nomi"), types.KeyboardButton(text="🔢 INN")],
            [types.KeyboardButton(text="📞 Telefon"), types.KeyboardButton(text="📍 Viloyat")],
            [types.KeyboardButton(text="👤 Menejer"), types.KeyboardButton(text=kb.BTN_CANCEL)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


@router.message(F.text == kb.BTN_EDIT_PHARMACY)
async def edit_pharmacy(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(PharmacyState.edit_search)
    await message.answer(
        "🔍 Apteka nomini, INN yoki shartnoma raqamini kiriting:",
        reply_markup=kb.cancel(),
    )


@router.message(PharmacyState.edit_search)
async def edit_pharmacy_search(message: types.Message, state: FSMContext,
                               company, user):
    if await stop_flow(message, state, user["role"]):
        return
    rows = await repo.search_pharmacies(company["id"], (message.text or "").strip(), limit=1)
    if not rows:
        return await message.answer("❌ Apteka topilmadi. Qayta kiriting:")

    row = rows[0]
    await state.update_data(edit_ph_id=row["id"])
    await state.set_state(PharmacyState.edit_field)
    await message.answer(
        f"{pharmacy_block(row)}\n\n<b>Nimani o'zgartiramiz?</b>",
        parse_mode="HTML",
        reply_markup=edit_field_kb(),
    )


@router.message(PharmacyState.edit_field)
async def edit_pharmacy_field(message: types.Message, state: FSMContext, user):
    if await stop_flow(message, state, user["role"]):
        return
    text = message.text or ""

    if text == "📍 Viloyat":
        regions = await repo.get_regions()
        return await message.answer(
            "📍 Yangi viloyatni tanlang:", reply_markup=ikb.regions(regions)
        )
    if text == "👤 Menejer":
        managers = await repo.list_managers()
        return await message.answer(
            "👤 Yangi menejerni tanlang:", reply_markup=ikb.managers(managers)
        )

    field = EDIT_FIELDS.get(text)
    if not field:
        return await message.answer("Iltimos, tugmadan tanlang!")

    await state.update_data(edit_field=field)
    await state.set_state(PharmacyState.edit_value)
    await message.answer(
        f"Aptekaning yangi {EDIT_LABEL[field]} kiriting:", reply_markup=kb.cancel()
    )


@router.callback_query(PharmacyState.edit_field, F.data.startswith(ikb.CB_REGION))
async def edit_pharmacy_region(callback: types.CallbackQuery, state: FSMContext,
                               company, user):
    region_id = int(callback.data.removeprefix(ikb.CB_REGION))
    data = await state.get_data()
    await repo.update_pharmacy_region(data["edit_ph_id"], region_id)
    await state.clear()
    row = await repo.get_pharmacy(company["id"], data["edit_ph_id"])
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"✅ Viloyat yangilandi!\n\n{pharmacy_block(row)}",
        parse_mode="HTML",
        reply_markup=kb.admin_menu(user["role"]),
    )
    await callback.answer()


@router.callback_query(PharmacyState.edit_field, F.data.startswith(ikb.CB_MANAGER))
async def edit_pharmacy_manager(callback: types.CallbackQuery, state: FSMContext,
                                company, user):
    manager_id = int(callback.data.removeprefix(ikb.CB_MANAGER)) or None
    data = await state.get_data()
    await repo.update_pharmacy_manager(data["edit_ph_id"], manager_id)
    await state.clear()
    row = await repo.get_pharmacy(company["id"], data["edit_ph_id"])
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"✅ Menejer yangilandi!\n\n{pharmacy_block(row)}",
        parse_mode="HTML",
        reply_markup=kb.admin_menu(user["role"]),
    )
    await callback.answer()


@router.message(PharmacyState.edit_value)
async def edit_pharmacy_save(message: types.Message, state: FSMContext,
                             company, user):
    if await stop_flow(message, state, user["role"]):
        return
    data = await state.get_data()
    field = data["edit_field"]
    value = (message.text or "").strip()

    if not value:
        return await message.answer("❌ Bo'sh bo'lishi mumkin emas. Qayta kiriting:")
    if field == "inn" and (not value.isdigit() or not 9 <= len(value) <= 14):
        return await message.answer("❌ INN 9–14 xonali raqam bo'lishi kerak:")

    await repo.update_pharmacy_field(data["edit_ph_id"], field, value)
    await state.clear()
    row = await repo.get_pharmacy(company["id"], data["edit_ph_id"])
    await message.answer(
        f"✅ Yangilandi!\n\n{pharmacy_block(row)}",
        parse_mode="HTML",
        reply_markup=kb.admin_menu(user["role"]),
    )


# ============================================================
#  📑 APTEKA MA'LUMOTI
# ============================================================

@router.message(F.text == kb.BTN_PHARMACY_INFO)
async def pharmacy_info(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📑 <b>Apteka ma'lumoti</b>\n\n"
        "Apteka nomi, INN, telefon, viloyat, shartnoma № va menejeri.",
        parse_mode="HTML",
        reply_markup=ikb.pharmacy_info_menu(),
    )


@router.callback_query(F.data == "info:search")
async def info_search_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(InfoState.search)
    await callback.message.answer(
        "🔍 Apteka nomini (yoki bir qismini) yoxud INN kiriting:",
        reply_markup=kb.cancel(),
    )
    await callback.answer()


@router.message(InfoState.search)
async def info_search(message: types.Message, state: FSMContext, company, user):
    if await stop_flow(message, state, user["role"]):
        return
    rows = await repo.search_pharmacies(company["id"], (message.text or "").strip(), limit=20)
    if not rows:
        return await message.answer("❌ Apteka topilmadi. Qayta kiriting:")

    await state.clear()
    blocks = [pharmacy_block(r) for r in rows]
    if len(rows) > 1:
        blocks[0] = f"🔎 <b>{len(rows)} ta natija:</b>\n\n" + blocks[0]
    await send_chunks(message, blocks, user["role"])


@router.callback_query(F.data == "info:region")
async def info_region_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    counts = await repo.count_pharmacies_by_region()
    if not counts:
        return await callback.answer("Bazada apteka yo'q!", show_alert=True)
    await callback.message.answer(
        "📍 <b>Regionni tanlang:</b>\n<i>Qavs ichida — apteka soni.</i>",
        parse_mode="HTML",
        reply_markup=ikb.regions_with_counts(counts),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(ikb.CB_INFO_REGION))
async def info_region_list(callback: types.CallbackQuery, state: FSMContext,
                           company, user):
    region_id = int(callback.data.removeprefix(ikb.CB_INFO_REGION))
    await state.clear()
    await callback.answer("⏳")

    rows = await repo.list_pharmacies_by_region(company["id"], region_id, limit=200)
    if not rows:
        return await callback.message.answer(
            "❌ Bu regionda apteka yo'q.", reply_markup=kb.admin_menu(user["role"])
        )

    region_name = rows[0]["region_name"]
    shown = rows[:LIST_LIMIT]
    blocks = [pharmacy_block(r) for r in shown]
    blocks[0] = f"📍 <b>{esc(region_name)}</b> — {len(rows)} ta apteka:\n\n" + blocks[0]
    if len(rows) > LIST_LIMIT:
        blocks.append(
            f"<i>Jami {len(rows)} ta, birinchi {LIST_LIMIT} tasi ko'rsatildi. "
            f"To'liq ro'yxat Excelda.</i>"
        )
    await send_chunks(callback.message, blocks, user["role"])


@router.callback_query(F.data == "info:excel")
async def info_excel(callback: types.CallbackQuery, state: FSMContext,
                     company, user):
    await state.clear()
    await callback.answer("⏳ Excel tayyorlanmoqda...")

    rows = await repo.search_pharmacies(company["id"], "", limit=10000)
    if not rows:
        return await callback.message.answer(
            "❌ Bazada apteka yo'q!", reply_markup=kb.admin_menu(user["role"])
        )

    filename = f"aptekalar_{datetime.now().strftime('%d.%m.%Y')}.xlsx"
    await callback.message.answer_document(
        BufferedInputFile(build_pharmacies_excel(rows), filename=filename),
        caption=f"📥 Aptekalar ro'yxati — {len(rows)} ta",
        reply_markup=kb.admin_menu(user["role"]),
    )


async def send_chunks(message: types.Message, blocks: list[str],
                      role: str = "admin") -> None:
    """Uzun ro'yxatni 4096 chegarasiga sig'diradi."""
    parts = chunks(blocks)
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        await message.answer(
            part,
            parse_mode="HTML",
            reply_markup=kb.admin_menu(role) if last else None,
        )
