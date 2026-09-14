# -*- coding: utf-8 -*-
"""Tests for defect 4.3 (lease obligation inside 1520 counted twice) — the свод rule.

Checks the свод's 1450/1550 result for every document against the gold xlsx.
No LLM calls. Run: python D:\\models\\tests\\test_rent_rule.py
Log: tests\\_last_run_43.txt
"""
import os, sys, io, json, glob, re
sys.path.insert(0, r'D:\models')
sys.path.insert(0, r'D:\models\pylibs')
import svod
import openpyxl

EX = r'D:\models\extracted'
LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_43.txt'), 'w', encoding='utf-8')
ok = fail = 0


def check(name, cond, detail=''):
    global ok, fail
    line = f'{"PASS" if cond else "FAIL"}  {name}' + (f'  {detail}' if not cond and detail else '')
    print(line)
    LOG.write(line + '\n')
    if cond: ok += 1
    else: fail += 1


def rent_cells(doc):
    """что свод положит в 1450 и 1550 для этого документа"""
    j = json.load(io.open(os.path.join(EX, doc + '.json'), encoding='utf-8'))
    bal = j.get('balance')
    if not bal:
        return None
    svod.mark_chains(bal)
    year = 2026 if '2026' in doc else 2025
    idx = svod.col_index_balance(bal, year)
    if idx is None:
        return None

    def v_of(it):
        v = it.get('values') or []
        return v[idx] if idx < len(v) else None

    def top(code):
        lst = [it for it in (bal.get('items') or []) if it.get('code') == code]
        return lst[-1] if lst else None

    long_v, short_v, notes, susp = svod.rent_extract(bal, idx)
    b1550 = v_of(top('1550')) if top('1550') else None
    b1450 = v_of(top('1450')) if top('1450') else None
    r1550 = (b1550 or 0) + short_v if short_v is not None else b1550
    r1450 = (b1450 or 0) + long_v if long_v is not None else b1450
    return {'1550': r1550, '1450': r1450, 'susp': susp, 'notes': notes,
            'short': short_v, 'long': long_v, 'base1550': b1550, 'base1450': b1450}


print('=== 1. Разбор конкретного случая: Моторные технологии_6мес_2025 ===')
r = rent_cells('Моторные технологии_6мес_2025')
check('1550 = 9410 (эталон), а не 9643', r['1550'] == 9410, f'получено {r["1550"]}')
check('аренда из 1520 не прибавлена', r['short'] is None, f'short={r["short"]}')
check('в замечаниях записано, почему не прибавлена',
      any('1550 уже содержит аренду' in n for n in r['notes']), str(r['notes']))

print('\n=== 2. Правило не сломало остальные случаи аренды ===')
CASES = [('КИФА_6мес_2026', 1550, 37732, 'аренда из 1520 -> 1550'),
         ('КИФА_6мес_2025', 1550, 51460, 'аренда из 1520 -> 1550'),
         ('Бианка премиум_6мес_2025', 1550, 182716, 'аренда из 1520 -> 1550'),
         ('Эфферон_6мес_2025', 1550, 26971, 'аренда из 1520 -> 1550'),
         ('Сибсульфур_6мес_2025', 1550, 21622, 'аренда на верхнем уровне -> 1550'),
         ('Рекорд трейд_6мес_2026', 1550, 20744, 'аренда внутри 1550, не плюсуется'),
         ('ТГК-14_6мес_2026', 1550, 498191, 'нет аренды, только база'),
         ('Моторные технологии_6мес_2025', 1450, 8287, 'долгосрочная аренда внутри 1450')]
for doc, code, want, why in CASES:
    rc = rent_cells(doc)
    check(f'{doc} {code} = {want} ({why})', rc and rc[str(code)] == want,
          f'получено {rc and rc.get(str(code))}')

print('\n=== 3. Синтетика: 1550 со своей арендой блокирует аренду из 1520 ===')
bal = {'columns': ['На 30 июня 2026 г.'], 'items': [
    {'code': '1520', 'name': 'Кредиторская задолженность', 'values': [1000], 'children': [
        {'code': None, 'name': 'Расчеты по обязательствам по аренде', 'values': [233]}]},
    {'code': '1550', 'name': 'Прочие обязательства', 'values': [9410], 'children': [
        {'code': None, 'name': 'Краткосрочные обязательства по аренде', 'values': [9410]}]}]}
svod.mark_chains(bal)
lng, sht, notes, susp = svod.rent_extract(bal, 0)
check('аренда из 1520 не сложена', sht is None, f'short={sht}')

bal2 = {'columns': ['На 30 июня 2026 г.'], 'items': [
    {'code': '1520', 'name': 'Кредиторская задолженность', 'values': [1000], 'children': [
        {'code': None, 'name': 'Расчеты по обязательствам по аренде', 'values': [233]}]}]}
svod.mark_chains(bal2)
lng2, sht2, notes2, susp2 = svod.rent_extract(bal2, 0)
check('без аренды в 1550 аренда из 1520 складывается', sht2 == 233, f'short={sht2}')

print('\n=== 4. Весь свод: 1450/1550 против эталона xlsx ===')
wb = openpyxl.load_workbook(os.path.join(EX, 'svod_2025_2026.xlsx'), data_only=True)
ws = wb[wb.sheetnames[0]]
rows = list(ws.iter_rows(values_only=True))
hdr = rows[0]
gold = {}
for r in rows[2:]:
    nm = (r[0] or '').strip() if isinstance(r[0], str) else ''
    if not nm:
        continue
    for ci in range(1, len(hdr)):
        if not hdr[ci]:
            continue
        code = str(hdr[ci]).strip().split(' ')[0].split('+')[0]
        for off, yr in ((0, '2025'), (1, '2026')):
            if ci + off < len(r):
                gold[(nm, code, yr)] = r[ci + off]

match = mism = zero = 0
bad = []
for p in sorted(glob.glob(os.path.join(EX, '*_6мес_*.json'))):
    doc = os.path.basename(p)[:-5]
    m = re.match(r'^(.*)_6мес_(\d{4})$', doc)
    if not m:
        continue
    em, yr = m.group(1), m.group(2)
    rc = rent_cells(doc)
    if not rc:
        continue
    for code in ('1550', '1450'):
        g = gold.get((em, code, yr))
        if g is None:
            continue
        g = int(g)
        v = rc[code]
        if g == 0 and v is None:
            zero += 1          # «пусто» против явного нуля — не дефект
        elif v == g:
            match += 1
        else:
            mism += 1
            bad.append((doc, code, v, g))
# Проект 111_6мес_2025 — известное исключение: его JSON от 03.09 разрушен старым
# фолбэком, перегон отложен до пилотного пакета (см. OCR_ПЛАН.md, раздел 4.2).
KNOWN = [b for b in bad if b[0] == 'Проект 111_6мес_2025']
unexpected = [b for b in bad if b[0] != 'Проект 111_6мес_2025']
check('расхождений с эталоном нет (кроме известного Проект 111_6мес_2025)',
      not unexpected, str(unexpected))
check('Проект 111_6мес_2025 всё ещё помечен как известный дефект',
      len(KNOWN) == 2, str(KNOWN))
check('совпадений не меньше 62', match >= 62, f'совпало {match}')
print(f'   совпало {match}, пусто-против-нуля {zero}, известное исключение {len(KNOWN)}, '
      f'неожиданных {len(unexpected)}')
LOG.write(f'   совпало {match}, пусто-против-нуля {zero}, '
          f'известное исключение {len(KNOWN)}, неожиданных {len(unexpected)}\n')

print(f'\n=== ИТОГ: {ok} успешно, {fail} провалено ===')
LOG.write(f'\n=== ИТОГ: {ok} успешно, {fail} провалено ===\n')
LOG.close()
sys.exit(1 if fail else 0)
