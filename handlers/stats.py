# -*- coding: utf-8 -*-
"""Admin panel: 📊 Statistika.

Hisobot butunlay SQL agregatlaridan yig'iladi — bronlar Pythonga
qatorma-qator tortilmaydi. Davr chegarasi Toshkent vaqtida hisoblanadi
(db/repo.period_start), shuning uchun "bugun" server qaysi zonada
turishidan qat'i nazar bir xil kunni bildiradi.

Butun router faqat adminlar uchun: buxgalter ham bu bo'limni ko'rmaydi.
"""
import logging
from decimal import Decimal

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile

from db import repo
from filters import IsAdmin
from keyboards import inline as ikb
from keyboards import reply as kb
from services.excel import build_stats_excel
from services.pricing import fmt_qty, fmt_sum
from services.render import SHORT_LINE, esc

logger = logging.getLogger(__name__)

router = Router(name="stats")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

DEFAULT_PERIOD = "month"
PERIOD_LABEL = {
    "today": "Bugun",
    "week": "Bu hafta",
    "month": "Bu oy",
    "all": "Butun davr",
}
STATUS_LABEL = {
    "new": "🆕 Yangi",
    "sent_to_pay": "💰 To'lovga yuborilgan",
    "paid": "✅ To'langan",
    "cancelled": "❌ Bekor qilingan",
}
TOP_LIMIT = 10          # xabardagi TOP ro'yxatlar uzunligi
EXPORT_DRUGS = 500      # Excel "Dorilar" varag'i uchun — amalda hammasi
NAME_LIMIT = 32         # uzun apteka/dori nomlari xabarni cho'zib yubormasin


def _cut(value, limit: int = NAME_LIMIT) -> str:
    text = str(value or "")
    return esc(text if len(text) <= limit else text[: limit - 1] + "…")


# ============================================================
#  HISOBOT MATNI
# ============================================================

async def build_report(company_id: int, period: str) -> str:
    since, since_label = await repo.period_start(period)

    totals = await repo.stats_totals(company_id, since)
    brons = totals["brons"]

    header = f"📊 <b>Statistika</b> — {PERIOD_LABEL.get(period, period)}"
    if since_label:
        header += f"\n🗓 {since_label} dan buyon"

    if not brons:
        return f"{header}\n{SHORT_LINE}\n\n📭 Bu davrda bron qilinmagan."

    average = Decimal(totals["total"]) / brons
    blocks = [
        f"{header}\n{SHORT_LINE}\n"
        f"📋 Bronlar: <b>{fmt_qty(brons)}</b> ta\n"
        f"💰 Summa: <b><code>{fmt_sum(totals['total'])}</code> so'm</b>\n"
        f"🏢 Aptekalar: {fmt_qty(totals['pharmacies'])} ta\n"
        f"📈 O'rtacha bron: <code>{fmt_sum(average)}</code> so'm"
    ]

    statuses = await repo.stats_by_status(company_id, since)
    blocks.append(
        "📌 <b>Holat bo'yicha</b>\n" + "\n".join(
            f"{STATUS_LABEL.get(s['status'], esc(s['status']))} — "
            f"{fmt_qty(s['n'])} ta · <code>{fmt_sum(s['total'])}</code>"
            for s in statuses
        )
    )

    drugs = await repo.stats_top_drugs(company_id, since, TOP_LIMIT)
    if drugs:
        blocks.append(
            "💊 <b>Ko'p ketgan dorilar</b>\n" + "\n".join(
                f"{i}. {_cut(d['drug_name'])} — "
                f"{fmt_qty(d['qty'])} {esc(d['unit'])} · "
                f"<code>{fmt_sum(d['total'])}</code>"
                for i, d in enumerate(drugs, 1)
            )
        )

    regions = await repo.stats_by_region(company_id, since)
    if regions:
        blocks.append(
            "📍 <b>Viloyatlar bo'yicha</b>\n" + "\n".join(
                f"{_cut(r['name'])} — {fmt_qty(r['n'])} ta · "
                f"<code>{fmt_sum(r['total'])}</code>"
                for r in regions
            )
        )

    pharmacies = await repo.stats_top_pharmacies(company_id, since, TOP_LIMIT)
    if pharmacies:
        blocks.append(
            "🏆 <b>Eng faol aptekalar</b>\n" + "\n".join(
                f"{i}. {_cut(p['name'])} ({_cut(p['region_name'], 12)}) — "
                f"{fmt_qty(p['n'])} ta · <code>{fmt_sum(p['total'])}</code>"
                for i, p in enumerate(pharmacies, 1)
            )
        )

    return "\n\n".join(blocks)


# ============================================================
#  KIRISH
# ============================================================

@router.message(Command("stats"))
@router.message(F.text == kb.BTN_STATS)
async def stats_entry(message: types.Message, state: FSMContext, company):
    await state.clear()
    text = await build_report(company["id"], DEFAULT_PERIOD)
    await message.answer(text, reply_markup=ikb.stats_periods(DEFAULT_PERIOD))


# ============================================================
#  DAVRNI ALMASHTIRISH
# ============================================================

@router.callback_query(F.data.startswith(f"{ikb.CB_STATS}p:"))
async def stats_period(callback: types.CallbackQuery, company):
    period = callback.data.removeprefix(f"{ikb.CB_STATS}p:")
    if period not in PERIOD_LABEL:
        return await callback.answer("⚠️ Noma'lum davr", show_alert=True)

    text = await build_report(company["id"], period)
    try:
        await callback.message.edit_text(text, reply_markup=ikb.stats_periods(period))
    except TelegramBadRequest as e:
        # Bir xil davr qayta bosilsa Telegram "message is not modified" beradi
        if "not modified" not in str(e):
            raise
    await callback.answer()


# ============================================================
#  EXCEL EKSPORT
# ============================================================

@router.callback_query(F.data.startswith(f"{ikb.CB_STATS}x:"))
async def stats_excel(callback: types.CallbackQuery, company):
    period = callback.data.removeprefix(f"{ikb.CB_STATS}x:")
    if period not in PERIOD_LABEL:
        return await callback.answer("⚠️ Noma'lum davr", show_alert=True)

    await callback.answer("📥 Fayl tayyorlanmoqda...")
    company_id = company["id"]
    since, _ = await repo.period_start(period)

    brons = await repo.list_brons_for_export(company_id, since)
    if not brons:
        return await callback.message.answer("📭 Bu davrda eksport qiladigan bron yo'q.")

    drugs = await repo.stats_top_drugs(company_id, since, EXPORT_DRUGS)
    label = PERIOD_LABEL[period]
    data = build_stats_excel(brons, drugs, label, STATUS_LABEL)

    await callback.message.answer_document(
        BufferedInputFile(data, filename=f"statistika_{period}.xlsx"),
        caption=f"📊 Statistika — {label}  |  {len(brons)} ta bron",
    )
    logger.info("Statistika eksporti (%s): %s ta bron", period, len(brons))
