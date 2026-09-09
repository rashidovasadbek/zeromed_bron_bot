# -*- coding: utf-8 -*-
"""Pul hisobi — YAGONA manba.

farm_botda bu hisob ikki joyda (calc_and_send va create_excel_order) aynan
takrorlangan edi: birini o'zgartirib ikkinchisini unutish oson. Bu yerda
spesifikatsiya matni ham, Excel ham, bazaga yozish ham shu moduldan oladi.

Yaxlitlash tartibi farm_bot bilan bir xil — buxgalteriya hujjatlari mos
kelishi uchun o'zgartirilmasligi kerak:
  1. qator qiymati (NDSsiz) = narx × miqdor        — yaxlitlanmaydi
  2. NDS summasi                                   — 2 xonagacha, ROUND_HALF_UP
  3. qator jami = qiymat + NDS                     — butun so'mgacha, ROUND_HALF_UP
  4. umumiy jami = yaxlitlangan qator jamilar yig'indisi
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
SUM = Decimal("1")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class Line:
    """Spesifikatsiyaning bitta qatori — hisoblangan holda."""

    drug_id: int | None
    name: str
    unit: str
    quantity: int
    price_no_nds: Decimal
    nds_rate: int
    cost_no_nds: Decimal   # narx × miqdor (yaxlitlanmagan)
    nds_sum: Decimal       # 2 xona
    line_total: Decimal    # butun so'm


@dataclass(frozen=True)
class Totals:
    lines: list[Line]
    grand_total: Decimal   # butun so'm

    @property
    def is_empty(self) -> bool:
        return not self.lines


def _dec(value) -> Decimal:
    """Har qanday sonni Decimal'ga aylantiradi.

    float orqali o'tkazmaymiz: 0.1 + 0.2 muammosi buxgalteriyada kechirilmaydi.
    asyncpg NUMERIC ustunni allaqachon Decimal qaytaradi, lekin qo'lda
    kiritilgan qiymat str/int bo'lishi mumkin.
    """
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def calc_line(drug_id, name: str, unit: str, quantity, price_no_nds, nds_rate) -> Line:
    qty = int(quantity)
    price = _dec(price_no_nds)
    rate = int(nds_rate)

    cost_no_nds = price * qty
    nds_sum = (cost_no_nds * (Decimal(rate) / HUNDRED)).quantize(CENT, rounding=ROUND_HALF_UP)
    line_total = (cost_no_nds + nds_sum).quantize(SUM, rounding=ROUND_HALF_UP)

    return Line(
        drug_id=drug_id,
        name=name,
        unit=unit,
        quantity=qty,
        price_no_nds=price,
        nds_rate=rate,
        cost_no_nds=cost_no_nds,
        nds_sum=nds_sum,
        line_total=line_total,
    )


def calc_items(rows) -> Totals:
    """Savat qatorlari (yoki bron tarkibi) → hisoblangan spesifikatsiya.

    rows — asyncpg Record yoki dict bo'lishi mumkin; quyidagi kalitlar kerak:
    drug_id, name, unit, quantity, price_no_nds, nds_rate
    """
    lines = [
        calc_line(
            r["drug_id"],
            r["name"],
            r["unit"],
            r["quantity"],
            r["price_no_nds"],
            r["nds_rate"],
        )
        for r in rows
    ]
    grand_total = sum((ln.line_total for ln in lines), Decimal("0"))
    return Totals(lines=lines, grand_total=grand_total)


def stored_items(rows) -> Totals:
    """Bazadagi bron_item qatorlaridan Totals yasaydi — QAYTA HISOBLAMAYDI.

    Bron yaratilganda hisoblangan summalar saqlanadi. Keyin dori narxi
    o'zgarsa ham, to'lov xabaridagi raqamlar hujjatdagi bilan bir xil
    qolishi shart — shuning uchun nds_sum va line_total bazadan olinadi.
    """
    lines = [
        Line(
            drug_id=r["drug_id"],
            name=r["name"],
            unit=r["unit"],
            quantity=int(r["quantity"]),
            price_no_nds=_dec(r["price_no_nds"]),
            nds_rate=int(r["nds_rate"]),
            cost_no_nds=_dec(r["price_no_nds"]) * int(r["quantity"]),
            nds_sum=_dec(r["nds_sum"]),
            line_total=_dec(r["line_total"]),
        )
        for r in rows
    ]
    grand_total = sum((ln.line_total for ln in lines), Decimal("0"))
    return Totals(lines=lines, grand_total=grand_total)


# --- Formatlash ---------------------------------------------------------
# Faqat ko'rsatish uchun. Hisobga qaytib kirmaydi — farm_botda formatlangan
# matn keyin float() bilan qayta o'qilardi, bu esa xato manbai edi.

def fmt_sum(value) -> str:
    """1234567 → '1 234 567' (butun so'm)."""
    return f"{_dec(value):,.0f}".replace(",", " ")


def fmt_money(value) -> str:
    """1234567.89 → '1 234 567.89'."""
    return f"{_dec(value):,.2f}".replace(",", " ")


def fmt_qty(value) -> str:
    return f"{int(value):,}".replace(",", " ")
