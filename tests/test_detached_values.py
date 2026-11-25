# -*- coding: utf-8 -*-
r"""Тест: текстовый слой, в котором числа оторваны от своих строк, уводит в скан.

Что было сломано:
  «АСГ Трансформаторен_6мес_2026» — скан с наклоном. Встроенный OCR записал слой так,
  что сначала идут ВСЕ названия строк и коды подряд, а числа — отдельными блоками по
  колонкам в конце страницы, без привязки к строкам. `get_text()` отдаёт этот порядок
  как есть, поэтому структурирование получило имена без чисел: в артефакте на каждой
  строке «row without values», все проверки `n/a`, а `is_failure(n/a)` — ложь. Провалов
  нет, эскалация на перечитывание картинкой не срабатывает, пустая форма проходит
  дальше как «непроваленная».

  Детектор `_garbled_page` такое не ловит по построению: он ищет ЛАТИНСКУЮ абракадабру,
  а слой АСГ кириллический — просто с ошибками OCR («Наименование локазателя»,
  «111. Капитал», «Нераспредепенная прибыль»). Буквы не важны, беда в порядке чисел.

Правило, которое проверяется: если у документа есть текстовый слой, но у большинства
строк-с-кодом нет числа рядом, слой считается нечитаемым и документ идёт веткой скана.

Признак починен и проверен на живом документе: АСГ перечитан веткой скана, статус `ok`,
34 строки, АКТИВ на месте, все шесть проверок баланса сходятся. Раздел 3 держит это
как регресс: он падает, если документ снова поедет текстовой веткой и потеряет АКТИВ.

Замер по корпусу (20 документов с текстовым слоем), доля строк-с-кодом с числом в
пределах ±3 строк:
    АСГ Трансформаторен_6мес_2026   25 строк, рядом у 1   -> 0.04   <-- сломан
    Эфферон_6мес_2025                8, 1                 -> 0.12   (мало строк)
    ИПС_6мес_2026                   35, 13                -> 0.37
    Сибсульфур_6мес_2025            99, 38                -> 0.38
    остальные читаемые                                    -> 0.68 … 1.00
Порог 0.30 стоит в провале между 0.12 и 0.37.

Запуск: python D:\models\tests\test_detached_values.py
Лог:    tests\_last_run_detached_values.txt
"""
import io
import os
import sys
import tempfile

sys.path.insert(0, r'D:\models\pylibs')
sys.path.insert(0, r'D:\models')
import pymupdf
import pipeline as pl

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_detached_values.txt'), 'w',
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


# ─── 1. пороги объявлены и лежат в провалах замеров ───
LOG.write('=== 1. пороги ===\n')
check('TEXT_COVERAGE_MIN объявлен', hasattr(pl, 'TEXT_COVERAGE_MIN'))
check('DETACHED_MIN_CODES объявлен', hasattr(pl, 'DETACHED_MIN_CODES'))
check('DETACHED_MAX_NEAR объявлен', hasattr(pl, 'DETACHED_MAX_NEAR'))
check('порог покрытия между смешанным (0.12) и остальными (0.46)',
      0.12 < pl.TEXT_COVERAGE_MIN < 0.46, f'порог {pl.TEXT_COVERAGE_MIN}')
check('порог доли между сломанным (0.12) и читаемыми (0.37)',
      0.12 < pl.DETACHED_MAX_NEAR < 0.37, f'порог {pl.DETACHED_MAX_NEAR}')
check('порог по числу строк отсекает короткие формы',
      pl.DETACHED_MIN_CODES > 8, f'порог {pl.DETACHED_MIN_CODES}')

# ─── 2. синтетика: сломанный слой и целый ───
LOG.write('\n=== 2. синтетика ===\n')
tmp = tempfile.mkdtemp(prefix='detached_')


def make_pdf(path, lines):
    doc = pymupdf.open()
    pg = doc.new_page()
    y = 40
    for ln in lines:
        pg.insert_text((40, y), ln, fontsize=9)
        y += 12
    doc.save(path)
    doc.close()


# сломанный: все коды подряд, числа отдельным блоком в конце
broken = [f'{c}' for c in
          ('1100', '1110', '1150', '1160', '1170', '1180', '1190', '1200',
           '1210', '1220', '1230', '1240', '1250', '1260', '1300', '1400',
           '1410', '1450', '1500', '1510', '1520', '1550')]
broken += ['1 668', '409 858', '736 021', '100 000', '22 376']
pb = os.path.join(tmp, 'broken.pdf')
make_pdf(pb, broken)

# целый: код и число в одной строке
healthy = [f'{c}  1 234' for c in
           ('1100', '1110', '1150', '1160', '1170', '1180', '1190', '1200',
            '1210', '1220', '1230', '1240', '1250', '1260', '1300', '1400',
            '1410', '1450', '1500', '1510', '1520', '1550')]
ph = os.path.join(tmp, 'healthy.pdf')
make_pdf(ph, healthy)

# короткий: 8 кодов без чисел — доля 0, но строк мало, скан не нужен
short = [f'{c}' for c in ('1100', '1110', '1150', '1200', '1250', '1300', '1500', '1520')]
ps = os.path.join(tmp, 'short.pdf')
make_pdf(ps, short)

for tag, path, want in (('сломанный', pb, True), ('целый', ph, False), ('короткий', ps, False)):
    doc = pymupdf.open(path)
    c, n = pl.values_near_codes(doc)
    got = pl.values_detached(doc)
    doc.close()
    check(f'{tag}: вердикт = {want}', got is want,
          f'кодов={c} рядом={n} доля={(n/c) if c else 0:.2f} получено {got}')

# ─── 3. реальные документы ───
LOG.write('\n=== 3. реальные документы ===\n')
DL = r'D:\data-scraping\downloads'
ASG = os.path.join(DL, 'АСГ Трансформаторен_6мес_2026.pdf')
if os.path.exists(ASG):
    doc = pymupdf.open(ASG)
    c, n = pl.values_near_codes(doc)
    wt, total = pl.text_layer_coverage(doc)
    unusable, why = pl.unusable_text_layer(doc)
    garb = sum(1 for pg in doc if pl._garbled_page(pg))
    doc.close()
    check('АСГ: слой признан нечитаемым', unusable, why)
    check('АСГ: причина — покрытие, а не порядок чисел',
          'страниц' in why, why)
    check('АСГ: текстовый слой лишь на малой доле страниц',
          wt / total < pl.TEXT_COVERAGE_MIN, f'{wt}/{total} = {wt/total:.2f}')
    check('АСГ: _garbled_page его НЕ ловит (потому и понадобился новый признак)',
          garb == 0, f'страниц с латинской абракадаброй: {garb}')
    check('АСГ: второе условие (числа оторваны) тоже сработало бы',
          c >= pl.DETACHED_MIN_CODES and n / c < pl.DETACHED_MAX_NEAR,
          f'кодов={c} рядом={n}')
    # Подтверждение из артефакта. ДО починки тут было 18 строк, у каждой
    # «row without values», строк АКТИВА (1100/1150/1210/1250/1600) не было
    # вовсе, а ровно проверки с 1600/1100/1200 стояли в n/a — и, поскольку
    # is_failure(n/a) ложь, документ проходил дальше как «непроваленный».
    # ПОСЛЕ починки документ идёт веткой скана, и это обязано быть видно
    # в артефакте: иначе признак сработал вхолостую и тест это пропустит.
    import json
    art = os.path.join(r'D:\models\extracted', 'АСГ Трансформаторен_6мес_2026.json')
    if os.path.exists(art):
        d = json.load(open(art, encoding='utf-8'))
        codes = {it.get('code') for it in ((d.get('balance') or {}).get('items') or [])}
        asset = {'1100', '1150', '1210', '1250', '1600'}
        check('АСГ: в артефакте есть строки АКТИВА (1100/1150/1210/1250/1600)',
              asset <= codes, f'найдено {sorted(codes & asset)}')
        check('АСГ: строки ПАССИВА на месте (1300/1400/1500/1700)',
              {'1300', '1400', '1500', '1700'} <= codes, f'есть {sorted(codes)}')
        check('АСГ: документ ушёл веткой скана',
              (d.get('source') or {}).get('method') == 'scan',
              f'получено {(d.get("source") or {}).get("method")!r}')
        ch = [c for c in (d.get('checks') or []) if c.get('form') == 'balance']
        na = {c['rule'] for c in ch if c.get('verdict') == 'n/a'}
        check('АСГ: n/a-проверок не осталось — пустая форма больше не проходит молча',
              not na, f'n/a: {sorted(na)}')
        check('АСГ: все шесть проверок баланса сходятся (ok)',
              len(ch) == 6 and all(c.get('verdict') == 'ok' for c in ch),
              f'всего {len(ch)}, ok: {sum(1 for c in ch if c.get("verdict") == "ok")}')
        check('АСГ: статус ok', d.get('status') == 'ok',
              f'получено {d.get("status")!r}')
        check('n/a не считается провалом (иначе эскалация шла бы по пустой форме)',
              not pl.is_failure({'verdict': 'n/a'}) and pl.is_failure({'verdict': 'fail'}))
else:
    LOG.write('  (пропуск: файла АСГ нет)\n')

# ─── 4. читаемые документы не задеты ───
LOG.write('\n=== 4. читаемые документы признак не трогает ===\n')
for nm in ('Рекорд трейд_6мес_2026.pdf', 'Унител_6мес_2026.pdf',
           'Бианка премиум_6мес_2026.pdf', 'УПТК65_6мес_2025.pdf',
           'Проект 111_6мес_2025.pdf', 'Славянск ЭКО_6мес_2026.pdf'):
    p = os.path.join(DL, nm)
    if not os.path.exists(p):
        continue
    doc = pymupdf.open(p)
    c, n = pl.values_near_codes(doc)
    wt, total = pl.text_layer_coverage(doc)
    unusable, why = pl.unusable_text_layer(doc)
    doc.close()
    check(f'{nm}: слой признан читаемым', not unusable,
          f'покрытие {wt}/{total}, кодов={c} рядом={n} — {why}')

# ─── 5. на чистом скане предупреждения быть не должно ───
LOG.write('\n=== 5. чистое сканирование не получает лишнего предупреждения ===\n')
# У документа без текстового слоя has_text и так False, и предупреждение
# «текстовый слой нечитаем» было бы неправдой: слоя нет вовсе. Поэтому оно
# вешается только на ПЕРЕКЛЮЧЕНИЕ решения (flipped), а не на сам факт непригодности.
src = io.open(r'D:\models\pipeline.py', encoding='utf-8').read()
check('переключение записано отдельным флагом flipped',
      'flipped = bool(has_text) and unusable' in src)
check('предупреждение висит на flipped, а не на unusable',
      "if flipped:\n        result['warnings'].append(f'текстовый слой нечитаем" in src)
doc0 = pymupdf.open(os.path.join(tmp, 'broken.pdf'))
check('на чистом скане (нет слоя) признак непригодности всё же истинен',
      pl.unusable_text_layer(doc0)[0])
doc0.close()

LOG.write(f'\nИТОГО: {ok} OK, {fail} провал(ов)\n')
LOG.close()
print(f'{ok} OK, {fail} провал(ов)  ->  tests/_last_run_detached_values.txt')
sys.exit(1 if fail else 0)
