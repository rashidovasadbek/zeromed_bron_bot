-- ============================================================
--  Shartnoma raqami: SA/B/C formati
-- ============================================================
-- 003 da viloyat kodi (B) formatdan olib tashlangan edi (A/C).
-- Endi u qaytariladi va oldiga yo'nalish harfi qo'shiladi:
--
--     S5/50/03
--     │└┘ │  └── C — sho't kodi          (company.account_code)
--     │ │  └──── B — viloyat kodi        (contract.region_code)
--     │ └─────── A — tartib raqami       (contract.seq_no)
--     └───────── S — yo'nalish harfi     (company.contract_prefix, "Sobir")
--
-- Harf kodga yozilmaydi, bazada turadi — qolgan rekvizitlar kabi.
-- Shu bilan birga account_code '01' dan '03' ga o'zgaradi: 002_seed.sql
-- dagi '01' taxminiy edi va o'sha faylning izohida tasdiqlash so'ralgan.

ALTER TABLE company ADD COLUMN contract_prefix TEXT NOT NULL DEFAULT '';

UPDATE company
SET contract_prefix = 'S',
    account_code    = '03'
WHERE code = 'zeromed';

-- Mavjud shartnomalar yangi formatga o'tkaziladi. contract.account_code
-- ham yangilanadi — u yaratilish paytida company'dan nusxa olinadi.
-- bron.doc_contract_no ataylab tegilmaydi: u snapshot, eski bronlar
-- eski raqam bilan qolishi kerak (001_init.sql dagi izohga ko'ra).
UPDATE contract c
SET contract_no  = co.contract_prefix || c.seq_no || '/'
                   || c.region_code || '/' || co.account_code,
    account_code = co.account_code
FROM company co
WHERE co.id = c.company_id;
