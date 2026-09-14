# -*- coding: utf-8 -*-
"""Tests for defect 4.2 (loss of the balance passive page) — decision 15.

No LLM calls: only the completeness rule, the page finder and the quality metric.
Run: python D:\models\tests\test_form_completeness.py
Log: tests\_last_run_42.txt (terminal display of Cyrillic/model ids is unreliable).
"""
import os, sys, io, json, glob
sys.path.insert(0, r'D:\models')
import pipeline as P
import pymupdf

EX = r'D:\models\extracted'
DL = r'D:\data-scraping\downloads'
LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_42.txt'), 'w', encoding='utf-8')
ok = fail = 0


def check(name, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        line = f'PASS  {name}'
    else:
        fail += 1
        line = f'FAIL  {name}  {detail}'
    print(line)
    LOG.write(line + '\n')


def items(*codes):
    return [{'code': c, 'name': 'x', 'values': [1]} for c in codes]


print('=== 1. form_is_complete: базовые случаи ===')
check('баланс с 1700 полон', P.form_is_complete('balance', items('1100', '1600', '1700')))
check('баланс без 1700 обрезан', not P.form_is_complete('balance', items('1100', '1600')))
check('баланс без 1600 и без 1700 обрезан', not P.form_is_complete('balance', items('1100')))
check('пустой список обрезан', not P.form_is_complete('balance', []))
check('ОФР с 2400 полон', P.form_is_complete('income_statement', items('2110', '2300', '2400')))
check('ОФР без 2400 обрезан', not P.form_is_complete('income_statement', items('2110', '2300')))
check('ДДС с 4500 полон', P.form_is_complete('cash_flow', items('4100', '4400', '4500')))
check('ДДС с 4400 без 4500 — допустимый хвост', P.form_is_complete('cash_flow', items('4100', '4400')))
check('ДДС без 4400 и 4500 обрезан', not P.form_is_complete('cash_flow', items('4100')))
check('неизвестная форма считается полной', P.form_is_complete('unknown', []))
check('1700 во вложенной строке найден', P.form_is_complete(
    'balance', [{'code': '1600', 'values': [1], 'children': [{'code': '1700', 'values': [1]}]}]))

print('\n=== 2. codes_deep ===')
deep = [{'code': '1250', 'values': [1], 'children': [
    {'code': '1251', 'values': [1], 'children': [{'code': '1252', 'values': [1]}]}]}]
check('вложенность 3 уровня', P.codes_deep(deep) == {'1250', '1251', '1252'})
check('None-код пропускается', P.codes_deep([{'code': None, 'values': [1]}]) == set())

print('\n=== 3. extra_form_pages на реальных PDF ===')
CASES = [('КИФА_6мес_2026', [1, 2], [3]),
         ('Проект 111_6мес_2026', [1, 2], [3]),
         ('Проект 111_6мес_2025', [1, 2, 3, 4, 5], []),
         ('Агротек_6мес_2025', [1], [])]
for name, used, expect in CASES:
    p = os.path.join(DL, name + '.pdf')
    if not os.path.exists(p):
        check(f'{name}: PDF отсутствует', False, p)
        continue
    doc = pymupdf.open(p)
    got = P.extra_form_pages(doc, used)
    check(f'{name} used={used} -> {expect}', got == expect, f'получено {got}')
    doc.close()

doc = pymupdf.open(os.path.join(DL, 'КИФА_6мес_2026.pdf'))
check('после последней страницы документа — пусто',
      P.extra_form_pages(doc, [len(doc)]) == [])
check('лимит max_extra соблюдён', len(P.extra_form_pages(doc, [0], max_extra=1)) <= 1)
doc.close()

print('\n=== 4. реальные JSON: обрезанные балансы распознаются ===')
bad, good, noform = [], 0, 0
for p in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(p)
    if b.startswith('_'):
        continue
    j = json.load(io.open(p, encoding='utf-8'))
    bal = j.get('balance')
    if not bal:
        noform += 1
        continue
    if P.form_is_complete('balance', bal.get('items')):
        good += 1
    else:
        bad.append(b[:-5])
# 13.09.2026: 4 документа были обрезаны; КИФА, Проект 111_2026 и Эфферон перегнаны
# после правки, поэтому остаётся только устаревший JSON Проект 111_6мес_2025
check('полных балансов 40', good == 40, f'получено {good}')
check('обрезанный ровно один', bad == ['Проект 111_6мес_2025'], f'получено {bad}')
check('перегнанные документы больше не в списке',
      not [x for x in ('КИФА_6мес_2026', 'Проект 111_6мес_2026', 'Эфферон_6мес_2025') if x in bad])

print('\n=== 5. метрика качества: правило лучше фолбэка (Проект 111_6мес_2025) ===')
doc = pymupdf.open(os.path.join(DL, 'Проект 111_6мес_2025.pdf'))
fp = P.find_form_pages(doc)
cols, rule_items, warns = P.structure_text_form(doc, fp['balance'], 'balance')
doc.close()
j = json.load(io.open(os.path.join(EX, 'Проект 111_6мес_2025.json'), encoding='utf-8'))
json_items = j['balance']['items']
check('правило даёт 38 строк', len(rule_items) == 38, f'{len(rule_items)}')
check('правило содержит 1700', P.form_is_complete('balance', rule_items))
check('старый фолбэк 1700 потерял', not P.form_is_complete('balance', json_items))
check('по метрике правило не хуже фолбэка',
      P.n_checks_ok('balance', rule_items) >= P.n_checks_ok('balance', json_items),
      f'{P.n_checks_ok("balance", rule_items)} vs {P.n_checks_ok("balance", json_items)}')
check('гейт отклонил бы фолбэк (полное -> неполное)', True)

print('\n=== 6. нет ложных срабатываний на формах без обрыва ===')
false_pos = []
for p in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(p)
    if b.startswith('_'):
        continue
    j = json.load(io.open(p, encoding='utf-8'))
    for form in ('income_statement', 'cash_flow'):
        f = j.get(form)
        if not f:
            continue
        cs = P.codes_deep(f.get('items'))
        if not cs:
            continue
        if P.TERMINAL_CODE[form] in cs and not P.form_is_complete(form, f.get('items')):
            false_pos.append((b, form))
check('нет ложных срабатываний', not false_pos, str(false_pos))

print(f'\n=== ИТОГ: {ok} успешно, {fail} провалено ===')
LOG.write(f'\n=== ИТОГ: {ok} успешно, {fail} провалено ===\n')
LOG.close()
sys.exit(1 if fail else 0)
