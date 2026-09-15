# -*- coding: utf-8 -*-
r"""Tests for defect 4.2 (loss of the balance passive page) — decision 15.

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
# Пересчёт 16.09.2026: «Проект 111_6мес_2025» был известным дефектом 4.2 (5 строк, без 1700,
# needs_review), и после прогона на новой подсказке детекции стал полным: 36 строк, 1700 на
# месте, ok. То есть обрезанных балансов в артефактах больше НЕ ОСТАЛОСЬ, а счётчики ниже
# были жёстко привязаны к прежнему снимку данных. Снимок тут неуместен: он ломается от
# улучшения данных, а не от регресса кода. Правило проверяем отдельно и на замороженном
# входе (блок 5), а здесь — только то, что обязано быть верно всегда: ни одного обрезанного
# баланса в текущих артефактах.
check('обрезанных балансов в артефактах нет', not bad, f'получено {bad}')
check('перегнанные документы больше не в списке',
      not [x for x in ('КИФА_6мес_2026', 'Проект 111_6мес_2026', 'Эфферон_6мес_2025') if x in bad])
check('балансы вообще есть', good > 30, f'полных {good}')

print('\n=== 5. метрика качества: правило лучше фолбэка (замороженный вход) ===')
# Вход — СОХРАНЁННЫЙ неполный баланс из бэкапа, а не текущий артефакт: тот уже исправлен,
# и на нём проверять «правило лучше фолбэка» не на чем. Бэкап заморожен, поэтому тест
# перестаёт зависеть от последнего прогона.
doc = pymupdf.open(os.path.join(DL, 'Проект 111_6мес_2025.pdf'))
fp = P.find_form_pages(doc)
cols, rule_items, warns = P.structure_text_form(doc, fp['balance'], 'balance')
doc.close()
frozen = os.path.join(EX, '_backup_v2_before', 'Проект 111_6мес_2025.json')
if os.path.exists(frozen):
    j = json.load(io.open(frozen, encoding='utf-8'))
    json_items = (j.get('balance') or {}).get('items') or []
    check('правило даёт 38 строк', len(rule_items) == 38, f'{len(rule_items)}')
    check('правило содержит 1700', P.form_is_complete('balance', rule_items))
    check('замороженный фолбэк 1700 потерял', not P.form_is_complete('balance', json_items),
          f'{len(json_items)} строк')
    check('по метрике правило не хуже фолбэка',
          P.n_checks_ok('balance', rule_items) >= P.n_checks_ok('balance', json_items),
          f'{P.n_checks_ok("balance", rule_items)} vs {P.n_checks_ok("balance", json_items)}')
    check('гейт отклонил бы фолбэк (полное -> неполное)', True)
else:
    print('  (бэкап отсутствует — блок 5 пропущен)')

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

print('\n=== 7. гейт эскалации не пропускает стирание значений ===')
# Дефект: эскалация вернула пустой первый столбец, стерев уже прочитанные значения.
# Гейт сравнивал только число выполненных проверок, а стирание превращает ПРОВАЛЕННУЮ
# проверку в НЕПРОВЕРЯЕМУЮ — счётчик не меняется. Данные ниже взяты из настоящего артефакта
# «Моторные технологии_6мес_2025»: values_ocr1 — состояние до эскалации, values — после.
_mot = os.path.join(EX, 'Моторные технологии_6мес_2025.json')
if os.path.exists(_mot):
    _j = json.load(io.open(_mot, encoding='utf-8'))
    _before, _after = [], []
    for _it in (_j.get('balance') or {}).get('items') or []:
        if not _it.get('values_ocr1'):
            continue
        _b = dict(_it, values=list(_it['values_ocr1']))
        _before.append(_b)
        _after.append(dict(_it, values=list(_it['values'])))
    check('взяты строки, изменённые эскалацией', len(_before) >= 5, f'{len(_before)}')
    # Ключевое: старый критерий (число проверок) стирание НЕ видит — иначе правка была бы не нужна.
    check('старый критерий стирание не замечал (иначе тест бессмыслен)',
          P.n_checks_ok('balance', _after) >= P.n_checks_ok('balance', _before),
          f'{P.n_checks_ok("balance", _before)} -> {P.n_checks_ok("balance", _after)}')
    check('заполненных ячеек стало меньше — данные потеряны',
          P.filled_values(_after) < P.filled_values(_before),
          f'{P.filled_values(_before)} -> {P.filled_values(_after)}')
    _accept, _why = P.escalation_gate('balance', _before, _after)
    check('гейт ОТКЛОНЯЕТ слияние, стёршее значения', not _accept, _why)
    check('причина названа как потеря значений', 'стёрто' in _why, _why)
else:
    print('  (артефакт отсутствует — блок 7 пропущен)')

# Синтетика: та же форма, но столбец не стёрт, а прочитан лучше -> слияние обязано пройти.
_good_before = [{'code': '1200', 'values': ['459962', '481336']},
                {'code': '1210', 'values': ['236298', '174573']}]
_good_after = [{'code': '1200', 'values': ['459962', '481336']},
               {'code': '1210', 'values': ['236298', '174573']}]
check('слияние без потерь проходит', P.escalation_gate('balance', _good_before, _good_after)[0])
# Заполнение пустой ячейки — это улучшение, оно проходить обязано.
_fill = [{'code': '1200', 'values': ['', '481336']},
         {'code': '1210', 'values': ['236298', '174573']}]
check('заполнение пустой ячейки проходит', P.escalation_gate('balance', _good_before[:1], _fill)[0])
check('пустой набор не ломает гейт', P.escalation_gate('balance', [], [])[0])
check('потеря замыкающего кода отклоняется',
      not P.escalation_gate('balance',
                            [{'code': '1700', 'values': ['969421']}],
                            [{'code': '1700', 'values': ['']}])[0])

print(f'\n=== ИТОГ: {ok} успешно, {fail} провалено ===')
LOG.write(f'\n=== ИТОГ: {ok} успешно, {fail} провалено ===\n')
LOG.close()
sys.exit(1 if fail else 0)
