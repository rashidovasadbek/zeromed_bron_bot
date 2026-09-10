# zeromed_co_bron_bot

**Zeromed** uchun bron yig'uvchi Telegram bot. `mediwell02bronbot`dan nusxa
olingan — arxitektura va bron oqimi bir xil, faqat kompaniya rekvizitlari
(`db/migrations/002_seed.sql`) va `.env` boshqa.

> ⚠️ Bot username, guruh ID'lari va deploy manzili hali belgilanmagan —
> pastdagi bo'limlarni to'ldiring.

Menejer aptekani tanlaydi → dorilarni bron qiladi → Excel spesifikatsiya oladi → bron **bron guruhiga** tushadi → to'lov qilingach **oplata guruhiga** o'tadi.

Butun interfeys va kod izohlari **o'zbekcha** — handler yoki xabar qo'shsangiz shu qoidani saqlang.

## Ishga tushirish

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # to'ldiring (pastga qarang)
python -m db.migrate              # baza sxemasini qo'llash
python main.py
```

Testlar yoki linter sozlamasi yo'q.

## `.env`

| Kalit | Izoh |
|---|---|
| `BOT_TOKEN` | @BotFather dan |
| `BRON_GROUP_ID` | Bronlar tushadigan guruh (bot admin bo'lishi shart) |
| `OPLATA_GROUP_ID` | To'lov qilinganlar tushadigan guruh |
| `BOOTSTRAP_ADMIN_ID` | Faqat birinchi ishga tushirish uchun: bazada admin bo'lmasa, shu ID admin qilib yoziladi |
| `DB_USER` / `DB_PASSWORD` / `DB_NAME` / `DB_HOST` / `DB_PORT` | PostgreSQL |
| `COMPANY_CODE` | `company.code` — bu botda `zeromed` |

Adminlar `.env` da emas, **bazada** (`app_user.role`). Admin qo'shish uchun kod ham, qayta ishga tushirish ham kerak emas.

> Guruhlar hozir oddiy `group` turida. Supergroup'ga o'tkazilsa **ID o'zgaradi** — `.env` ni yangilash kerak.

## Arxitektura

| Papka / fayl | Vazifasi |
|---|---|
| `main.py` | Dispatcher, middleware va routerlarni yig'adi |
| `config.py` | Env **bitta joyda** o'qiladi (`Settings`) |
| `db/pool.py` | asyncpg pool — butun bot uchun bitta |
| `db/repo.py` | **Barcha SQL** shu yerda; handlerlarda SQL yo'q |
| `db/migrate.py` + `db/migrations/` | Idempotent migration runner (`schema_migrations`) |
| `handlers/bron.py` | Apteka tanlash → savat → hisoblash → tasdiqlash |
| `handlers/groups.py` | Bron guruhidagi «To'lov guruhiga yuborish» tugmasi |
| `handlers/admin.py` | Xodimlar, dorilar, kompaniya rekvizitlari |
| `handlers/pharmacy_admin.py` | Aptekalar: qo'shish, tahrirlash, ma'lumot, Excel |
| `handlers/stats.py` | 📊 Statistika: davr bo'yicha hisobot + Excel (faqat admin) |
| `middlewares/auth.py` | `app_user` ro'yxatidan o'tmagan odam kira olmaydi |
| `services/pricing.py` | Pul hisobi — **yagona manba** |
| `services/render.py` | Xabar matnlari + 4096 belgi chegarasi (`chunks()`) |
| `services/excel.py` | Excel → `bytes` (diskka yozilmaydi) |

### Rollar

`admin` — hamma narsa · `buxgalter` — to'lovni tasdiqlaydi · `manager` — bron qiladi

To'lov tugmasini faqat `admin` va `buxgalter` bosa oladi.

### Shartnoma raqami

Format `SA/B/C` — masalan **`S5/50/03`**:
- **S** — yo'nalish harfi (`company.contract_prefix`) — bu botda **`S`** (Sobir)
- **A** — `counter` jadvalidan, `UPDATE … RETURNING` bilan (atomar, poyga yo'q)
- **B** — viloyat kodi (`region.code`: 50=Namangan, 60=Andijon, …)
- **C** — kompaniyaning sho't kodi (`company.account_code`) — bu botda **`03`**

Harf ham, sho't kodi ham bazada (`company` jadvalida), kodda emas. Ikkalasi
ham har bir shartnoma raqamiga tushadi, shuning uchun admin paneldan
tahrirlanmaydi (`COMPANY_FIELDS` ro'yxatida yo'q) — o'zgartirish kerak
bo'lsa yangi migration yoziladi.

### Pul hisobi

`services/pricing.py` da, `Decimal` + `ROUND_HALF_UP`. Yaxlitlash tartibi o'zgartirilmasligi kerak:

1. qator qiymati = narx × miqdor — yaxlitlanmaydi
2. NDS summasi — 2 xonagacha
3. qator jami = qiymat + NDS — butun so'mgacha
4. umumiy jami = yaxlitlangan qator jamilar yig'indisi

Bron yaratilganda narx, NDS va qator jami `bron_item` ga **snapshot** qilinadi — dori keyin qimmatlashsa ham eski hujjat o'zgarmaydi. Oplata guruhiga yuborishda summalar qayta hisoblanmaydi (`pricing.stored_items`).

## Deploy

> TODO: server, papka, baza nomi va systemd unit hali belgilanmagan.
> Xuddi shu serverda ishlaydigan bo'lsa, **DB nomi va papkani
> `mediwell02bronbot` (baza `zeromed_bron`) bilan to'qnashtirmang** —
> masalan baza `zeromed_co_bron`, unit `zeromedcobot.service`.

```bash
git pull origin main
./venv/bin/pip install -r requirements.txt   # requirements o'zgargan bo'lsa
./venv/bin/python -m db.migrate              # yangi migration bo'lsa
sudo systemctl restart <unit-nomi>.service
journalctl -u <unit-nomi>.service -f
```

Sog'lom start log'i: `Bot ishga tushdi... 🚀`

## Sxemani o'zgartirish

`db/migrations/` ga yangi `00N_*.sql` qo'shing va `python -m db.migrate` yugurtiring. Mavjud fayllar **tahrirlanmaydi** — ular allaqachon qo'llangan.
