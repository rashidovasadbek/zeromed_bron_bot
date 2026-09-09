# -*- coding: utf-8 -*-
"""Migration runner.

Ishlatish:  python -m db.migrate

db/migrations/ ichidagi *.sql fayllar nomi bo'yicha tartiblanib
yugurtiriladi. Har biri schema_migrations jadvaliga yoziladi, shuning uchun
qayta yugurtirish xavfsiz — allaqachon qo'llanilgani o'tkazib yuboriladi.
Har bir fayl bitta tranzaksiyada bajariladi: o'rtasida xato chiqsa,
o'sha fayl to'liq orqaga qaytadi.

farm_botda migration umuman yo'q edi — skripts.sql qo'lda yurgizilgan
DDL to'plami bo'lib qolgan va production bilan mos kelmasdi.
"""
import asyncio
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_db_settings  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


async def run() -> int:
    settings = load_db_settings()
    conn = await asyncpg.connect(**settings.db_config)
    try:
        await conn.execute(CREATE_TRACKING_TABLE)
        applied = {r["filename"] for r in await conn.fetch("SELECT filename FROM schema_migrations")}

        files = sorted(MIGRATIONS_DIR.glob("*.sql"), key=lambda p: p.name)
        if not files:
            print(f"⚠️  {MIGRATIONS_DIR} bo'sh — migration topilmadi")
            return 1

        pending = [f for f in files if f.name not in applied]
        if not pending:
            print(f"✅ Hammasi qo'llangan ({len(applied)} ta migration)")
            return 0

        for path in pending:
            sql = path.read_text(encoding="utf-8")
            print(f"▶️  {path.name} ...", end=" ", flush=True)
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES ($1)", path.name
                )
            print("ok")

        print(f"✅ {len(pending)} ta migration qo'llandi")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(run()))
    except Exception as e:  # noqa: BLE001 — CLI, sabab ko'rinishi kerak
        print(f"❌ Migration xatosi: {type(e).__name__}: {e}")
        sys.exit(1)
