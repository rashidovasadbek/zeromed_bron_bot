-- ============================================================
--  Boshlang'ich ma'lumotlar: viloyatlar + kompaniya
-- ============================================================

-- Viloyat kodlari (B) — farm_bot database.REGION_CODES dan olingan.
-- Bu kodlar shartnoma raqamiga tushadi, shuning uchun o'zgartirilmaydi.
INSERT INTO region (name, code, sort_order) VALUES
    ('Toshkent vil.', '10', 10),
    ('Sirdaryo',      '20', 20),
    ('Jizzax',        '25', 25),
    ('Samarqand',     '30', 30),
    ('Farg''ona',     '40', 40),
    ('Namangan',      '50', 50),
    ('Andijon',       '60', 60),
    ('Qashqadaryo',   '70', 70),
    ('Surxondaryo',   '75', 75),
    ('Buxoro',        '80', 80),
    ('Navoiy',        '85', 85),
    ('Xorazm',        '90', 90),
    ('Nukus',         '95', 95);


-- Kompaniya. mediwell02bronbot'dan nusxa: rekvizitlar (bank, INN, MFO,
-- direktor) mediwell bilan bir xil, faqat nomi va sho't raqami boshqa.
-- ⚠️ account_code = '01' — vaqtinchalik taxmin, deploy'dan oldin
--    tasdiqlang (kerak bo'lsa shu qatorni tahrirlang, hali qo'llanmagan).
--    Keyinchalik admin panel orqali ham tahrirlanadi — kod o'zgarishi shart emas.
INSERT INTO company (code, name, address, account_no, bank_name, inn, mfo, director, account_code, header_emoji)
VALUES (
    'zeromed',
    'Zeromed',
    NULL,
    '20208000007367249003',
    '"InFinBANK"',
    '312636862',
    '01070',
    'А.А.Рашидов',
    '01',
    '🔵'
);

-- Shartnoma raqami hisoblagichi nolda boshlanadi
INSERT INTO counter (company_id, last_seq)
SELECT id, 0 FROM company WHERE code = 'zeromed';
