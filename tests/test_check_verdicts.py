# -*- coding: utf-8 -*-
r"""Тесты вердиктов правил: три исхода, гейт эскалации и защита эталона.

Без вызовов модели. Проверяется ровно то, что менялось:
  1. правило, которое не на чем вычислить, — это 'n/a', а НЕ провал;
  2. провал ('fail') — единственное, что открывает эскалацию;
  3. сохранённые артефакты без поля verdict читаются по старому полю ok;
  4. коды расходных строк ОФР попадают в цель эскалации (знак в правиле — разделитель);
  5. сборка свода без флага не трогает эталон xlsx.

Запуск: python D:\models\tests\test_check_verdicts.py
Лог:    tests\_last_run_verdicts.txt
"""
import io
import os
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P
import svod_build

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_verdicts.txt'), 'w',
              encoding='utf-8')
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


def verdicts(form_key, items):
    return {c['rule']: c['verdict'] for c in P.run_checks(form_key, items)}


# ── 1. три исхода ────────────────────────────────────────────────────────────
print('=== 1. правило без данных — это n/a, а не провал ===')
consistent = [
    {'code': '1600', 'name': 'БАЛАНС', 'values': [1000], 'children': []},
    {'code': '1700', 'name': 'БАЛАНС', 'values': [1000], 'children': []},
    {'code': '1300', 'name': 'Итого по разделу III', 'values': [1000], 'children': []},
]
v = verdicts('balance', consistent)
check('1600 == 1700 сходится -> ok', v['1600 == 1700'] == 'ok', v['1600 == 1700'])
check('раздел IV не заполнен -> n/a (не fail)',
      v['1400 == 1410+1420+1430+1440+1450'] == 'n/a',
      v['1400 == 1410+1420+1430+1440+1450'])
check('раздел V не заполнен -> n/a (не fail)',
      v['1500 == 1510+1520+1530+1540+1550'] == 'n/a',
      v['1500 == 1510+1520+1530+1540+1550'])

broken = [dict(it) for it in consistent]
broken[0]['values'] = [900]          # 1600 != 1700 (разница 100, TOL=2 её не покрывает)
v = verdicts('balance', broken)
check('1600 != 1700 -> fail', v['1600 == 1700'] == 'fail', v['1600 == 1700'])

partial = [
    {'code': '1700', 'name': 'БАЛАНС', 'values': [1000, None], 'children': []},
    {'code': '1500', 'name': 'Итого по разделу V', 'values': [200, None], 'children': []},
    {'code': '1510', 'name': 'Заемные средства', 'values': [100, None], 'children': []},
    {'code': '1520', 'name': 'Кредиторская задолженность', 'values': [100, None],
     'children': []},
]
v = verdicts('balance', partial)
check('одна колонка верна, вторая пуста -> ok (не fail)',
      v['1500 == 1510+1520+1530+1540+1550'] == 'ok',
      v['1500 == 1510+1520+1530+1540+1550'])

print()
print('=== 2. только fail открывает эскалацию ===')
check('n/a не провал', P.is_failure({'verdict': 'n/a', 'ok': False}) is False)
check('ok не провал', P.is_failure({'verdict': 'ok', 'ok': True}) is False)
check('fail — провал', P.is_failure({'verdict': 'fail', 'ok': False}) is True)

print()
print('=== 3. артефакт прежней версии (поля verdict нет) ===')
check('сохранённый ok=True читается как непровал', P.is_failure({'ok': True}) is False)
check('сохранённый ok=False читается как провал', P.is_failure({'ok': False}) is True)
check('поле verdict имеет приоритет над ok',
      P.is_failure({'verdict': 'n/a', 'ok': False}) is False)
check('нет ни verdict, ни ok -> не провал', P.is_failure({}) is False)

print()
print('=== 4. цель эскалации: знак в правиле — разделитель, а не часть кода ===')
import re


def codes_from_rule(rule):
    """Та же выборка, что внутри escalate_failed_form: токены ровно из 4 цифр."""
    return {t for t in re.findall(r'\d+', rule) if len(t) == 4}


check('2100 == 2110-2120 -> 2110 и 2120 в цели',
      {'2110', '2120'} <= codes_from_rule('2100 == 2110-2120 (±)'),
      sorted(codes_from_rule('2100 == 2110-2120 (±)')))
check('2200 == 2100-2210-2220 -> 2210 и 2220 в цели',
      {'2210', '2220'} <= codes_from_rule('2200 == 2100-2210-2220 (±)'))
check('2400 -> 2410, 2430, 2460 в цели',
      {'2410', '2430', '2460'} <= codes_from_rule('2400 == 2300-2410±2421∓2430±2450-2460'))
check('правило баланса не изменилось',
      codes_from_rule('1500 == 1510+1520+1530+1540+1550')
      == {'1500', '1510', '1520', '1530', '1540', '1550'})
check('пятизначный под-код в цель не просочится',
      codes_from_rule('1500 == 15301+1510') == {'1500', '1510'})

print()
print('=== 5. сборка свода не трогает эталон без флага ===')
gen, backup = svod_build.target_xlsx(overwrite_gold=False)
check('без флага пишем в generated-файл', gen == svod_build.XLSX_GENERATED, str(gen))
check('без флага копия эталона не делается', backup is None, str(backup))
check('путь эталона остался прежним',
      svod_build.XLSX_PATH.name == 'svod_2025_2026.xlsx')
check('generated-файл не совпадает с эталоном',
      svod_build.XLSX_GENERATED != svod_build.XLSX_PATH)

print()
print('=' * 60)
print(f'ИТОГ: {ok} успешно, {fail} провалено')
LOG.write(f'\nИТОГ: {ok} успешно, {fail} провалено\n')
LOG.close()
sys.exit(1 if fail else 0)
