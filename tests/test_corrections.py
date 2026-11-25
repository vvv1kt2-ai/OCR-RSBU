# -*- coding: utf-8 -*-
r"""Тесты слоя правок corrections.json.

Без вызовов модели. Проверяется ровно то, ради чего слой сделан отдельным файлом:
  1. ключ записи не зависит ни от списка отчётностей, ни от списка кодов свода;
  2. запись не перезаписывается — новое состояние ДОПИСЫВАЕТСЯ в history;
  3. правка попадает в ту же ячейку, которую читает свод (семантика svod.get_val);
  4. если строки нет вовсе — правка НЕ применяется и НЕ создаёт строку;
  5. пометка про колонку накрывает только свои коды;
  6. reconcile различает: ждёт / данные поехали / правка устарела / строки нет;
  7. артефакты на диске не меняются — это главный инвариант слоя.

Запуск: python D:\models\tests\test_corrections.py
Лог:    tests\_last_run_corrections.txt
"""
import hashlib
import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, r'D:\models')
import corrections as C

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_corrections.txt'), 'w',
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


def form(items, columns=None):
    return {'form': 'x', 'columns': columns or ['c0', 'c1'], 'items': items}


# ── 1. ключ записи ───────────────────────────────────────────────────────────
print('=== 1. ключ не зависит от списков отчётностей и кодов свода ===')
k = C.make_key('ИПС_6мес_2025', 'balance', 0, '1520')
check('ключ собирается из doc/form/column/code', k == 'ИПС_6мес_2025|balance|0|1520', k)
check('ключ разбирается обратно', C.parse_key(k) == ('ИПС_6мес_2025', 'balance', 0, '1520'))
check('отсутствующий код -> *',
      C.make_key('D', 'balance', 1, None) == 'D|balance|1|*')
check('* разбирается в None', C.parse_key('D|balance|1|*')[3] is None)
check('код вне свода живёт в ключе так же, как любой другой',
      C.parse_key(C.make_key('D', 'balance', 2, '9999'))[3] == '9999')
check('doc разбирается на эмитента и год',
      C.doc_parts('ИПС_6мес_2025') == ('ИПС', 2025))
check('неродственный стем не разбирается', C.doc_parts('что-то') == (None, None))
check('отсутствующий файл -> пустой слой',
      len(C.Corrections.load(r'D:\models\tests\_нет_такого_файла.json').entries) == 0)

# ── 2. запись не перезаписывается ────────────────────────────────────────────
print()
print('=== 2. история дописывается, а не переписывается ===')
corr = C.Corrections({}, Path(r'D:\models\tests\_tmp_corr.json'))
corr.record('D_6мес_2025', 'balance', 0, code=None, codes=['1520'], rule='r1',
            state='disputed', reason='первая пометка', source='verify',
            at='2026-09-16T10:00:00+03:00')
check('запись создана', len(corr.entries) == 1)
e = corr.entries[C.make_key('D_6мес_2025', 'balance', 0, None)]
check('история начата', len(e['history']) == 1, str(len(e['history'])))

corr.record('D_6мес_2025', 'balance', 0, code='1520', state='corrected',
            value_read=999, value_final=1000, reason='сверил с PDF',
            at='2026-09-16T11:00:00+03:00')
check('другая ячейка — отдельная запись', len(corr.entries) == 2, str(len(corr.entries)))
e2 = corr.entries[C.make_key('D_6мес_2025', 'balance', 0, '1520')]
check('новое состояние записано', e2['state'] == 'corrected', e2['state'])
check('история у новой записи начата', len(e2['history']) == 1)

corr.record('D_6мес_2025', 'balance', 0, code='1520', state='confirmed',
            reason='перепроверил, верно', at='2026-09-16T12:00:00+03:00')
check('повторная запись по тому же ключу не создаёт вторую',
      len(corr.entries) == 2, str(len(corr.entries)))
check('история ДОПИСАНА, а не переписана', len(e2['history']) == 2, str(len(e2['history'])))
check('первый переход сохранён',
      e2['history'][0]['state'] == 'corrected' and e2['history'][1]['state'] == 'confirmed')
check('в истории видны значения на момент перехода',
      e2['history'][0]['value_read'] == 999 and e2['history'][0]['value_final'] == 1000)
check('прежняя пометка про колонку не тронута',
      corr.entries[C.make_key('D_6мес_2025', 'balance', 0, None)]['state'] == 'disputed')

print()
print('=== 3. некорректные состояния отвергаются ===')
try:
    corr.record('D', 'balance', 0, code='1', state='corrected')
    check('corrected без value_final отвергнут', False, 'исключения не было')
except ValueError:
    check('corrected без value_final отвергнут', True)
try:
    corr.record('D', 'balance', 0, code='1', state='придумано')
    check('неизвестное состояние отвергнуто', False, 'исключения не было')
except ValueError:
    check('неизвестное состояние отвергнуто', True)

# ── 4. применение правки ─────────────────────────────────────────────────────
print()
print('=== 4. правка попадает в ту ячейку, которую читает свод ===')
f = form([
    {'code': '1520', 'name': 'Кредиторская задолженность', 'values': [999, 888]},
    {'code': '1520', 'name': 'Кредиторская задолженность (повтор)', 'values': [111, 222]},
])
c2 = C.Corrections({}, Path(r'D:\models\tests\_tmp_corr.json'))
c2.record('D', 'balance', 0, code='1520', state='corrected',
          value_read=111, value_final=777)
rep = c2.apply_form(f, 'D', 'balance')
check('правка применена', len(rep['applied']) == 1 and not rep['unapplied'], str(rep))
check('записано в ПОСЛЕДНЮЮ строку с кодом (как читает svod.get_val)',
      f['items'][1]['values'][0] == 777, str(f['items'][1]['values']))
check('первая строка с тем же кодом не тронута', f['items'][0]['values'][0] == 999)
check('соседняя колонка не тронута', f['items'][1]['values'][1] == 222)
check('get_val видит новое значение', C._get_val(f, '1520', 0) == 777)

print()
print('=== 5. строки нет — правка НЕ применяется и строку не создаёт ===')
f2 = form([{'code': '1500', 'name': 'Итого', 'values': [1000, 2000]}])
c3 = C.Corrections({}, Path(r'D:\models\tests\_tmp_corr.json'))
c3.record('D', 'balance', 0, code='1520', state='corrected',
          value_read=None, value_final=500)
rep = c3.apply_form(f2, 'D', 'balance')
check('применения нет', not rep['applied'], str(rep['applied']))
check('объяснено как «строки нет»',
      len(rep['unapplied']) == 1 and 'строки с кодом 1520 нет' in rep['unapplied'][0]['why'],
      str(rep['unapplied']))
check('строка НЕ создана', len(f2['items']) == 1, str(len(f2['items'])))
check('чужие значения не тронуты', f2['items'][0]['values'] == [1000, 2000])

print()
print('=== 6. пометка-спор не является правкой: применять нечего ===')
f3 = form([{'code': '1500', 'name': 'Итого', 'values': [1000]}])
c4 = C.Corrections({}, Path(r'D:\models\tests\_tmp_corr.json'))
c4.record('D', 'balance', 0, code=None, codes=['1500'], state='disputed')
rep = c4.apply_form(f3, 'D', 'balance')
check('пометка-спор не применяется', not rep['applied'])
check('пометка-спор не попадает в список неприменённых ПРАВОК',
      not rep['unapplied'], str(rep['unapplied']))
check('значение под пометкой не тронуто', f3['items'][0]['values'] == [1000])

# Противоречивая запись: правка без кода — применять некуда, и это должно быть видно.
c4.record('D', 'balance', 1, code=None, state='corrected', value_read=None, value_final=5)
rep = c4.apply_form(f3, 'D', 'balance')
check('правка без кода не применяется', not rep['applied'])
check('правка без кода объяснена',
      len(rep['unapplied']) == 1 and 'про всю колонку' in rep['unapplied'][0]['why'],
      str(rep['unapplied']))

# ── 7. накрытие ячеек пометкой ───────────────────────────────────────────────
print()
print('=== 7. пометка про колонку накрывает только свои коды ===')
c5 = C.Corrections({}, Path(r'D:\models\tests\_tmp_corr.json'))
c5.record('D', 'balance', 0, code=None, codes=['1520', '1530', '1550'],
          state='disputed')
check('свой код помечен', c5.cell_state('D', 'balance', '1550', 0) == 'disputed')
check('чужой код не помечен', c5.cell_state('D', 'balance', '2110', 0) is None)
check('другая колонка не помечена', c5.cell_state('D', 'balance', '1550', 1) is None)
check('другая форма не помечена', c5.cell_state('D', 'cash_flow', '1550', 0) is None)

c5.record('D', 'balance', 0, code='1550', state='corrected', value_final=42)
check('правка сильнее пометки', c5.cell_state('D', 'balance', '1550', 0) == 'corrected')
check('соседний код остался спорным', c5.cell_state('D', 'balance', '1520', 0) == 'disputed')

c5.record('D', 'balance', 0, code='1520', state='rejected')
check('снятая пометка не даёт заливки', c5.cell_state('D', 'balance', '1520', 0) is None)
check('снятая пометка не глушит соседа', c5.cell_state('D', 'balance', '1530', 0) == 'disputed')

c5.record('D', 'balance', 0, code='1530', state='confirmed')
check('подтверждённая пометка не даёт заливки',
      c5.cell_state('D', 'balance', '1530', 0) is None)

# ── 8. reconcile ─────────────────────────────────────────────────────────────
print()
print('=== 8. reconcile различает состояния ===')


def status_of(entry_rec, art):
    cc = C.Corrections({}, Path(r'D:\models\tests\_tmp_corr.json'))
    cc.record(**entry_rec)
    return cc.reconcile({'D_6мес_2025': art})[0]['status']


art_live = {'balance': form([{'code': '1520', 'name': 'КЗ', 'values': [999]}])}
art_fixed = {'balance': form([{'code': '1520', 'name': 'КЗ', 'values': [1000]}])}
art_other = {'balance': form([{'code': '1520', 'name': 'КЗ', 'values': [555]}])}
art_norow = {'balance': form([{'code': '1500', 'name': 'Итого', 'values': [1]}])}

base = dict(doc='D_6мес_2025', form='balance', column=0, code='1520')
check('правка ещё нужна -> active',
      status_of({**base, 'state': 'corrected', 'value_read': 999,
                 'value_final': 1000}, art_live) == C.ACTIVE)
check('код уже читает верное -> stale',
      status_of({**base, 'state': 'corrected', 'value_read': 999,
                 'value_final': 1000}, art_fixed) == C.STALE)
check('данные под правкой поехали -> drifted',
      status_of({**base, 'state': 'corrected', 'value_read': 999,
                 'value_final': 1000}, art_other) == C.DRIFTED)
check('строки нет -> no_row',
      status_of({**base, 'state': 'corrected', 'value_read': 999,
                 'value_final': 1000}, art_norow) == C.NO_ROW)
check('спор со неизменным значением -> active',
      status_of({**base, 'state': 'disputed', 'value_read': 999}, art_live) == C.ACTIVE)
check('спор, значение изменилось -> drifted',
      status_of({**base, 'state': 'disputed', 'value_read': 999}, art_other) == C.DRIFTED)
check('закрытая запись -> closed',
      status_of({**base, 'state': 'confirmed'}, art_live) == C.CLOSED)
check('пометка про колонку -> active',
      status_of(dict(doc='D_6мес_2025', form='balance', column=0, code=None,
                     codes=['1520'], state='disputed'), art_live) == C.ACTIVE)
check('артефакта нет -> no_row',
      C.Corrections({}, Path(r'D:\models\tests\_tmp_corr.json')).reconcile({}) == [])

# ── 9. что не видно в своде и что осталось без пометки ───────────────────────
print()
print('=== 9. пометки вне колонок свода и подозрения без пометки ===')
c6 = C.Corrections({}, Path(r'D:\models\tests\_tmp_corr.json'))
c6.record('D', 'balance', 0, code=None, codes=['1520', '1530'], state='disputed')
c6.record('D', 'balance', 1, code='1510', state='disputed')
inv = C.invisible_entries(c6, {'1510', '2110'})
check('пометка вне колонок свода найдена', len(inv) == 1, str(len(inv)))
check('нашлась именно та, чьи коды вне свода', inv[0]['column'] == 0, str(inv[0]['column']))
check('пометка по коду из свода не считается невидимой',
      all(e['column'] != 1 for e in inv))

c7 = C.Corrections({}, Path(r'D:\models\tests\_tmp_corr.json'))
c7.record('D_6мес_2025', 'balance', 0, code=None, codes=['1520'], state='disputed')
susp = [('D_6мес_2025', 'balance', 0, 'r1'), ('Другой_6мес_2025', 'balance', 1, 'r2')]
un = C.uncovered(c7, susp)
check('подозрение без пометки найдено', len(un) == 1, str(len(un)))
check('найдено именно непомеченное', un[0][0] == 'Другой_6мес_2025', str(un[0]))
check('помеченное подозрение не попало в список', all(x[0] != 'D_6мес_2025' for x in un))

# ── 10. инвариант: артефакты на диске не меняются ────────────────────────────
print()
print('=== 10. артефакты на диске не меняются (главный инвариант слоя) ===')


def digest_dir():
    h = hashlib.sha1()
    for p in sorted(C.EXTRACTED.glob('*_6мес_*.json')):
        h.update(p.name.encode('utf-8'))
        h.update(p.read_bytes())
    return h.hexdigest()


before = digest_dir()
corr_real = C.Corrections.load()
n_applied = n_unapplied = 0
for p in sorted(C.EXTRACTED.glob('*_6мес_*.json')):
    stem = p.stem
    d = json.loads(p.read_text(encoding='utf-8'))
    for fn in C.FORMS:
        if d.get(fn):
            rep = corr_real.apply_form(d[fn], stem, fn)
            n_applied += len(rep['applied'])
            n_unapplied += len(rep['unapplied'])
after = digest_dir()
check('применение правок не изменило ни одного файла на диске', before == after,
      f'{before} != {after}')
check('реальный слой читается', len(corr_real.entries) >= 1, str(len(corr_real.entries)))
print(f'      (прогон по реальным данным: применено {n_applied}, '
      f'не применено {n_unapplied})')

# ── 11. сериализация ─────────────────────────────────────────────────────────
print()
print('=== 11. запись и чтение файла ===')
tmp = Path(r'D:\models\tests\_tmp_corr.json')
c8 = C.Corrections({}, tmp)
c8.record('D_6мес_2025', 'balance', 0, code='1520', state='corrected',
          value_read=999, value_final=1000, reason='сверил', source='human',
          at='2026-09-16T10:00:00+03:00')
c8.save()
back = C.Corrections.load(tmp)
check('файл читается обратно', len(back.entries) == 1, str(len(back.entries)))
e_back = back.entries[C.make_key('D_6мес_2025', 'balance', 0, '1520')]
check('состояние сохранилось', e_back['state'] == 'corrected')
check('значения сохранились',
      e_back['value_read'] == 999 and e_back['value_final'] == 1000)
check('история сохранилась', len(e_back['history']) == 1)
check('пояснение сохранено', e_back['reason'] == 'сверил')
check('счётчики считают верно', back.counts()['corrected'] == 1, str(back.counts()))
check('схема содержит описание состояний', 'states' in back.to_dict())
tmp.unlink()

print()
print('=' * 60)
print(f'ИТОГ: {ok} успешно, {fail} провалено')
LOG.write(f'\nИТОГ: {ok} успешно, {fail} провалено\n')
LOG.close()
sys.exit(1 if fail else 0)
