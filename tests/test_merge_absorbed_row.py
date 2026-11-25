# -*- coding: utf-8 -*-
r"""Тест слияния дублей кодов: сумма правит итог, но напечатанная строка не исчезает.

Что было сломано:
  `merge_duplicate_codes` складывала две строки с одним кодом и ВЫБРАСЫВАЛА вторую.
  Когда вторая несла данные, которых больше нет нигде, они пропадали. Измерено на
  «Бианка премиум»: «Обязательство по аренде» напечатано с тем же кодом 1520, что и
  «Кредиторская задолженность»; после сложения строка исчезала, `rent_extract` её не
  находил, и свод терял аренду — 1550 пустел, тогда как эталон даёт 173 350.

Правило, которое проверяется:
  1. если у сложенной строки НЕТ своих дочерних строк, она сохраняется как дочерняя —
     она единственный носитель своего значения;
  2. если дочерние строки ЕСТЬ, они переезжают наверх и уже несут значение, поэтому
     родителя сохранять нельзя — иначе сумма считается дважды. Измерено на
     «Биовитрум»: 45 722 = 12 262 + 33 461, и вместе с родителем выходило 91 445
     вместо 45 723;
  3. итог по коду в обоих случаях остаётся суммой (это и есть смысл правила).

Без вызовов модели.

Запуск: python D:\models\tests\test_merge_absorbed_row.py
Лог:    tests\_last_run_merge_row.txt
"""
import io
import json
import os
import sys

sys.path.insert(0, r'D:\models\pylibs')
sys.path.insert(0, r'D:\models')
import pipeline as P
import svod

LOG = io.open(os.path.join(r'D:\models\tests', '_last_run_merge_row.txt'), 'w',
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


def item(code, name, values, children=None):
    it = {'code': code, 'name': name, 'values': list(values),
          'raw_values': [str(v) for v in values]}
    if children:
        it['children'] = children
    return it


# ─── 1. признак в исходнике ───
LOG.write('=== 1. правило объявлено в pipeline.py ===\n')
src = io.open(r'D:\models\pipeline.py', encoding='utf-8').read()
check('сохранение сложенной строки есть', '_absorbed_by_sum' in src)
check('сохранение обусловлено отсутствием дочерних строк',
      "if not nxt.get('children'):" in src)

# ─── 2. без дочерних строк: строка сохраняется ───
LOG.write('\n=== 2. сложенная строка без детей ===\n')
items = [item('1520', 'Кредиторская задолженность', [100, 200]),
         item('1520', 'Обязательство по аренде', [50, 60])]
warns = []
out = P.merge_duplicate_codes(items, warnings=warns, form_key='balance')

top = [it for it in out if it.get('code') == '1520']
check('на верхнем уровне остался один 1520', len(top) == 1, f'получено {len(top)}')
check('итог по коду = сумма [150, 260]', top and top[0]['values'] == [150, 260],
      f'получено {top[0]["values"] if top else None}')
kids = [c for c in (top[0].get('children') or []) if c.get('_absorbed_by_sum')]
check('сложенная строка сохранена как дочерняя', len(kids) == 1,
      f'детей-остатков {len(kids)}')
check('у сохранённой строки верное имя',
      kids and kids[0]['name'] == 'Обязательство по аренде',
      f'получено {kids[0]["name"] if kids else None}')
check('у сохранённой строки верные значения [50, 60]',
      kids and kids[0]['values'] == [50, 60],
      f'получено {kids[0]["values"] if kids else None}')
check('в предупреждениях сказано, что значения сложены',
      any('сложены значения строк' in w for w in warns), f'{warns}')

# ─── 3. свод находит аренду в сохранённой строке ───
LOG.write('\n=== 3. свод видит аренду ===\n')
form = {'items': out}
svod.mark_chains(form)
long_v, short_v, notes, susp = svod.rent_extract(form, 0)
check('rent_extract нашёл краткосрочную аренду', short_v == 50,
      f'получено short={short_v}')
check('и не нашёл долгосрочной', long_v is None, f'получено long={long_v}')
check('в деталях названо «Обязательство по аренде»',
      any('Обязательство по аренде' in n for n in notes), f'{notes}')

# ─── 4. с дочерними строками: родителя НЕ сохраняем ───
LOG.write('\n=== 4. сложенная строка со своими детьми ===\n')
kids_of_b = [item(None, 'Краткосрочные обязательства по лизингу', [20, 21]),
             item(None, 'Краткосрочные обязательства по аренде', [30, 31])]
items2 = [item('1520', 'Кредиторская задолженность', [100, 200]),
          item('1520', 'Обязательство по аренде', [50, 52], children=kids_of_b)]
warns2 = []
out2 = P.merge_duplicate_codes(items2, warnings=warns2, form_key='balance')
top2 = [it for it in out2 if it.get('code') == '1520']
check('итог по коду по-прежнему сумма [150, 252]',
      top2 and top2[0]['values'] == [150, 252],
      f'получено {top2[0]["values"] if top2 else None}')
absorbed2 = [c for c in (top2[0].get('children') or []) if c.get('_absorbed_by_sum')]
check('родитель НЕ сохранён (иначе сумма удвоится)', not absorbed2,
      f'сохранено {len(absorbed2)}')
names2 = [c.get('name') for c in (top2[0].get('children') or [])]
check('дети родителя переехали наверх',
      'Краткосрочные обязательства по лизингу' in names2
      and 'Краткосрочные обязательства по аренде' in names2, f'{names2}')

# ─── 5. и в этом случае аренда считается ОДИН раз ───
LOG.write('\n=== 5. двойного счёта нет ===\n')
form2 = {'items': out2}
svod.mark_chains(form2)
long2, short2, notes2, _ = svod.rent_extract(form2, 0)
check('краткосрочная аренда = 20 + 30 = 50, а не 50 + 50',
      short2 == 50, f'получено short={short2}')

# ─── 6. повтор строки (не отдельная строка) не создаёт остатка ───
LOG.write('\n=== 6. настоящий повтор ===\n')
items3 = [item('1250', 'Денежные средства', [70, 80]),
          item('1250', 'Денежные средства', [70, 80])]
out3 = P.merge_duplicate_codes(items3, warnings=[], form_key='balance')
top3 = [it for it in out3 if it.get('code') == '1250']
check('повтор слит, а не сложен: [70, 80]',
      top3 and top3[0]['values'] == [70, 80],
      f'получено {top3[0]["values"] if top3 else None}')
check('остатка у повтора нет',
      not [c for c in (top3[0].get('children') or []) if c.get('_absorbed_by_sum')],
      f'{top3[0].get("children") if top3 else None}')

# ─── 7. копия не создаётся, если ровно такая строка уже есть в детях ───
# Замер: «ЕнисейАгроСоюз_6мес_2025». Дешёвый переразбор вернул «Обязательство по аренде»
# 10 847 кодом 1520, а та же строка уже лежала под 1520 БЕЗ кода. Копия ничего не делала
# видимым, зато удваивала значение: свод давал 1550 = 21 694 вместо 10 847.
LOG.write('\n=== 7. строка уже есть в детях: копия не нужна ===\n')
items4 = [item('1520', 'Кредиторская задолженность', [100, 200],
               children=[item(None, 'Обязательство по аренде', [50, 60])]),
          item('1520', 'Обязательство по аренде', [50, 60])]
warns4 = []
out4 = P.merge_duplicate_codes(items4, warnings=warns4, form_key='balance')
top4 = [it for it in out4 if it.get('code') == '1520']
check('итог по коду = сумма [150, 260]',
      top4 and top4[0]['values'] == [150, 260],
      f'получено {top4[0]["values"] if top4 else None}')
absorbed4 = [c for c in (top4[0].get('children') or []) if c.get('_absorbed_by_sum')]
check('копия НЕ добавлена — строка и так видна', not absorbed4,
      f'добавлено копий {len(absorbed4)}')
kids4 = [c for c in (top4[0].get('children') or [])
         if (c.get('name') or '') == 'Обязательство по аренде'
         and list(c.get('values') or []) == [50, 60]]
check('«Обязательство по аренде» [50, 60] ровно один раз', len(kids4) == 1,
      f'получено {len(kids4)}')

# ─── 8. и в этом случае свод считает аренду один раз ───
LOG.write('\n=== 8. свод считает такую аренду один раз ===\n')
form4 = {'items': out4}
svod.mark_chains(form4)
long4, short4, notes4, _ = svod.rent_extract(form4, 0)
check('краткосрочная аренда = 50, а не 100', short4 == 50, f'получено short={short4}')

# ─── 9. страховка самого свода: артефакт собран ДО правки ───
# Артефакты на диске старше правки, поэтому свод обязан уметь не удваивать и такой случай.
LOG.write('\n=== 9. страховка свода на старый артефакт ===\n')
legacy = [item('1520', 'Кредиторская задолженность', [150, 260],
               children=[item(None, 'Обязательство по аренде', [50, 60]),
                         {'code': '1520', 'name': 'Обязательство по аренде',
                          'values': [50, 60], 'raw_values': ['', ''],
                          '_absorbed_by_sum': True}])]
form5 = {'items': legacy}
svod.mark_chains(form5)
long5, short5, notes5, _ = svod.rent_extract(form5, 0)
check('краткосрочная аренда = 50, а не 100', short5 == 50, f'получено short={short5}')
check('в деталях сказано, что копия отброшена',
      any('поглощённая копия' in n for n in notes5), f'{notes5}')

# ─── 10. боевой артефакт: цифры сверены с отчётом ───
# Отчёт печатает «Кредиторская задолженность» 1520 = 369 996 и отдельной строкой
# «Обязательство по аренде» 1520 = 10 847; итог раздела V 753 348 = 325 783 + 380 843 +
# 46 722, то есть 1520 в своде обязан быть 380 843 — сумма подтверждена самим отчётом.
LOG.write('\n=== 10. боевой артефакт ЕнисейАгроСоюз_6мес_2025 ===\n')
REAL = os.path.join(r'D:\models\extracted', 'ЕнисейАгроСоюз_6мес_2025.json')
if os.path.exists(REAL):
    d = json.loads(io.open(REAL, encoding='utf-8').read())
    bal = d['balance']
    svod.mark_chains(bal)
    long6, short6, notes6, _ = svod.rent_extract(bal, 0)
    check('аренда = 10 847 (столько печатает отчёт)', short6 == 10847,
          f'получено short={short6}')
    top6 = [it for it in bal['items'] if it.get('code') == '1520']
    check('итог 1520 = 380 843 = 369 996 + 10 847',
          bool(top6) and (top6[0].get('values') or [None])[0] == 380843,
          f'получено {top6[0].get("values") if top6 else None}')
    check('напечатанное значение сохранено в raw_values',
          bool(top6) and (top6[0].get('raw_values') or [None])[0] == 369996,
          f'получено {top6[0].get("raw_values") if top6 else None}')
    check('итог раздела V 753 348 сходится с 380 843',
          bool(top6) and 325783 + 380843 + 46722 == 753348, 'арифметика отчёта')
else:
    check('артефакт на месте', False, REAL)

# ─── 11. копия, у которой пустые колонки стали нулями, — та же строка ───
# `_sum_vals` превращает None в 0, поэтому у копии пустые колонки могут отличаться от
# оригинала: «УПТК65_6мес_2025» — копия [20556, 0, 0], оригинал [20556, None, None].
# Сравнение кортежей «как есть» считало их разными строками и копию добавляло.
LOG.write('\n=== 11. копия с 0 вместо None — та же строка ===\n')
items5 = [item('1520', 'Кредиторская задолженность', [1012815, 1298284, 560827],
               children=[item(None, 'Обязательство по аренде', [20556, None, None])]),
          item('1520', 'Обязательство по аренде', [20556, 0, 0])]
out5 = P.merge_duplicate_codes(items5, warnings=[], form_key='balance')
top5 = [it for it in out5 if it.get('code') == '1520']
check('итог по коду = 1 012 815 + 20 556 = 1 033 371',
      bool(top5) and (top5[0].get('values') or [None])[0] == 1033371,
      f'получено {top5[0].get("values") if top5 else None}')
absorbed5 = [c for c in (top5[0].get('children') or []) if c.get('_absorbed_by_sum')]
check('копия НЕ добавлена: 0 в пустой колонке — это та же строка', not absorbed5,
      f'добавлено копий {len(absorbed5)}')

# ─── 12. но ДВЕ РАЗНЫЕ строки с одним именем копией не считаются ───
# «ЕнисейАгроСоюз_6мес_2025» печатает «Обязательство по аренде» дважды: [None, 21, 379]
# и [10847, None, None]. Проверка «нет колонки с двумя разными заполненными значениями»
# (pipeline._rows_repeat) объявила бы их одной строкой — здесь этого быть не должно.
LOG.write('\n=== 12. две разные строки с одним именем ===\n')
check('копия [20556,0,0] и строка [20556,None,None] — одна строка',
      P._same_printed_row([20556, 0, 0], [20556, None, None]))
check('копия [10847,None,None] и строка [None,21,379] — РАЗНЫЕ строки',
      not P._same_printed_row([10847, None, None], [None, 21, 379]))
check('пустая копия ничьей копией не признаётся',
      not P._same_printed_row([None, None, None], [None, None, None]))
check('правило pipeline и правило свода совпадают',
      all(P._same_printed_row(a, b) == svod.same_printed_row(a, b)
          for a, b in (([20556, 0, 0], [20556, None, None]),
                       ([10847, None, None], [None, 21, 379]),
                       ([None, None, None], [None, None, None]),
                       ([100, 200], [100, 200]))))

# ─── 13. страховка свода на артефакт УПТК65_6мес_2025 (собран до правки) ───
LOG.write('\n=== 13. страховка свода: копия с нулями ===\n')
legacy2 = [item('1520', 'Кредиторская задолженность', [1033371, 1298284, 560827],
                children=[item(None, 'Обязательство по аренде', [20556, None, None]),
                          {'code': '1520', 'name': 'Обязательство по аренде',
                           'values': [20556, 0, 0], 'raw_values': ['', '', ''],
                           '_absorbed_by_sum': True}])]
form6 = {'items': legacy2}
svod.mark_chains(form6)
long6b, short6b, notes6b, _ = svod.rent_extract(form6, 0)
check('аренда = 20 556, а не 41 112', short6b == 20556, f'получено short={short6b}')
check('в деталях сказано, что копия отброшена',
      any('поглощённая копия' in n for n in notes6b), f'{notes6b}')

# ─── 14. боевой артефакт УПТК65_6мес_2025 ───
# Отчёт печатает «Кредиторская задолженность» 1520 = 1 012 815 (стр. 4) и отдельной
# строкой «Обязательство по аренде» 1520 = 20 556 (стр. 5), 1550 = «-».
# Итог раздела V = 1 351 816, и он сходится только если 20 556 учтено ОДИН раз:
# 306 490 + 1 012 815 + 20 556 + 11 954 = 1 351 815 (расхождение 1 — округление в отчёте).
LOG.write('\n=== 14. боевой артефакт УПТК65_6мес_2025 ===\n')
REAL2 = os.path.join(r'D:\models\extracted', 'УПТК65_6мес_2025.json')
if os.path.exists(REAL2):
    d2 = json.loads(io.open(REAL2, encoding='utf-8').read())
    bal2 = d2['balance']
    svod.mark_chains(bal2)
    long8, short8, notes8, _ = svod.rent_extract(bal2, 0)
    check('аренда = 20 556', short8 == 20556, f'получено short={short8}')
    t1520 = [it for it in bal2['items'] if it.get('code') == '1520']
    check('1520 = 1 033 371 = 1 012 815 + 20 556',
          bool(t1520) and (t1520[0].get('values') or [None])[0] == 1033371,
          f'получено {t1520[0].get("values") if t1520 else None}')
    check('напечатанное значение сохранено в raw_values = 1 012 815',
          bool(t1520) and (t1520[0].get('raw_values') or [None])[0] == 1012815,
          f'получено {t1520[0].get("raw_values") if t1520 else None}')
    check('копии-двойника в дереве больше нет',
          not [c for c in (t1520[0].get('children') or [])
               if c.get('_absorbed_by_sum')],
          'копия осталась')
    check('итог раздела V сходится при однократном счёте (1 351 815 против 1 351 816)',
          abs((306490 + 1033371 + 11954) - 1351816) <= 2, 'арифметика отчёта')
else:
    check('артефакт на месте', False, REAL2)

# ─── 15. phantom_copies — детектор строки-двойника ───
# Строка `_absorbed_by_sum` законна, пока она ЕДИНСТВЕННЫЙ носитель значения (19 из 19
# в корпусе). Как только у неё находится двойник, копия перестаёт что-либо делать видимым
# и становится риском двойного счёта. Различать эти два случая обязан детектор.
LOG.write('\n=== 15. phantom_copies: копия с двойником vs единственный носитель ===\n')

def tree(items):
    f = {'items': items}
    svod.mark_chains(f)
    return f

sole = tree([item('1520', 'Кредиторская задолженность', [1033371],
                  children=[{'code': '1520', 'name': 'Обязательство по аренде',
                             'values': [20556], 'raw_values': [''],
                             '_absorbed_by_sum': True}])])
pc = svod.phantom_copies(sole)
check('копия-единственный носитель: детектор её видит', len(pc) == 1, f'{pc}')
check('но фантомом НЕ считает (двойника нет)', pc and pc[0]['phantom'] is False, f'{pc}')

twin = tree([item('1520', 'Кредиторская задолженность', [1033371],
                  children=[item('1520', 'Обязательство по аренде', [20556, None, None]),
                            {'code': '1520', 'name': 'Обязательство по аренде',
                             'values': [20556, 0, 0], 'raw_values': ['', '', ''],
                             '_absorbed_by_sum': True}])])
pc2 = svod.phantom_copies(twin)
check('копия с двойником распознана как фантом',
      any(p['phantom'] for p in pc2), f'{pc2}')
check('пустые колонки копии (0 против None) не мешают опознанию',
      any(p['phantom'] for p in pc2 if p['name'] == 'Обязательство по аренде'), f'{pc2}')

# Две РАЗНЫЕ напечатанные строки аренды с одинаковым именем — не двойники.
# Именно на этом «плывёт» слишком мягкое правило pipeline._rows_repeat.
diff = tree([item('1520', 'Кредиторская задолженность', [100],
                  children=[item(None, 'Обязательство по аренде', [None, 21, 379]),
                            {'code': '1520', 'name': 'Обязательство по аренде',
                             'values': [10847, None, None], 'raw_values': ['', '', ''],
                             '_absorbed_by_sum': True}])])
pc3 = svod.phantom_copies(diff)
check('две разные строки с одним именем фантомом не считаются',
      pc3 and all(p['phantom'] is False for p in pc3), f'{pc3}')

check('в дереве без _absorbed_by_sum детектор молчит',
      svod.phantom_copies({'items': [item('1520', 'Кредиторская задолженность', [1])]}) == [],
      'найдены строки там, где их нет')

# ─── 16. детектор в аудите свода и значение ЕнисейАгроСоюза ───
LOG.write('\n=== 16. аудит свода: раздел о строках-двойниках ===\n')
AUD = os.path.join(r'D:\models\extracted', 'svod_18emitters_audit.md')
CSV18 = os.path.join(r'D:\models\extracted', 'svod_18emitters.csv')
if os.path.exists(AUD):
    aud = io.open(AUD, encoding='utf-8').read()
    check('раздел «Строки-двойники» есть в аудите',
          '### Строки-двойники: где возможен двойной счёт' in aud, 'раздел отсутствует')
    check('корпус чист: фантомов не найдено',
          'имеющих двойника, нет' in aud, 'в аудите перечислены фантомы')
    check('раздел не перечисляет строк там, где фантомов нет',
          '| Эмитент | Год | Код | Цепочка | Строка |' not in aud, 'таблица нарисована зря')
    # Пояснение «учтено ОДИН раз» печатается только когда фантом реально найден, поэтому
    # проверяем не вывод, а то, что оно вообще написано в сборщике аудита.
    check('в сборщике аудита есть пояснение про однократный счёт',
          'учтено ОДИН раз' in io.open(r'D:\models\svod_build.py', encoding='utf-8').read(),
          'пояснения нет в svod_build.py')
else:
    check('аудит свода на месте', False, AUD)

if os.path.exists(CSV18):
    rows = io.open(CSV18, encoding='utf-8-sig').read().splitlines()
    head = rows[0].split(';')
    col = head.index('1550+аренда_2025')
    em = {r.split(';')[0]: r.split(';') for r in rows[1:] if r.strip()}
    check('ЕнисейАгроСоюз: 1550+аренда_2025 = 10 847',
          em.get('ЕнисейАгроСоюз', [None] * 99)[col] == '10847',
          f'получено {em.get("ЕнисейАгроСоюз", [None]*99)[col]}')
    check('УПТК65: 1550+аренда_2025 = 20 556',
          em.get('УПТК65', [None] * 99)[col] == '20556',
          f'получено {em.get("УПТК65", [None]*99)[col]}')
else:
    check('свод 18 эмитентов на месте', False, CSV18)

LOG.write(f'\nИТОГ: успешно {ok}, провалов {fail}\n')
LOG.close()
print(f'успешно {ok}, провалов {fail} (лог: tests/_last_run_merge_row.txt)')
sys.exit(1 if fail else 0)
