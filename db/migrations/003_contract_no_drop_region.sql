-- ============================================================
--  Shartnoma raqami formatidan viloyat kodini (B) olib tashlash
-- ============================================================
-- Eski format edi A/B/C (masalan 5/60/02), endi A/C (5/02).
-- region_code ustuni contract jadvalida saqlanib qoladi (tarixiy
-- yozuv sifatida), lekin contract_no ga endi qo'shilmaydi.
--
-- bron.doc_contract_no — bu snapshot, eski bronlar eski formatda
-- qolaveradi (001_init.sql dagi izohga ko'ra: "shartnoma keyin
-- o'zgarsa, bron o'zgarmaydi").

UPDATE contract
SET contract_no = seq_no || '/' || account_code;
