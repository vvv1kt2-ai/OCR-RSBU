# -*- coding: utf-8 -*-
r"""Тест: аудит различает «формы в документе нет» и «форма есть, но не прочитана».

Что было сломано:
  Обе ситуации стояли в одной таблице под подписью «настоящие пробелы чтения».
  Замер: Регион-Продукт_6мес_2026 — 6 страниц, из них 1-3 баланс, 4 пустая,
  5-6 ОФР. ОДДС в файле НЕТ ВООВЩЕ, а аудит предлагал его перечитать. Читатель
  пошёл бы перечитывать файл, в котором формы нет, вместо того чтобы собрать файл
  заново.

Правило, которое проверяется: если ни одна страница файла не названа этой формой,
аудит обязан сказать «формы в документе нет — перечитывать нечего»; если страница
с такой меткой есть, а формы в артефакте нет — «есть, но не прочитана». Если меток
в артефакте нет вовсе (сделан до этой правки), аудит обязан честно сказать, что
случай не опознан, а не угадывать.

Без вызовов модели. Данные синтетические, во временном каталоге.

Запуск: python D:\models\tests\test_missing_forms_reason.py
Лог:    tests\_last_run_missing_forms.txt
"""
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r'D:\models\pylibs')
sys.path.insert(0, r'D:\models')
import svod_build as sb

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_missing_forms.txt'), 'w',
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


BAL_COLS = ['На 30 июня 2026 г.', 'На 31 декабря 2025 г.']
BAL = {'form': '0710001', 'columns': list(BAL_COLS),
       'items': [{'code': '1510', 'name': 'Заемные средства', 'values': [100, 90]},
                 {'code': '1300', 'name': 'Итого по разделу III', 'values': [100, 90]},
                 {'code': '1700', 'name': 'БАЛАНС', 'values': [100, 90]}]}


def artifact(page_labels=None, with_is=False, with_cf=False):
    d = {'schema_version': 1.1,
         'source': {'file': 'x.pdf', 'pages_total': 2, 'text_layer': False,
                    'method': 'scan', 'unread_pages': [], 'non_form_pages': {}},
         'company': {'name': 'x'}, 'period': {}, 'unit': {'label': 'тыс. руб.'},
         'balance': BAL, 'checks': [], 'warnings': [], 'status': 'ok'}
    if page_labels is not None:
        d['source']['page_labels'] = page_labels
    if with_is:
        d['income_statement'] = {'form': '0710002', 'columns': ['За 1 полугодие 2026 г.'],
                                 'items': [{'code': '2110', 'name': 'Выручка', 'values': [1]}]}
    if with_cf:
        d['cash_flow'] = {'form': '0710005', 'columns': ['За 1 полугодие 2026 г.'],
                          'items': [{'code': '4110', 'name': 'Поступления', 'values': [1]}]}
    return d


# 1) формы нет в документе: страницы есть, но ни одна не названа ОФР/ОДДС
# 2) форма есть, но не прочитана: ОФР прочитан, а страница 2 названа cash_flow —
#    значит не хватает ровно ОДДС, и причина у него своя
# 3) меток нет вовсе: артефакт сделан до правки
CASES = {
    'НетФормы': artifact({'1': 'balance', '2': 'other'}),
    'ЕстьФорма': artifact({'1': 'balance', '2': 'cash_flow'}, with_is=True),
    'БезМеток': artifact(None),
    # Две формы отсутствуют, и причины РАЗНЫЕ: ОФР в документе нет (страницы с такой
    # меткой нет), а ОДДС есть на стр. 2, но не прочитан. Такой документ обязан
    # попасть в ОБЕ таблицы, каждая форма — в свою.
    'Смешанный': artifact({'1': 'balance', '2': 'cash_flow'}),
}

tmp = Path(tempfile.mkdtemp(prefix='missforms_'))
for nm, d in CASES.items():
    json.dump(d, open(tmp / f'{nm}_6мес_2026.json', 'w', encoding='utf-8'),
              ensure_ascii=False)
(tmp / 'emitters.json').write_text(json.dumps(
    {'emitters': list(CASES), 'orphans': [], 'mfso': []}, ensure_ascii=False),
    encoding='utf-8')

sb.EXTRACTED = tmp
sb.EMITTERS_PATH = tmp / 'emitters.json'
sb.AUDIT_ONLY_EMITTERS = False
sb.XLSX_GENERATED = tmp / 'svod.generated.xlsx'
sb.XLSX_PATH = tmp / 'ЭТАЛОН_НЕ_ТРОГАТЬ.xlsx'
sb.CSV_PATH = tmp / 'svod.csv'
sb.AUDIT_PATH = tmp / 'svod_audit.md'
sb.main(overwrite_gold=False)
audit = sb.AUDIT_PATH.read_text(encoding='utf-8')


def between(a, start, end):
    if start not in a:
        return ''
    t = a.split(start, 1)[1]
    return t.split(end, 1)[0] if end in t else t


ABSENT = between(audit, '### Формы, которых в документе НЕТ',
                 '### Формы, которые в документе ЕСТЬ')
UNREAD = between(audit, '### Формы, которые в документе ЕСТЬ',
                 '### Метки страниц не записаны')
UNKNOWN = audit.split('### Метки страниц не записаны', 1)[1] if \
    '### Метки страниц не записаны' in audit else ''

# ─── 1. форма, которой нет в документе ───
LOG.write('=== 1. формы нет в документе ===\n')
check('раздел «которых в документе НЕТ» существует',
      '### Формы, которых в документе НЕТ' in audit)
check('НетФормы попал в раздел «нет в документе»', 'НетФормы' in ABSENT,
      f'раздел: {ABSENT[:200]!r}')
check('НетФормы НЕ попал в раздел «есть, но не прочитана»', 'НетФормы' not in UNREAD,
      f'раздел: {UNREAD[:200]!r}')
check('сказано, что перечитывать нечего',
      'перечитывать нечего' in audit or 'повторный сбор файла' in audit)
check('приведены метки страниц файла (2: other)', '2: other' in ABSENT,
      f'раздел: {ABSENT[:300]!r}')
check('названы молчащие коды свода (4100, 4110)', '4100, 4110' in ABSENT)

# ─── 2. форма есть, но не прочитана ───
LOG.write('\n=== 2. форма есть, но не прочитана ===\n')
check('раздел «ЕСТЬ, но не прочитаны» существует',
      '### Формы, которые в документе ЕСТЬ' in audit)
check('ЕстьФорма попал в раздел «есть, но не прочитана»', 'ЕстьФорма' in UNREAD,
      f'раздел: {UNREAD[:200]!r}')
check('ЕстьФорма НЕ попал в раздел «нет в документе»', 'ЕстьФорма' not in ABSENT,
      f'раздел: {ABSENT[:200]!r}')
check('названа страница с меткой ОДДС', '2' in UNREAD)
check('сказано, что лечится перечитыванием', 'перечитыванием' in audit)

# ─── 3. артефакт без меток: честное «не опознан» ───
LOG.write('\n=== 3. метки не записаны — случай не опознан ===\n')
check('раздел про отсутствие меток есть', '### Метки страниц не записаны' in audit)
check('БезМеток попал именно туда', 'БезМеток' in UNKNOWN, f'раздел: {UNKNOWN[:200]!r}')
check('БезМеток не выдан ни за «нет в документе»', 'БезМеток' not in ABSENT)
check('БезМеток не выдан ни за «не прочитана»', 'БезМеток' not in UNREAD)
check('объяснено, что нужен повторный прогон и он бесплатный',
      'бесплатный' in UNKNOWN, f'раздел: {UNKNOWN[:200]!r}')

# ─── 4. старая формулировка ушла ───
LOG.write('\n=== 4. документ с двумя формами и РАЗНЫМИ причинами ===\n')
check('Смешанный: ОФР — в разделе «нет в документе»', 'Смешанный' in ABSENT,
      f'раздел: {ABSENT[:300]!r}')
check('Смешанный: ОДДС — в разделе «есть, но не прочитана»', 'Смешанный' in UNREAD,
      f'раздел: {UNREAD[:300]!r}')
sm_absent = [ln for ln in ABSENT.split('\n') if ln.startswith('| Смешанный')]
sm_unread = [ln for ln in UNREAD.split('\n') if ln.startswith('| Смешанный')]
check('в «нет в документе» у Смешанного назван именно ОФР',
      bool(sm_absent) and 'ОФР' in sm_absent[0] and 'ОДДС' not in sm_absent[0],
      f'получено {sm_absent}')
check('в «не прочитана» у Смешанного назван именно ОДДС',
      bool(sm_unread) and 'ОДДС' in sm_unread[0], f'получено {sm_unread}')

LOG.write('\n=== 5. старая формулировка ушла ===\n')
check('«настоящие пробелы чтения» больше не утверждается про все случаи',
      'настоящие пробелы чтения' not in audit)

# ─── 5. конвейер пишет метки ───
LOG.write('\n=== 6. конвейер пишет source.page_labels ===\n')
src = io.open(r'D:\models\pipeline.py', encoding='utf-8').read()
check('метки собираются из разметки страниц',
      "doc_result['_page_labels'] = {p.get('page')" in src)
check('метки пишутся в артефакт',
      "result['source']['page_labels'] = dict(doc_result.get('_page_labels') or {})" in src)

# ─── 6. реальный случай Регион-Продукт_6мес_2026 ───
LOG.write('\n=== 7. реальный Регион-Продукт_6мес_2026 ===\n')
real = Path(r'D:\models\extracted\Регион-Продукт_6мес_2026.json')
if real.exists():
    d = json.loads(real.read_text(encoding='utf-8'))
    labels = (d.get('source') or {}).get('page_labels') or {}
    check('в артефакте записаны метки страниц', bool(labels), f'получено {labels}')
    check('ОДДС среди меток нет — формы в файле действительно нет',
          'cash_flow' not in set(labels.values()), f'метки {labels}')
    check('баланс и ОФР среди меток есть',
          {'balance', 'income_statement'} <= set(labels.values()), f'метки {labels}')
    check('и в артефакте нет ОДДС', not d.get('cash_flow'))
    ra = Path(r'D:\models\extracted\svod_18emitters_audit.md')
    if ra.exists():
        a2 = ra.read_text(encoding='utf-8')
        ab = between(a2, '### Формы, которых в документе НЕТ',
                     '### Формы, которые в документе ЕСТЬ')
        check('в своде по 18 Регион-Продукт стоит в разделе «нет в документе»',
              'Регион-Продукт' in ab, f'раздел: {ab[:300]!r}')
    else:
        LOG.write('  (пропуск: свод по 18 ещё не собран)\n')
else:
    LOG.write('  (пропуск: нет артефакта)\n')

LOG.write(f'\nИТОГО: {ok} OK, {fail} провал(ов)\n')
LOG.close()
print(f'{ok} OK, {fail} провал(ов)  ->  tests/_last_run_missing_forms.txt')
sys.exit(1 if fail else 0)
