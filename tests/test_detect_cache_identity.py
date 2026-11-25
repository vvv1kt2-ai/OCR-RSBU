# -*- coding: utf-8 -*-
r"""Тест: ключ кэша меток страниц следует за ФАЙЛОМ, а не только за именем.

Что было сломано:
  Ключ кэша меток был `{документ}_detect_{хэш промпта}_pg_p{страница}` — отпечатка
  файла в нём не было. Ключ кэша РАСШИФРОВОК страниц отпечаток содержал всегда, и
  в самом коде записано правило: «Two files can share a name (re-download, replaced
  file) and two names can share content. The cache key must follow the bytes».
  Кэш меток это правило нарушал.

  Как это проявилось. Пользователь заменил `АйДи Коллект_6мес_2026.pdf`: вместо
  пояснительной записки положил настоящую отчётность. Стем и промпт у нового файла
  те же, поэтому ключи совпали, и прогон взял СТАРЫЕ метки: страницы 1-22 остались
  помечены 'notes' от прежнего файла. Баланс нового файла лежит на стр. 1 — он не был
  найден вовсе, в артефакте `balance: None`, а статус вышел `needs_review`.

Правило, которое проверяется: две разные редакции одного имени дают разные ключи.

Запуск: python D:\models\tests\test_detect_cache_identity.py
Лог:    tests\_last_run_detect_identity.txt
"""
import hashlib
import io
import os
import sys
import tempfile

sys.path.insert(0, r'D:\models\pylibs')
sys.path.insert(0, r'D:\models')
import pymupdf
import pipeline as pl

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_detect_identity.txt'), 'w',
              encoding='utf-8')
ok = fail = 0


def check(name, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        LOG.write(f'  OK   {name}\n')
    else:
        fail += 1
        LOG.write(f'  ПРОВАЛ {name} {detail}\n')


# ─── 1. отпечаток входит в ключ ───
LOG.write('=== 1. отпечаток входит в ключ ===\n')
A = pl.detect_cache_stem('Тест_6мес_2026.pdf', fp='aaaaaaaaaa')
B = pl.detect_cache_stem('Тест_6мес_2026.pdf', fp='bbbbbbbbbb')
check('ключ с отпечатком содержит его', 'aaaaaaaaaa' in A, A)
check('разные отпечатки дают разные ключи', A != B, f'{A} == {B}')
check('без отпечатка ключ остаётся прежним (совместимость со старыми вызовами)',
      pl.detect_cache_stem('Тест_6мес_2026.pdf') == 'Тест_6мес_2026_detect_3792534a',
      pl.detect_cache_stem('Тест_6мес_2026.pdf'))
check('страница входит в ключ',
      pl.detect_page_cache_stem('Тест_6мес_2026.pdf', 1, 'aaaaaaaaaa')
      != pl.detect_page_cache_stem('Тест_6мес_2026.pdf', 2, 'aaaaaaaaaa'))

# ─── 2. ключ страницы содержит и отпечаток, и страницу ───
LOG.write('\n=== 2. ключ страницы ===\n')
k = pl.detect_page_cache_stem('АйДи Коллект_6мес_2026.pdf', 1, 'd2e620cdf6')
check('в ключе есть отпечаток', 'd2e620cdf6' in k, k)
check('в ключе есть страница', k.endswith('_pg_p1'), k)
check('в ключе есть стем', k.startswith('АйДи Коллект_6мес_2026_detect'), k)

# ─── 3. живой вызов передаёт отпечаток ───
LOG.write('\n=== 3. живой вызов ===\n')
src = io.open(r'D:\models\pipeline.py', encoding='utf-8').read()
check('detect_pages_per_page передаёт doc_fingerprint(doc)',
      'detect_page_cache_stem(name, p, doc_fingerprint(doc))' in src)
check('doc_fingerprint считает sha1 БАЙТОВ файла',
      'sha1 of the PDF BYTES' in src or 'sha1 of the PDF BYTES' in src)

# ─── 4. на реальных файлах: два года одного эмитента не делят ключ ───
LOG.write('\n=== 4. реальные файлы ===\n')
DL = r'D:\data-scraping\downloads'


def real_fp(name):
    p = os.path.join(DL, name)
    if not os.path.exists(p):
        return None
    h = hashlib.sha1()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()[:10]


for n in ('АйДи Коллект_6мес_2025.pdf', 'АйДи Коллект_6мес_2026.pdf'):
    fp = real_fp(n)
    if fp is None:
        continue
    doc = pymupdf.open(os.path.join(DL, n))
    got = pl.doc_fingerprint(doc)
    doc.close()
    check(f'{n}: doc_fingerprint совпал с sha1 файла', got == fp, f'{got} != {fp}')

fp25, fp26 = real_fp('АйДи Коллект_6мес_2025.pdf'), real_fp('АйДи Коллект_6мес_2026.pdf')
if fp25 and fp26:
    check('у 2025 и 2026 разные отпечатки', fp25 != fp26, f'{fp25} == {fp26}')
    k25 = pl.detect_page_cache_stem('АйДи Коллект_6мес_2025.pdf', 1, fp25)
    k26 = pl.detect_page_cache_stem('АйДи Коллект_6мес_2026.pdf', 1, fp26)
    check('ключи разных файлов не совпадают', k25 != k26)
    # то, что было сломано: без отпечатка ключи различались только стемом
    check('без отпечатка ключи различались ТОЛЬКО стемом (в этом и была беда)',
          pl.detect_page_cache_stem('АйДи Коллект_6мес_2025.pdf', 1)
          .replace('2025', 'XXXX') ==
          pl.detect_page_cache_stem('АйДи Коллект_6мес_2026.pdf', 1)
          .replace('2026', 'XXXX'))

# ─── 5. замена файла меняет ключ (сценарий дефекта) ───
LOG.write('\n=== 5. замена файла меняет ключ ===\n')
tmp = tempfile.mkdtemp(prefix='detectid_')
p = os.path.join(tmp, 'Эмитент_6мес_2026.pdf')
doc = pymupdf.open()
doc.new_page().insert_text((40, 60), 'ПЕРВАЯ РЕДАКЦИЯ', fontsize=12)
doc.save(p)
doc.close()
d1 = pymupdf.open(p)
fp1 = pl.doc_fingerprint(d1)
k1 = pl.detect_page_cache_stem('Эмитент_6мес_2026.pdf', 1, fp1)
d1.close()
# заменяем файл другой редакцией под тем же именем
doc = pymupdf.open()
doc.new_page().insert_text((40, 60), 'ВТОРАЯ РЕДАКЦИЯ, ДРУГОЙ ДОКУМЕНТ', fontsize=12)
doc.save(p)
doc.close()
d2 = pymupdf.open(p)
fp2 = pl.doc_fingerprint(d2)
k2 = pl.detect_page_cache_stem('Эмитент_6мес_2026.pdf', 1, fp2)
d2.close()
check('отпечаток изменился после замены файла', fp1 != fp2, f'{fp1} == {fp2}')
check('ключ изменился после замены файла — старые метки не подхватятся',
      k1 != k2, f'{k1} == {k2}')
check('без отпечатка ключ НЕ изменился бы (старое поведение)',
      pl.detect_page_cache_stem('Эмитент_6мес_2026.pdf', 1)
      == pl.detect_page_cache_stem('Эмитент_6мес_2026.pdf', 1))

LOG.write(f'\nИТОГО: {ok} OK, {fail} провал(ов)\n')
LOG.close()
print(f'{ok} OK, {fail} провал(ов)  ->  tests/_last_run_detect_identity.txt')
sys.exit(1 if fail else 0)
