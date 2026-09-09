# -*- coding: utf-8 -*-
"""Reply (pastdagi) klaviaturalar.

Tugma matnlari konstanta sifatida — handlerlar F.text == BTN_... deb
solishtiradi. farm_botda matnlar handler ichida qo'lda yozilgan edi va
bittasini o'zgartirsa boshqasi ishlamay qolardi.
"""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

# --- Bosh menyu ---
BTN_BRON = "📋 Bron"
BTN_HELP = "❓ Yordam"
BTN_ADMIN = "⚙️ Panel"

# --- Bron oqimi ---
BTN_CALC = "🛒 Hisoblash"
BTN_RESET = "🔄 Qayta boshlash"
BTN_MAIN_MENU = "🔙 Bosh menyu"
BTN_CONFIRM = "✅ Tasdiqlash"
BTN_EDIT_CART = "📝 O'zgartirish"
BTN_BACK = "🔙 Orqaga"

# --- Admin panel ---
BTN_DRUGS = "💊 Dorilar"
BTN_NEW_PHARMACY = "🏢 Yangi apteka"
BTN_EDIT_PHARMACY = "📝 Aptekani tahrirlash"
BTN_PHARMACY_INFO = "📑 Apteka ma'lumoti"
BTN_STAFF = "👤 Xodimlar"
BTN_REQUISITES = "🏦 Rekvizitlar"
BTN_STATS = "📊 Statistika"

# --- Umumiy ---
BTN_CANCEL = "🔙 Bekor qilish"
BTN_SKIP = "⏭ O'tkazib yuborish"

# Har qanday FSM oqimini to'xtatadigan tugmalar
STOP_BUTTONS = {BTN_CANCEL, BTN_MAIN_MENU}


def _kb(rows: list[list[str]], placeholder: str | None = None) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t) for t in row] for row in rows],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=placeholder,
    )


def main_menu(show_panel: bool) -> ReplyKeyboardMarkup:
    rows = [[BTN_BRON], [BTN_HELP]]
    if show_panel:
        rows.append([BTN_ADMIN])
    return _kb(rows, "Tanlang...")


def admin_menu(role: str = "admin") -> ReplyKeyboardMarkup:
    """Panel tugmalari rolga qarab.

    Buxgalter aptekalar bilan to'liq ishlaydi, lekin dori narxlari,
    xodimlar, rekvizitlar va statistika faqat adminda qoladi.
    """
    rows = [
        [BTN_NEW_PHARMACY, BTN_EDIT_PHARMACY],
        [BTN_PHARMACY_INFO],
    ]
    if role == "admin":
        rows.insert(0, [BTN_DRUGS, BTN_STATS])
        rows.append([BTN_STAFF, BTN_REQUISITES])
    rows.append([BTN_MAIN_MENU])
    return _kb(rows)


def cancel() -> ReplyKeyboardMarkup:
    return _kb([[BTN_CANCEL]])


def cancel_or_skip() -> ReplyKeyboardMarkup:
    return _kb([[BTN_SKIP], [BTN_CANCEL]])


def cart_actions() -> ReplyKeyboardMarkup:
    return _kb([[BTN_CALC, BTN_RESET], [BTN_MAIN_MENU]])


def spec_actions() -> ReplyKeyboardMarkup:
    return _kb([[BTN_CONFIRM, BTN_EDIT_CART], [BTN_BACK]])
