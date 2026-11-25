# -*- coding: utf-8 -*-
r"""Тест выбора страниц формы: шаг назад не должен уходить на ЧУЖУЮ форму.

Что было сломано (измерено, а не предположено):
  `find_form_pages` после разбора формы делает «шаг назад» — добирает предыдущую
  страницу, если на ней есть признак формы. Для ОДДС признаком считалось в том
  числе голое «Наименование показателя», которое стоит в шапке ЛЮБОЙ формы. Поэтому
  шаг назад дважды заходил на «Отчёт об изменениях капитала» (форма 0710004) —
  она опознавалась только по заголовку, а в текстовом слое заголовка нет, есть
  колонтитул «Форма 0710004 с. 2».

Последствия, которые и проверяются:
  1. в список страниц ОДДС попадали две страницы чужой формы;
  2. `detect_columns` читал шапку ЧУЖОЙ формы и выдавал колонки
     ['2025-06-30', '2025-12-31'] для документа 2026 года;
  3. свод по этим колонкам ставил числа 2026 года в колонку 2025;
  4. в items ОДДС попадал мусорный код 3211 со склейкой строк капитала.

Тест держит и признак в исходнике, и результат на реальных PDF. Без вызовов модели.

Запуск: python D:\models\tests\test_form_pages_foreign.py
Лог:    tests\_last_run_form_pages.txt
"""
import io
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, r'D:\models\pylibs')
sys.path.insert(0, r'D:\models')
import fitz
import pipeline as P
sys.path.insert(0, r'D://models//tests')
import _pdfpath

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_form_pages.txt'), 'w',
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


DL = Path(r'D:\data-scraping\downloads')
EXTRACTED = Path(r'D:\models\extracted')
FOREIGN = ('0710003', '0710004', '0710006')
OWN = {'balance': '0710001', 'income_statement': '0710002', 'cash_flow': '0710005'}

# документы, у которых список страниц ОДДС (или ОФР) был испорчен чужими страницами
AFFECTED = {
    'Бианка премиум_6мес_2025': ('cash_flow', [8, 9]),
    'Бианка премиум_6мес_2026': ('cash_flow', [10, 11]),
    'Проект 111_6мес_2025': ('cash_flow', [9, 10]),
    'Сибсульфур_6мес_2025': ('cash_flow', [9, 10]),
    'Унител_6мес_2026': ('cash_flow', [7, 8]),
    'Урожай_6мес_2026': ('cash_flow', [11, 12]),
    'Рекорд трейд_6мес_2026': ('cash_flow', [7, 8]),
    'АСГ Трансформаторен_6мес_2026': ('income_statement', [8]),
}

# ─── 1. признак в исходнике ───
src = io.open(r'D:\models\pipeline.py', encoding='utf-8').read()
check('в pipeline.py объявлены коды чужих форм',
      'FOREIGN_FORM_CODES' in src and '0710004' in src)
check('шаг назад отказывается заходить на страницу чужой формы',
      'any(fc in t for fc in FOREIGN_FORM_CODES)' in src)
check('голое «Наименование показателя» больше НЕ признак ОДДС',
      "'cash_flow': ('сальдо' in tl or 'Наименование показателя' in t)" not in src)
check('голое «Наименование показателя» больше НЕ признак ОФР',
      "'income_statement': ('выручка' in tl or 'Наименование показателя' in t)" not in src)

# ─── 2. реальные PDF: чужой страницы в списке быть не должно ───
LOG.write('\n=== 2. известные пострадавшие документы ===\n')
for stem, (form, was_foreign) in sorted(AFFECTED.items()):
    _pp = _pdfpath.pdf_path(f'{stem}.pdf')
    pdf = Path(_pp) if _pp else (DL / f'{stem}.pdf')
    if not pdf.exists():
        check(f'{stem}: PDF на месте', False, str(pdf))
        continue
    doc = fitz.open(pdf)
    fp = P.find_form_pages(doc)
    pages = list(fp.get(form) or [])
    texts = {p: doc[p - 1].get_text() for p in pages}
    doc.close()

    intruders = [p for p in pages if any(f in texts[p] for f in FOREIGN)]
    check(f'{stem}: в списке {form} нет страниц чужой формы', not intruders,
          f'чужие страницы: {intruders}')
    for p in was_foreign:
        check(f'{stem}: снята страница {p} (там действительно 0710004)',
              p not in pages, f'осталась, список={pages}')
    check(f'{stem}: {form} всё ещё непустой', bool(pages), f'список={pages}')
    check(f'{stem}: страницы {form} несут свой код {OWN[form]}',
          all(OWN[form] in texts[p] for p in pages),
          f'без своего кода: {[p for p in pages if OWN[form] not in texts[p]]}')

# ─── 3. сплошная проверка по всем документам с артефактами ───
LOG.write('\n=== 3. сплошная проверка ===\n')
def find_pdf(stem, period, year):
    """PDF документа: сначала в корне загрузок, затем в archive/ по подпапкам.

    Зачем искать в архиве. Файлы разложены по периодам (`archive/6мес_2025/` и т. д.),
    и корень `downloads` содержит только текущую выгрузку. Пока проверка смотрела лишь
    в корень, она молча пропускала всё уехавшее в архив — а условие «проверены все
    документы с артефактами» на этом не выполнялось (найдено 17 вместо 60+). Это дефект
    ОХВАТА теста, а не кода: сам критерий (нет страниц чужой формы) проверялся верно.
    """
    direct = DL / f'{stem}_{period}_{year}.pdf'
    if direct.exists():
        return direct
    for cand in (DL / 'archive').rglob(f'{stem}_{period}_{year}.pdf'):
        return cand
    return None


seen = 0
dirty = []
for p in sorted(EXTRACTED.glob('*_6мес_*.json')):
    m = re.match(r'^(.*)_6мес_(\d{4})\.json$', p.name)
    if not m:
        continue
    pdf = find_pdf(m.group(1), '6мес', m.group(2))
    if pdf is None:
        continue
    seen += 1
    doc = fitz.open(pdf)
    fp = P.find_form_pages(doc)
    for form in ('balance', 'income_statement', 'cash_flow'):
        for pg in (fp.get(form) or []):
            t = doc[pg - 1].get_text()
            if OWN[form] in t:
                continue
            if any(f in t for f in FOREIGN):
                dirty.append(f'{p.name}:{form}:стр{pg}')
    doc.close()

check('проверены все документы с артефактами', seen >= 60, f'проверено {seen}')
check('ни у одного документа нет страниц чужой формы в списке', not dirty,
      f'найдено: {dirty[:8]}')

# ─── 4. колонки ОДДС трёх документов-2026 называют СВОЙ год ───
LOG.write('\n=== 4. колонки ОДДС после правки ===\n')
for stem in ('Бианка премиум_6мес_2026', 'Унител_6мес_2026', 'Урожай_6мес_2026'):
    art = EXTRACTED / f'{stem}.json'
    if not art.exists():
        check(f'{stem}: артефакт на месте', False)
        continue
    d = json.load(open(art, encoding='utf-8'))
    cf = d.get('cash_flow') or {}
    cols = [str(c) for c in (cf.get('columns') or [])]
    check(f'{stem}: колонки ОДДС называют 2026', any('2026' in c for c in cols),
          f'columns={cols}')
    check(f'{stem}: колонки ОДДС называют 2025', any('2025' in c for c in cols),
          f'columns={cols}')
    check(f'{stem}: мусорный код 3211 в ОДДС отсутствует',
          not any(str(it.get('code')) == '3211' for it in (cf.get('items') or [])),
          f'коды={[it.get("code") for it in (cf.get("items") or [])][:5]}')

LOG.write(f'\nИТОГ: успешно {ok}, провалов {fail}\n')
LOG.close()
print(f'успешно {ok}, провалов {fail} (лог: tests/_last_run_form_pages.txt)')
sys.exit(1 if fail else 0)
