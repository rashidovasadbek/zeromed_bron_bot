# -*- coding: utf-8 -*-
"""Inline klaviaturalar.

callback_data prefikslari qat'iy — bir prefiks boshqasining boshi
bo'lmasligi kerak, aks holda startswith() noto'g'ri handlerga tushadi.
farm_botda "select_" juda umumiy edi.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- Prefikslar ---
CB_PICK_PHARMACY = "ph:"      # apteka tanlash (inline qidiruvdan)
CB_ADD_DRUG = "cart:"         # savatga dori qo'shish
CB_DEL_ITEM = "cartdel:"      # savatdan o'chirish
CB_COMPANY_PICK = "co:"       # (kelajakda) kompaniya tanlash
CB_REGION = "reg:"            # viloyat tanlash
CB_MANAGER = "mgr:"           # menejer tanlash
CB_DRUG_EDIT = "drug:"        # dori kartochkasi
CB_DRUG_FIELD = "drugf:"      # dori maydonini tahrirlash
CB_USER = "usr:"              # xodim kartochkasi
CB_REQ_FIELD = "req:"         # rekvizit maydoni
CB_INFO_REGION = "inforeg:"   # region bo'yicha aptekalar
CB_SEND_TO_PAY = "pay:"       # bron guruhidagi to'lov tugmasi
CB_STATS = "stat:"            # statistika davri va eksporti
CB_NOOP = "noop"


def pharmacy_search_button() -> InlineKeyboardMarkup:
    """Inline qidiruvni shu chatda ochadi."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔍 Aptekani qidirish", switch_inline_query_current_chat="")
    ]])


def pharmacy_results(rows) -> InlineKeyboardMarkup:
    """Matnli qidiruv natijalari.

    Inline rejim (@BotFather) o'chiq bo'lsa ham bron qilish ishlashi
    uchun — botni bitta sozlamaga bog'lab qo'ymaymiz.
    """
    b = InlineKeyboardBuilder()
    for r in rows:
        b.row(InlineKeyboardButton(
            text=f"🏢 {r['name']} — №{r['contract_no']}",
            callback_data=f"{CB_PICK_PHARMACY}{r['id']}",
        ))
    return b.as_markup()


def drugs_list(drugs) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for d in drugs:
        b.row(InlineKeyboardButton(text=f"➕ {d['name']}", callback_data=f"{CB_ADD_DRUG}{d['id']}"))
    return b.as_markup()


def cart_edit(items) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for it in items:
        b.row(
            InlineKeyboardButton(
                text=f"📦 {it['name']} — {it['quantity']} {it['unit']}",
                callback_data=CB_NOOP,
            ),
            InlineKeyboardButton(text="❌", callback_data=f"{CB_DEL_ITEM}{it['drug_id']}"),
        )
    return b.as_markup()


def regions(rows, prefix: str = CB_REGION) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for r in rows:
        b.button(text=f"{r['name']} ({r['code']})", callback_data=f"{prefix}{r['id']}")
    b.adjust(2)
    return b.as_markup()


def regions_with_counts(rows) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for r in rows:
        b.button(text=f"{r['name']} ({r['n']})", callback_data=f"{CB_INFO_REGION}{r['id']}")
    b.adjust(2)
    return b.as_markup()


def managers(rows, allow_none: bool = True) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for u in rows:
        b.button(text=u["full_name"], callback_data=f"{CB_MANAGER}{u['id']}")
    b.adjust(2)
    if allow_none:
        b.row(InlineKeyboardButton(text="➖ Biriktirmayman", callback_data=f"{CB_MANAGER}0"))
    return b.as_markup()


def drugs_admin(drugs) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for d in drugs:
        mark = "" if d["active"] else "🚫 "
        b.row(InlineKeyboardButton(
            text=f"{mark}{d['name']} — {int(d['price_no_nds']):,}".replace(",", " "),
            callback_data=f"{CB_DRUG_EDIT}{d['id']}",
        ))
    b.row(InlineKeyboardButton(text="➕ Yangi dori", callback_data=f"{CB_DRUG_EDIT}new"))
    return b.as_markup()


def drug_card(drug) -> InlineKeyboardMarkup:
    did = drug["id"]
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Nomi", callback_data=f"{CB_DRUG_FIELD}name:{did}")
    b.button(text="📏 O'lchov", callback_data=f"{CB_DRUG_FIELD}unit:{did}")
    b.button(text="💰 Narx", callback_data=f"{CB_DRUG_FIELD}price_no_nds:{did}")
    b.button(text="📊 NDS %", callback_data=f"{CB_DRUG_FIELD}nds_rate:{did}")
    b.button(text="📦 Quti sig'imi", callback_data=f"{CB_DRUG_FIELD}box_capacity:{did}")
    b.adjust(2)
    toggle = "🚫 Sotuvdan olish" if drug["active"] else "✅ Sotuvga qaytarish"
    b.row(InlineKeyboardButton(text=toggle, callback_data=f"{CB_DRUG_FIELD}toggle:{did}"))
    b.row(InlineKeyboardButton(text="🔙 Ro'yxatga", callback_data=f"{CB_DRUG_EDIT}list"))
    return b.as_markup()


def users_list(rows) -> InlineKeyboardMarkup:
    role_icon = {"admin": "👑", "buxgalter": "💰", "manager": "👤"}
    b = InlineKeyboardBuilder()
    for u in rows:
        mark = "" if u["active"] else "🚫 "
        icon = role_icon.get(u["role"], "👤")
        b.row(InlineKeyboardButton(
            text=f"{mark}{icon} {u['full_name']}",
            callback_data=f"{CB_USER}card:{u['id']}",
        ))
    b.row(InlineKeyboardButton(text="➕ Yangi xodim", callback_data=f"{CB_USER}new"))
    return b.as_markup()


def user_card(user) -> InlineKeyboardMarkup:
    uid = user["id"]
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text="🎭 Rolni o'zgartirish", callback_data=f"{CB_USER}chrole:{uid}"
    ))
    toggle = "🚫 Bloklash" if user["active"] else "✅ Faollashtirish"
    b.row(InlineKeyboardButton(text=toggle, callback_data=f"{CB_USER}toggle:{uid}"))
    b.row(InlineKeyboardButton(text="🔙 Ro'yxatga", callback_data=f"{CB_USER}list"))
    return b.as_markup()


def role_picker_for(user_id: int, current_role: str) -> InlineKeyboardMarkup:
    """Mavjud xodimning rolini almashtirish. Hozirgi rol ✅ bilan belgilanadi."""
    labels = [("manager", "👤 Menejer"), ("buxgalter", "💰 Buxgalter"), ("admin", "👑 Admin")]
    b = InlineKeyboardBuilder()
    for role, label in labels:
        mark = " ✅" if role == current_role else ""
        b.row(InlineKeyboardButton(
            text=f"{label}{mark}", callback_data=f"{CB_USER}setrole:{role}:{user_id}"
        ))
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"{CB_USER}card:{user_id}"))
    return b.as_markup()


def role_picker() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Menejer", callback_data=f"{CB_USER}role:manager")],
        [InlineKeyboardButton(text="💰 Buxgalter", callback_data=f"{CB_USER}role:buxgalter")],
        [InlineKeyboardButton(text="👑 Admin", callback_data=f"{CB_USER}role:admin")],
    ])


def requisites_edit(company) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏢 Nomi", callback_data=f"{CB_REQ_FIELD}name")
    b.button(text="📍 Manzil", callback_data=f"{CB_REQ_FIELD}address")
    b.button(text="💳 H/r", callback_data=f"{CB_REQ_FIELD}account_no")
    b.button(text="🏦 Bank", callback_data=f"{CB_REQ_FIELD}bank_name")
    b.button(text="🔢 INN", callback_data=f"{CB_REQ_FIELD}inn")
    b.button(text="🏛 MFO", callback_data=f"{CB_REQ_FIELD}mfo")
    b.button(text="👔 Direktor", callback_data=f"{CB_REQ_FIELD}director")
    b.adjust(2)
    return b.as_markup()


def pharmacy_info_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Qidirish", callback_data="info:search")],
        [InlineKeyboardButton(text="📍 Region bo'yicha", callback_data="info:region")],
        [InlineKeyboardButton(text="📥 Excel (hammasi)", callback_data="info:excel")],
    ])


STATS_PERIODS = [
    ("today", "📅 Bugun"),
    ("week", "🗓 Bu hafta"),
    ("month", "📆 Bu oy"),
    ("all", "♾ Hammasi"),
]


def stats_periods(current: str) -> InlineKeyboardMarkup:
    """Davr tugmalari — tanlangani ✅ bilan.

    Excel tugmasi joriy davrni callback_data ichida olib yuradi, shunda
    handler holatni eslab qolishi shart emas.
    """
    b = InlineKeyboardBuilder()
    for code, label in STATS_PERIODS:
        mark = " ✅" if code == current else ""
        b.button(text=f"{label}{mark}", callback_data=f"{CB_STATS}p:{code}")
    b.adjust(2)
    b.row(InlineKeyboardButton(
        text="📥 Excel yuklab olish", callback_data=f"{CB_STATS}x:{current}"
    ))
    return b.as_markup()


def send_to_pay(bron_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="💰 To'lov guruhiga yuborish",
            callback_data=f"{CB_SEND_TO_PAY}{bron_id}",
        )
    ]])
