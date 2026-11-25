# -*- coding: utf-8 -*-
r"""Тест: аудит называет причину «needs_review» по каждому эмитенту и не путает их.

Что было сломано (две ошибки в разделе 5 аудита):
  1. Причина бралась из переменной `f`, оставшейся от цикла раздела 2. В генераторе
     раздела 5 своего `f` не было, поэтому во ВСЕ строки попадала одна и та же
     чужая строка. Замер на реальном своде: у Денума и ЕнисейАгроСоюза в колонке
     «Причина» стояло «4100 == 4110-4120 [кол.1]» — правило ОДДС, которого в их
     балансах нет. Настоящие причины: «1600 == 1700 [кол.1]» и
     «1200 == 1210+1215+1220+1230+1240+1250+1260 [кол.2]».
  2. Колонка «Файл» была пуста всегда: годы перебирались строками ('2025'), а ключи
     `data` — целыми (2025), поэтому условие `(em, y) in data` было ложно.

Правило, которое проверяется: причина у каждого эмитента — ЕГО собственная, и файл
назван. Две ошибки проверяются вместе: если вернуть любую из них, тест падает.

Вторым сбором проверяется область аудита: при `AUDIT_ONLY_EMITTERS = True` разделы
про весь корпус (4 и 6) и открытые записи corrections.json по эмитентам вне свода
в аудит не попадают.

Без вызовов модели. Данные синтетические, во временном каталоге.

Запуск: python D:\models\tests\test_audit_needs_review.py
Лог:    tests\_last_run_needs_review.txt
"""
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r'D:\models\pylibs')
sys.path.insert(0, r'D:\models')
import openpyxl
import corrections as corr_mod
import svod as svod_mod
import svod_build as sb

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_needs_review.txt'), 'w',
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
FLOW_COLS = ['За 1 полугодие 2026 г.', 'За 1 полугодие 2025 г.']


def bal(items):
    return {'form': '0710001', 'columns': list(BAL_COLS),
            'items': [{'code': c, 'name': c, 'values': v} for c, v in items]}


def flow(items):
    return {'form': '0710005', 'columns': list(FLOW_COLS),
            'items': [{'code': c, 'name': c, 'values': v} for c, v in items]}


# Альфа: 1600 != 1700 только в колонке 0; 1300+1400+1500 == 1700 сходится в обеих,
# поэтому причина обязана быть ровно одна и именно про 1600.
ALPHA_BAL = bal([('1600', [100, 100]), ('1700', [999, 100]), ('1300', [999, 100])])
# ОДДС Альфы намеренно не сходится: 5 != 10-1. Это правило НЕ должно попасть
# в раздел 5 — именно оно раньше протекало туда из раздела 2.
ALPHA_CF = flow([('4100', [5, 5]), ('4110', [10, 10]), ('4120', [-1, -1])])
# Бета: своя причина — про 1300+1400+1500, и только в колонке 0.
BETA_BAL = bal([('1300', [1, 1]), ('1400', [2, 2]), ('1500', [3, 3]), ('1700', [999, 6])])


def artifact(balance=None, cash=None):
    d = {'schema_version': 1.1,
         'source': {'file': 'x.pdf', 'pages_total': 1, 'text_layer': True,
                    'method': 'text'},
         'company': {'name': 'x'}, 'period': {}, 'unit': {'label': 'тыс. руб.'},
         'checks': [], 'warnings': [], 'status': 'ok'}
    if balance:
        d['balance'] = balance
    if cash:
        d['cash_flow'] = cash
    return d


CORR_ENTRIES = [
    # Эмитент вне свода — при AUDIT_ONLY_EMITTERS в аудит попасть не должен.
    {'key': 'Внешний_6мес_2026|balance|0|*', 'doc': 'Внешний_6мес_2026',
     'form': 'balance', 'column': 0, 'code': None, 'codes': [],
     'rule': '', 'state': 'disputed', 'value_read': None, 'value_final': None,
     'reason': 'внешний эмитент', 'source': 'test', 'history': []},
    # Эмитент внутри свода — должен остаться.
    {'key': 'Альфа_6мес_2026|balance|0|*', 'doc': 'Альфа_6мес_2026',
     'form': 'balance', 'column': 0, 'code': None, 'codes': [],
     'rule': '', 'state': 'disputed', 'value_read': None, 'value_final': None,
     'reason': 'внутри свода', 'source': 'test', 'history': []},
]

_orig_load = corr_mod.Corrections.load


def build(only_emitters):
    """Собрать свод во временном каталоге. Возвращает (аудит, каталог)."""
    tmp = Path(tempfile.mkdtemp(prefix='needsrev_'))
    json.dump(artifact(ALPHA_BAL, ALPHA_CF),
              open(tmp / 'Альфа_6мес_2026.json', 'w', encoding='utf-8'),
              ensure_ascii=False)
    json.dump(artifact(BETA_BAL),
              open(tmp / 'Бета_6мес_2026.json', 'w', encoding='utf-8'),
              ensure_ascii=False)
    (tmp / 'emitters.json').write_text(json.dumps(
        {'emitters': ['Альфа', 'Бета'], 'orphans': [], 'mfso': []},
        ensure_ascii=False), encoding='utf-8')
    corr_path = tmp / 'corrections.json'
    corr_path.write_text(json.dumps(
        {'version': 1, 'about': 'тест', 'states': {}, 'updated': '2026-09-16',
         'entries': CORR_ENTRIES}, ensure_ascii=False), encoding='utf-8')
    corr_mod.Corrections.load = classmethod(
        lambda cls, path=None: _orig_load.__func__(cls, str(corr_path)))

    sb.EXTRACTED = tmp
    sb.EMITTERS_PATH = tmp / 'emitters.json'
    sb.AUDIT_ONLY_EMITTERS = only_emitters
    sb.XLSX_GENERATED = tmp / 'svod.generated.xlsx'
    sb.XLSX_PATH = tmp / 'ЭТАЛОН_НЕ_ТРОГАТЬ.xlsx'
    sb.CSV_PATH = tmp / 'svod.csv'
    sb.AUDIT_PATH = tmp / 'svod_audit.md'
    sb.main(overwrite_gold=False)
    return sb.AUDIT_PATH.read_text(encoding='utf-8'), tmp


def section(audit, num):
    """Текст раздела `## <num>.` до следующего заголовка `## `."""
    head = f'## {num}.'
    if head not in audit:
        return ''
    tail = audit.split(head, 1)[1]
    for nxt in ('## 1.', '## 2.', '## 3.', '## 4.', '## 5.', '## 6.', '## 7.'):
        if nxt in tail:
            tail = tail.split(nxt, 1)[0]
    return tail


def table_rows(block):
    rows = []
    for ln in block.split('\n'):
        s = ln.strip()
        if s.startswith('|') and not s.startswith('| Эмитент') and '---' not in s:
            rows.append([c.strip() for c in s.strip('|').split('|')])
    return rows


# ─── 1. основа: причина у каждого своя и файл назван ───
LOG.write('=== 1. раздел 5: причина и файл по каждому эмитенту ===\n')
audit, tmp = build(only_emitters=False)
rows = table_rows(section(audit, 5))
by = {r[0]: r for r in rows if r}

check('в разделе 5 ровно две строки (Альфа и Бета)', len(rows) == 2,
      f'получено {rows}')
if 'Альфа' in by and 'Бета' in by:
    a, b = by['Альфа'], by['Бета']
    check('у Альфы причина — её собственная (1600 == 1700)',
          a[3] == '1600 == 1700 [кол.0]', f'получено {a[3]!r}')
    check('у Беты причина — её собственная (1300+1400+1500 == 1700)',
          b[3] == '1300+1400+1500 == 1700 [кол.0]', f'получено {b[3]!r}')
    check('причины РАЗНЫЕ (иначе вернулась бы протёкшая переменная f)',
          a[3] != b[3], f'обе: {a[3]!r}')
    check('файл Альфы назван', a[1] == 'Альфа_6мес_2026.json', f'получено {a[1]!r}')
    check('файл Беты назван', b[1] == 'Бета_6мес_2026.json', f'получено {b[1]!r}')
else:
    check('в разделе 5 есть Альфа и Бета', False, f'получено {sorted(by)}')

# ─── 2. правило ОДДС не протекает в раздел «(баланс)» ───
LOG.write('\n=== 2. правило ОДДС не попадает в раздел про баланс ===\n')
d_alpha = json.loads((tmp / 'Альфа_6мес_2026.json').read_text(encoding='utf-8'))
cf_fails = svod_mod.check_cf(d_alpha['cash_flow'])
check('у Альфы правило ОДДС действительно не сходится (иначе проверка пустая)',
      '4100 == 4110-4120 [кол.0]' in cf_fails, f'получено {cf_fails}')
check('но в разделе 5 этого правила нет',
      '4100 == 4110-4120' not in section(audit, 5),
      f'раздел 5: {section(audit, 5)!r}')
check('и во всём аудите его нет — ОДДС-заметки в раздел 2 не идут по построению',
      '4100 == 4110-4120' not in audit)

# ─── 3. основная сборка не ограничена: корпусные разделы на месте ───
LOG.write('\n=== 3. AUDIT_ONLY_EMITTERS = False (основная сборка) ===\n')
check('по умолчанию флаг выключен', sb.AUDIT_ONLY_EMITTERS is False)
check('раздел 4 содержит корпусные примечания (Омега)', 'Омега' in section(audit, 4))
check('раздел 6 содержит корпусные примечания (ИПС)', 'ИПС_6мес_2026' in section(audit, 6))
check('открытая запись по эмитенту ВНЕ свода показана', 'внешний эмитент' in audit)

# ─── 4. свод по короткому списку: аудит только про своих ───
LOG.write('\n=== 4. AUDIT_ONLY_EMITTERS = True (свод по короткому списку) ===\n')
audit2, _ = build(only_emitters=True)
check('раздел 4 помечен как пропущенный',
      'Пропущено' in section(audit2, 4), f'раздел 4: {section(audit2, 4)!r}')
check('раздел 6 помечен как пропущенный',
      'Пропущено' in section(audit2, 6), f'раздел 6: {section(audit2, 6)!r}')
check('открытая запись по эмитенту ВНЕ свода убрана', 'внешний эмитент' not in audit2)
check('открытая запись по эмитенту ВНУТРИ свода осталась', 'внутри свода' in audit2)
check('число записей в corrections.json всё равно названо',
      'Записей: 2' in audit2, f'не найдено в {section(audit2, 1)[:200]!r}')
# Раздел 5 обязан работать одинаково в обеих сборках.
rows2 = table_rows(section(audit2, 5))
by2 = {r[0]: r for r in rows2 if r}
check('в ограниченной сборке причина Альфы та же',
      by2.get('Альфа', [None] * 4)[3] == '1600 == 1700 [кол.0]',
      f'получено {by2.get("Альфа")}')

# ─── 5. реальный свод: причины совпадают с провалами в артефактах ───
LOG.write('\n=== 5. реальные артефакты Денум и ЕнисейАгроСоюз ===\n')
real_audit = Path(r'D:\models\extracted\svod_18emitters_audit.md')
if real_audit.exists():
    ra = real_audit.read_text(encoding='utf-8')
    rb = {r[0]: r for r in table_rows(section(ra, 5)) if r}
    for em, art in (('Денум', 'Денум_6мес_2026'),
                    ('ЕнисейАгроСоюз', 'ЕнисейАгроСоюз_6мес_2026')):
        p = Path(r'D:\models\extracted') / f'{art}.json'
        if not p.exists():
            LOG.write(f'  (пропуск: нет {art})\n')
            continue
        dd = json.loads(p.read_text(encoding='utf-8'))
        real_fails = [c['rule'] for c in (dd.get('checks') or [])
                      if c.get('form') == 'balance' and c.get('verdict') == 'fail']
        shown = rb.get(em, [None] * 4)[3]
        check(f'{em}: причина в аудите совпадает с провалом в артефакте',
              bool(real_fails) and real_fails[0].split(' [')[0] in (shown or ''),
              f'аудит {shown!r}, артефакт {real_fails}')
    check('у Денума и ЕнисейАгроСоюза причины РАЗНЫЕ',
          rb.get('Денум', [None] * 4)[3] != rb.get('ЕнисейАгроСоюз', [None] * 4)[3],
          f'{rb.get("Денум")} / {rb.get("ЕнисейАгроСоюз")}')
else:
    LOG.write('  (пропуск: реального аудита нет)\n')

LOG.write(f'\nИТОГО: {ok} OK, {fail} провал(ов)\n')
LOG.close()
print(f'{ok} OK, {fail} провал(ов)  ->  tests/_last_run_needs_review.txt')
sys.exit(1 if fail else 0)
