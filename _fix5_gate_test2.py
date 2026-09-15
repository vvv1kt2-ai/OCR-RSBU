# -*- coding: utf-8 -*-
r"""Проверка гейтов правки 5 на НАСТОЯЩЕМ коде, без оплаты.

Прошлая попытка была неубедительной: артефакты уже были в состоянии «после эскалации»,
менять было нечего. Поэтому здесь я:

  1. откатываю артефакт ТГК-14 в состояние ДО эскалации (1250 = 11081647) — именно так
     выглядел документ, когда эскалация его испортила;
  2. подсовываю эскалации ровно то, что она тогда вернула (1250 = 11061647);
  3. смотрю, применит ли её гейт.

Ожидание: гейт 2 (регрессия проверок) должен ОТКЛОНИТЬ правку, потому что до неё
правило 1200 сходится точно, а после — расходится на 20000.

Платные вызовы запрещены: chat() подменён на исключение.
"""
import io, os, json, sys, copy

sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
SRC = r'D:\data-scraping\downloads'


class PaidCall(Exception):
    pass


P.chat = lambda *a, **k: (_ for _ in ()).throw(PaidCall('платный вызов'))

stem, form = 'ТГК-14_6мес_2025', 'balance'
path = None
for root, _, files in os.walk(SRC):
    for fn in files:
        if os.path.splitext(fn)[0] == stem:
            path = os.path.join(root, fn)

saved = json.load(io.open(os.path.join(EX, stem + '.json'), encoding='utf-8'))


def item(items, code):
    for it in items:
        if it.get('code') == code:
            return it


print('=' * 78)
print('СОСТОЯНИЕ АРТЕФАКТА (как есть на диске)')
res = copy.deepcopy(saved)
it = item(res[form]['items'], '1250')
print('  1250 = %s   (ocr1 = %s, corrected_by = %s)'
      % (it.get('values'), it.get('values_ocr1'), 'да' if it.get('corrected_by') else 'нет'))
ok_before = P.n_checks_ok(form, res[form]['items'])
print('  проверок проходит: %d' % ok_before)

print()
print('=' * 78)
print('ТЕСТ: откатываю значение к состоянию ДО эскалации и запускаю её заново')
res2 = copy.deepcopy(saved)
it2 = item(res2[form]['items'], '1250')
# состояние до эскалации: значение, которое стояло в документе изначально
it2['values'] = list(it2['values_ocr1'])
it2.pop('corrected_by', None)
it2.pop('confirmed_by', None)
it2.pop('values_ocr1', None)
print('  откатил: 1250 = %s' % it2['values'])
ok_rollback = P.n_checks_ok(form, res2[form]['items'])
print('  проверок проходит теперь: %d  (правило 1200 сходится точно)' % ok_rollback)

# эскалация должна вернуть ровно то, что вернула тогда: 1250 -> 11061647
orig = P.cached_llm
fake_llm = {'columns': [{'label': 'На 30.06.2025'}, {'label': 'На 31.12.2024'}, {'label': 'На 31.12.2023'}],
            'items': [{'code': '1250', 'name': 'Краткосрочные финансовые вложения',
                       'values': [11061647, 2658055, 4905033]}]}
P.cached_llm = lambda tag, fn: fake_llm
P.llm_structure_form = lambda *a, **k: (fake_llm, None)
P._normalize_llm = lambda llm, fk: llm['items']
P.identity_guard = lambda *a, **k: (True, 'тест: проверка личности отключена')
P.sibling_conflicts = lambda *a, **k: []

warnings = []
doc = P.pymupdf.open(path)
try:
    P.escalate_failed_form(doc, form, res2, warnings, name=os.path.basename(path))
except PaidCall as e:
    print('  ОШИБКА: код полез в платный вызов — %s' % e)
finally:
    doc.close()

it3 = item(res2[form]['items'], '1250')
print()
print('  РЕЗУЛЬТАТ:')
print('    1250 = %s' % it3['values'])
print('    corrected_by = %s' % ('ЕСТЬ (правка применена)' if it3.get('corrected_by') else 'нет (правка не применена)'))
print('    проверок проходит: %d' % P.n_checks_ok(form, res2[form]['items']))
print('    предупреждения:')
for w in warnings:
    print('       %s' % w[:200])
print()
applied = bool(it3.get('corrected_by')) and it3['values'][0] == 11061647
print('ВЕРДИКТ: порча %s' % ('ПРИМЕНЕНА — гейт не сработал' if applied else 'ОТКЛОНЕНА — гейт сработал'))
print('=' * 78)
