# -*- coding: utf-8 -*-
"""Xabar matnlarini yasash.

Telegram bitta xabarga 4096 belgi qo'yadi. farm_botda spesifikatsiya
xabari shu chegaraga urilib uzilib qolardi (send_blocks faqat admin
panelda bor edi). Bu yerda uzun matn har doim chunks() orqali o'tadi.
"""
import html

from services.pricing import Totals, fmt_money, fmt_qty, fmt_sum

# 4096 emas: HTML teglar va qo'shiladigan sarlavha uchun zaxira qoldiramiz
MAX_LEN = 3500

LINE = "─────────────────────"
SHORT_LINE = "──────────────────"


def esc(value) -> str:
    return html.escape(str(value)) if value is not None else ""


def chunks(blocks: list[str], separator: str = "\n\n") -> list[str]:
    """Bloklarni MAX_LEN ga sig'adigan xabarlarga yig'adi.

    Blok hech qachon o'rtasidan bo'linmaydi — faqat bloklar orasidan.
    Bitta blokning o'zi MAX_LEN dan uzun bo'lsa, alohida xabar bo'lib
    ketadi (Telegram uni baribir qabul qiladi, chunki 4096 dan kichik).
    """
    out: list[str] = []
    current = ""
    for block in blocks:
        candidate = block if not current else current + separator + block
        if len(candidate) > MAX_LEN and current:
            out.append(current)
            current = block
        else:
            current = candidate
    if current:
        out.append(current)
    return out


# ============================================================
#  SPESIFIKATSIYA
# ============================================================

def spec_lines(totals: Totals) -> list[str]:
    """Har dori uchun bitta blok."""
    return [
        (
            f"<b>{i}. {esc(ln.name)}</b>\n"
            f"   {fmt_qty(ln.quantity)} {esc(ln.unit)} × {fmt_money(ln.price_no_nds)}"
            f" = {fmt_money(ln.cost_no_nds)}\n"
            f"   NDS {ln.nds_rate}%: +{fmt_money(ln.nds_sum)}\n"
            f"   💵 <b>{fmt_money(ln.line_total)} so'm</b>"
        )
        for i, ln in enumerate(totals.lines, 1)
    ]


def spec_header(pharmacy) -> str:
    return (
        f"💊 <b>SPESIFIKATSIYA</b>\n"
        f"🏢 <b>{esc(pharmacy['name'])}</b>\n"
        f"📄 Shartnoma №{esc(pharmacy['contract_no'])}\n"
        f"{LINE}"
    )


def spec_footer(totals: Totals) -> str:
    return f"{LINE}\n💰 <b>JAMI: <code>{fmt_sum(totals.grand_total)} so'm</code></b>"


def spec_messages(pharmacy, totals: Totals) -> list[str]:
    """To'liq spesifikatsiya — bo'lingan xabarlar ro'yxati."""
    blocks = [spec_header(pharmacy)] + spec_lines(totals) + [spec_footer(totals)]
    return chunks(blocks)


# ============================================================
#  GURUH XABARLARI
# ============================================================

def bank_block(company) -> str:
    return (
        f"🏦 <b>BANK REKVIZITLARI:</b>\n"
        f"💳 H/R: <code>{esc(company['account_no'] or '—')}</code>\n"
        f"🆔 INN: <code>{esc(company['inn'] or '—')}</code>\n"
        f"🏛 MFO: <code>{esc(company['mfo'] or '—')}</code> ({esc(company['bank_name'] or '—')})"
    )


def _date(value) -> str:
    return value.strftime("%d.%m.%Y") if value else "—"


def bron_group_messages(bron_id: int, pharmacy, totals: Totals,
                        manager_name: str) -> list[str]:
    """Bron guruhiga tushadigan xabar.

    INN, sana va bank rekvizitlari ataylab yo'q — bu guruhda bronni
    kim, qaysi aptekaga qilgani ko'rinsa yetarli.
    """
    header = (
        f"🚀 <b>YANGI BRON</b> №{bron_id}\n"
        f"🏢 <b>{esc(pharmacy['name'])}</b>\n"
        f"📍 {esc(pharmacy['region_name'])}  |  👤 {esc(manager_name)}\n"
        f"📄 Shartnoma №{esc(pharmacy['contract_no'])}\n"
        f"{SHORT_LINE}"
    )
    footer = (
        f"{SHORT_LINE}\n"
        f"💰 <b>JAMI:</b> <code>{fmt_sum(totals.grand_total)}</code> so'm"
    )
    return chunks([header] + spec_lines(totals) + [footer])


def oplata_group_messages(bron, totals: Totals) -> list[str]:
    """Oplata guruhiga tushadigan xabar — eng to'liq ma'lumot.

    Menejer ismi va bank rekvizitlari yo'q: pul allaqachon tushgan.
    """
    header = (
        f"💳 <b>TO'LOV QILINDI</b>  |  Bron №{bron['id']}\n"
        f"🏢 <b>{esc(bron['pharmacy_name'])}</b>\n"
        f"🔢 INN: <code>{esc(bron['inn'])}</code>\n"
        f"📄 Shartnoma №{esc(bron['doc_contract_no'])}\n"
        f"📅 Sana: {_date(bron['doc_contract_date'])}\n"
        f"📍 {esc(bron['region_name'])}\n"
        f"{SHORT_LINE}"
    )
    footer = (
        f"{SHORT_LINE}\n"
        f"💰 <b>TO'LOV UCHUN JAMI:</b> "
        f"<code>{fmt_sum(totals.grand_total)}</code> so'm"
    )
    return chunks([header] + spec_lines(totals) + [footer])


def manager_receipt_messages(company, pharmacy, totals: Totals) -> list[str]:
    """Menejerga DM: rekvizitlar + to'liq dorilar ro'yxati.

    Bitta bronda 6-7 xil dori bo'lishi odatiy — ro'yxat to'liq chiqadi,
    uzun bo'lsa chunks() bo'lib yuboradi.
    """
    header = (
        f"{bank_block(company)}\n"
        f"📄 <b>Shartnoma №:</b> {esc(pharmacy['contract_no'])}\n"
        f"📅 <b>Sana:</b> {_date(pharmacy['contract_date'])}\n"
        f"{SHORT_LINE}"
    )
    footer = (
        f"{SHORT_LINE}\n"
        f"💰 <b>TO'LOV UCHUN JAMI:</b> "
        f"<code>{fmt_sum(totals.grand_total)}</code> so'm"
    )
    return chunks([header] + spec_lines(totals) + [footer])


# ============================================================
#  APTEKA MA'LUMOTI
# ============================================================

def pharmacy_block(row) -> str:
    phone = f"<code>{esc(row['phone'])}</code>" if row["phone"] else "—"
    return (
        f"🏢 <b>{esc(row['name'])}</b>\n"
        f"📍 {esc(row['region_name'])}\n"
        f"🔢 INN: <code>{esc(row['inn'])}</code>\n"
        f"📞 {phone}\n"
        f"📄 Shartnoma №: <code>{esc(row['contract_no'] or '—')}</code>\n"
        f"📅 Sana: {_date(row['contract_date'])}\n"
        f"👤 Menejer: {esc(row['manager_name'] or '—')}"
    )
