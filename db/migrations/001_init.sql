-- ============================================================
--  mediwell02_bron_bot — boshlang'ich sxema
-- ============================================================
-- Eslatma: bu fayl bir marta ishlaydi va qayta o'zgartirilmaydi.
-- Sxemani o'zgartirish kerak bo'lsa — yangi 00N_*.sql fayl qo'shing.

-- Apteka nomini xato yozilganda ham topish uchun (similarity)
CREATE EXTENSION IF NOT EXISTS pg_trgm;


-- 1. Kompaniya rekvizitlari -----------------------------------
-- farm_botda bu ma'lumot kodda uchta parallel dict edi
-- (SELLER_DETAILS / COMPANY_HEADER / BANK_BLOCK) — endi bazada.
CREATE TABLE company (
    id            SERIAL PRIMARY KEY,
    code          TEXT NOT NULL UNIQUE,          -- 'mediwell'
    name          TEXT NOT NULL,                 -- OOO "MEDIWELL" MCHJ
    address       TEXT,
    account_no    TEXT,                          -- H/r
    bank_name     TEXT,
    inn           TEXT,
    mfo           TEXT,
    director      TEXT,
    account_code  VARCHAR(5) NOT NULL,           -- shartnoma raqamidagi C qismi
    header_emoji  TEXT NOT NULL DEFAULT '🟢',    -- guruh xabari sarlavhasi uchun
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- 2. Viloyatlar -----------------------------------------------
-- farm_botda region erkin matn edi va bazada 58 xil yozuv yig'ilgan.
-- Bu yerda faqat tugmadan tanlanadi — xom matn umuman kiritilmaydi.
CREATE TABLE region (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    code        VARCHAR(5) NOT NULL,             -- shartnoma raqamidagi B qismi
    sort_order  INTEGER NOT NULL DEFAULT 0,
    active      BOOLEAN NOT NULL DEFAULT TRUE
);


-- 3. Tizim foydalanuvchilari ----------------------------------
-- Ro'yxatda yo'q odam botdan umuman foydalana olmaydi.
--   admin     — hamma narsa
--   buxgalter — to'lovni tasdiqlaydi (oplata guruhiga yuborish)
--   manager   — bron qiladi
CREATE TABLE app_user (
    id           SERIAL PRIMARY KEY,
    telegram_id  BIGINT NOT NULL UNIQUE,
    full_name    TEXT NOT NULL,
    role         TEXT NOT NULL CHECK (role IN ('admin', 'buxgalter', 'manager')),
    phone        TEXT,
    active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_app_user_active ON app_user(active) WHERE active;


-- 4. Aptekalar ------------------------------------------------
-- INN unique emas: bitta tashkilot bir nechta shartnoma olishi mumkin.
-- Admin panel qo'shishda dublikat haqida ogohlantiradi.
CREATE TABLE pharmacy (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    inn             VARCHAR(20) NOT NULL,
    region_id       INTEGER NOT NULL REFERENCES region(id),
    manager_user_id INTEGER REFERENCES app_user(id),
    phone           TEXT,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pharmacy_inn ON pharmacy(inn);
CREATE INDEX idx_pharmacy_region ON pharmacy(region_id);
-- Nomni xato yozilsa ham topish uchun (ILIKE va similarity ikkalasi ham tez ishlaydi)
CREATE INDEX idx_pharmacy_name_trgm ON pharmacy USING gin (lower(name) gin_trgm_ops);


-- 5. Shartnomalar ---------------------------------------------
-- Raqam formati A/B/C:
--   A = seq_no       (kompaniya bo'yicha ketma-ket, counter jadvalidan)
--   B = region_code  (viloyat kodi: 50=Namangan, 60=Andijon, ...)
--   C = account_code (bank sho't kodi — bu botda doim '02')
CREATE TABLE contract (
    id             SERIAL PRIMARY KEY,
    pharmacy_id    INTEGER NOT NULL REFERENCES pharmacy(id) ON DELETE CASCADE,
    company_id     INTEGER NOT NULL REFERENCES company(id),
    seq_no         INTEGER NOT NULL,
    region_code    VARCHAR(5) NOT NULL,
    account_code   VARCHAR(5) NOT NULL,
    contract_no    TEXT NOT NULL UNIQUE,          -- to'liq "A/B/C"
    contract_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pharmacy_id, company_id)
);
CREATE INDEX idx_contract_pharmacy ON contract(pharmacy_id);


-- 6. Shartnoma raqami hisoblagichi ----------------------------
-- farm_botdagi MAX(seq_no)+1 usuli poyga (race) beradi: ikki admin
-- bir vaqtda apteka qo'shsa bir xil raqam chiqadi.
-- Bu yerda UPDATE ... RETURNING qatorni qulflaydi — takrorlanish mumkin emas.
CREATE TABLE counter (
    company_id  INTEGER PRIMARY KEY REFERENCES company(id) ON DELETE CASCADE,
    last_seq    INTEGER NOT NULL DEFAULT 0
);


-- 7. Dorilar --------------------------------------------------
-- price_no_nds: 3 xonali — production bazasida narxlar shunday
-- (masalan 51339.286). farm_bot skripts.sql dagi (15,2) noto'g'ri edi.
CREATE TABLE drug (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    unit          VARCHAR(20) NOT NULL DEFAULT 'шт',
    price_no_nds  NUMERIC(15, 3) NOT NULL CHECK (price_no_nds >= 0),
    nds_rate      INTEGER NOT NULL DEFAULT 12 CHECK (nds_rate >= 0),
    box_capacity  INTEGER CHECK (box_capacity IS NULL OR box_capacity > 0),
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_drug_active ON drug(active) WHERE active;


-- 8. Savat ----------------------------------------------------
-- PRIMARY KEY (user_id, drug_id) — bir dori bir marta turadi.
-- farm_botda har qo'shish yangi qator yaratardi va savatda dublikat chiqardi.
CREATE TABLE cart (
    user_id     BIGINT NOT NULL,                 -- telegram_id
    drug_id     INTEGER NOT NULL REFERENCES drug(id) ON DELETE CASCADE,
    quantity    INTEGER NOT NULL CHECK (quantity > 0),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, drug_id)
);


-- 9. Bronlar --------------------------------------------------
-- doc_contract_no — snapshot: shartnoma keyin o'zgarsa, bron o'zgarmaydi.
CREATE TABLE bron (
    id                 BIGSERIAL PRIMARY KEY,
    manager_tg_id      BIGINT NOT NULL,
    pharmacy_id        INTEGER NOT NULL REFERENCES pharmacy(id),
    contract_id        INTEGER NOT NULL REFERENCES contract(id),
    company_id         INTEGER NOT NULL REFERENCES company(id),
    doc_contract_no    TEXT NOT NULL,
    doc_contract_date  DATE,
    total_sum          NUMERIC(15, 2) NOT NULL DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'new'
                         CHECK (status IN ('new', 'sent_to_pay', 'paid', 'cancelled')),
    bron_group_msg_id  BIGINT,                   -- guruhdagi xabarni tahrirlash uchun
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_to_pay_at     TIMESTAMPTZ,
    sent_to_pay_by     BIGINT                    -- kim to'lovga yubordi (telegram_id)
);
CREATE INDEX idx_bron_manager ON bron(manager_tg_id);
CREATE INDEX idx_bron_pharmacy ON bron(pharmacy_id);
CREATE INDEX idx_bron_status ON bron(status);
CREATE INDEX idx_bron_created ON bron(created_at DESC);


-- 10. Bron tarkibi --------------------------------------------
-- farm_bot buyurtma tarkibini tayyor HTML matn (drugs_text) sifatida
-- saqlardi — hisobot ham, qayta chizish ham imkonsiz edi.
-- Bu yerda har qator strukturalangan va narx snapshot qilinadi.
CREATE TABLE bron_item (
    id            BIGSERIAL PRIMARY KEY,
    bron_id       BIGINT NOT NULL REFERENCES bron(id) ON DELETE CASCADE,
    drug_id       INTEGER REFERENCES drug(id),
    drug_name     TEXT NOT NULL,
    unit          VARCHAR(20) NOT NULL,
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    price_no_nds  NUMERIC(15, 3) NOT NULL,
    nds_rate      INTEGER NOT NULL,
    nds_sum       NUMERIC(15, 2) NOT NULL,
    line_total    NUMERIC(15, 2) NOT NULL,
    line_no       INTEGER NOT NULL
);
CREATE INDEX idx_bron_item_bron ON bron_item(bron_id);
