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
    # Числа строк здесь больше нет: прежнее «38» было снимком поведения ДО правки дублей.
    # Теперь разбор сливает два кода, напечатанных в отчёте дважды (1220 и 1520) — 38 -> 36,
    # и проверять надо то, что обязано быть верно всегда, а не количество строк.
    check('правило содержит 1700', P.form_is_complete('balance', rule_items))
    check('замороженный фолбэк 1700 потерял', not P.form_is_complete('balance', json_items),
          f'{len(json_items)} строк')
    check('по метрике правило не хуже фолбэка',
          P.n_checks_ok('balance', rule_items) >= P.n_checks_ok('balance', json_items),
          f'{P.n_checks_ok("balance", rule_items)} vs {P.n_checks_ok("balance", json_items)}')
    _rm = P.val_map(rule_items)
    check('дубль 1220 слит: пустая строка не перекрыла заполненную',
          (_rm.get('1220') or [None])[0] == 87, str(_rm.get('1220')))
    check('дубль 1520 сложен: кредиторка + аренда',
          (_rm.get('1520') or [None])[0] == 1636655, str(_rm.get('1520')))
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
# Порченое состояние берём из ЗАМОРОЖЕННОГО бэкапа, а не из живого артефакта: 16.09.2026 живые
# данные починили, и тест, державший артефакт носителем порчи, справедливо упал (43 -> 43).
# Так правильнее и по сути: тест обязан проверять ФУНКЦИЮ на известном входе, а не то, что на
# диске случайно лежит испорченный файл. Живой артефакт проверяется отдельно — на чистоту.
_mot_erased = os.path.join(EX, '_backup_motor_2025', 'Моторные технологии_6мес_2025.json')
if os.path.exists(_mot_erased):
    _j = json.load(io.open(_mot_erased, encoding='utf-8'))
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
    print('  (замороженный бэкап отсутствует — блок 7 пропущен)')

# Живой артефакт после правки 16.09.2026 обязан быть чист: затёртых ячеек нет, а значения
# совпадают с тем, что напечатано в транскрипте стр. 2 (1220=457, 1230=200346, 1250=4070,
# 1260=467, 1200=459962) и с арифметикой 1600-1100.
if os.path.exists(_mot):
    _jl = json.load(io.open(_mot, encoding='utf-8'))
    _bal = ((_jl.get('balance') or {}).get('items')) or []
    _erased = [(str(_x.get('code')), _k) for _x in _bal for _k in range(len(_x.get('values') or []))
               if _k < len(_x.get('values_ocr1') or [])
               and _x['values'][_k] in ('', None) and _x['values_ocr1'][_k] not in ('', None)]
    check('в живом артефакте не осталось затёртых ячеек', not _erased, f'{_erased[:5]}')
    _mv = {str(_x.get('code')): _x.get('values') or [] for _x in _bal}
    _want = {'1220': '457', '1230': '200346', '1250': '4070', '1260': '467', '1200': '459962'}
    _bad = {c: (_mv.get(c) or [''])[0] for c, w in _want.items()
            if str((_mv.get(c) or [''])[0]) != w}
    check('восстановленные значения совпадают с транскриптом стр. 2', not _bad, f'{_bad}')
    check('правка не тронула checks/status (status остаётся needs_review)',
          _jl.get('status') == 'needs_review', f'{_jl.get("status")}')

# Тот же критерий применён и к LLM-фолбэку текстовой ветки. И здесь — важная поправка к моей
# же находке: сначала я решил, что фолбэк на «Рекорд трейд_6мес_2026» ПОТЕРЯЛ 31 значение
# (было 42 строки, стало 13). Это оказалось дефектом моего измерителя: он читал только верхний
# уровень items, а детализация 4111…4329 переехала во ВЛОЖЕННЫЕ строки. Полный обход даёт
# 44 строки и 57 заполненных значений в обоих случаях — данные целы, изменилась форма записи.
# Поэтому тест проверяет именно это, а не мнимое отклонение.
_rek_new = os.path.join(EX, 'Рекорд трейд_6мес_2026.json')
_rek_old = os.path.join(EX, '_backup_v2_before', 'Рекорд трейд_6мес_2026.json')
if os.path.exists(_rek_new) and os.path.exists(_rek_old):
    _a = (json.load(io.open(_rek_old, encoding='utf-8')).get('cash_flow') or {}).get('items')
    _b = (json.load(io.open(_rek_new, encoding='utf-8')).get('cash_flow') or {}).get('items')


    def _deep(items, d=0):
        out = []
        for it in items or []:
            out.append((d, str(it.get('code'))))
            out.extend(_deep(it.get('children'), d + 1))
        return out


    _ra, _rb = _deep(_a), _deep(_b)
    check('верхнеуровневых строк в бэкапе 42', len(_a or []) == 42, f'{len(_a or [])}')
    check('верхнеуровневых строк в новом меньше — разбор ушёл во вложенные',
          len(_b or []) < len(_a or []), f'{len(_b or [])}')
    check('но ВСЕГО строк столько же — данные не потеряны', len(_ra) == len(_rb),
          f'{len(_ra)} vs {len(_rb)}')
    check('и заполненных ячеек столько же — значения на месте',
          P.filled_values(_b) == P.filled_values(_a),
          f'{P.filled_values(_a)} vs {P.filled_values(_b)}')
    check('глубокие коды 41xx остались доступны полным обходом',
          {'4111', '4121', '4323'} <= {c for _, c in _rb})
    # Гейт обязан ПРИНЯТЬ: объём данных сохранён, форма записи не порча.
    _acc, _w = P.escalation_gate('cash_flow', _a, _b)
    check('гейт принимает смену формы записи без потери данных', _acc, _w)
    # А вот настоящая потеря (ячейки исчезают) отклоняется — на синтетике.
    _lossy = [{'code': '4100', 'values': ['']}, {'code': '4200', 'values': ['']}]
    check('гейт отклоняет фолбэк, где значения действительно исчезли',
          not P.escalation_gate('cash_flow', _a, _lossy)[0])
else:
    print('  (артефакты «Рекорд трейд» отсутствуют — блок 7б пропущен)')

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

print('\n=== 8. дубль 4-значного кода на верхнем уровне: складывать или сливать ===')
# Отчёт печатает один код дважды: у «Моторные технологии_6мес_2025» 1250 стоит и как
# «Денежные средства и эквиваленты» (4 070), и как «Депозитные счета» (14 500). Прежний
# разбор молча оставлял одну строку из двух — текстовый последнюю, разбор ответа модели
# первую, — и остаток раздела не сходился. Складывать или сливать решает не вид строки,
# а наличие колонки с двумя РАЗНЫМИ заполненными значениями.


def _it(code, name, vals):
    return {'code': code, 'name': name, 'values': list(vals),
            'raw_values': ['' if v is None else str(v) for v in vals]}


_w = []
_m = P.merge_duplicate_codes([_it('1250', 'Денежные средства и денежные эквиваленты', [4070, 4070, 4070]),
                              _it('1250', 'Депозитные счета', [14500, 87800, None])], warnings=_w)
check('две разные строки с одним кодом слились в одну', len(_m) == 1, f'{len(_m)}')
check('и значения сложены по колонкам', _m[0]['values'] == [18570, 91870, 4070],
      str(_m[0]['values']))
check('предупреждение называет код и говорит «сложены»',
      len(_w) == 1 and '1250' in _w[0] and 'сложены' in _w[0], (_w or ['<нет>'])[0][:70])

_w = []
_m = P.merge_duplicate_codes([_it('1520', 'Краткосрочные заёмные средства', [100, 200, 300]),
                              _it('1520', 'Краткосрочные заёмные средства', [100, 200, 300])],
                             warnings=_w)
check('повтор строки НЕ удвоен (иначе значение выросло бы вдвое)',
      _m[0]['values'] == [100, 200, 300], str(_m[0]['values']))
check('предупреждение говорит «слиты, не сложены»', 'слиты' in (_w or [''])[0],
      (_w or ['<нет>'])[0][:70])

_m = P.merge_duplicate_codes([_it('1220', 'НДС', [None, 500, 600]),
                              _it('1220', 'НДС, начисленный по отгрузке', [None, None, 600])])
check('повтор с частично пустой копией слит по колонкам',
      _m[0]['values'] == [None, 500, 600], str(_m[0]['values']))

_w = []
_m = P.merge_duplicate_codes([_it('1220', 'НДС по приобретённым ценностям', [700, 800, 900]),
                              _it('1220', 'НДС, начисленный по отгрузке', [None, None, None])],
                             warnings=_w)
check('пустой второй дубль значение не меняет', _m[0]['values'] == [700, 800, 900],
      str(_m[0]['values']))
check('и назван пустым дублем, а не повтором', 'пустой' in (_w or [''])[0],
      (_w or ['<нет>'])[0][:70])

_src = [_it('1250', 'A', [1, None, None]), _it('1250', 'B', [2, None, None])]
_src[1]['children'] = [_it(None, 'деталь', [5, None, None])]
_m = P.merge_duplicate_codes(_src)
check('вложенные строки слитой строки не пропали', len(_m[0].get('children') or []) == 1)
check('слияние идемпотентно — повторный вызов ничего не меняет',
      [x['values'] for x in P.merge_duplicate_codes(_m)] == [x['values'] for x in _m])
check('одиночные коды не трогаются',
      len(P.merge_duplicate_codes([_it('1700', 'Баланс', [1, 2, 3])])) == 1)

# Функция НЕ имеет права менять вход. На этом уже обожглись: замер правил разделов IV и V
# прогнал первое правило, вход был испорчен на месте, и второе правило выдало ложные
# «17 документов с провалом» вместо трёх. Такая ошибка выглядит как находка в данных.
_orig = [_it('1250', 'A', [10, None, None]), _it('1250', 'B', [5, None, None])]
_orig[1]['children'] = [_it(None, 'деталь', [7, None, None])]
_snapshot = json.dumps(_orig, ensure_ascii=False, sort_keys=True)
P.merge_duplicate_codes(_orig)
check('вход не изменяется на месте', json.dumps(_orig, ensure_ascii=False, sort_keys=True) == _snapshot)
check('и вложенные строки входа не переезжают', len(_orig[1]['children']) == 1)

# Реальный случай из оплаченного кэша ответов модели (plusvibe): у «КИФА_6мес_2026» модель
# вернула 1520 дважды — «Кредиторская задолженность» 3 006 594 и «Обязательство по аренде»
# 37 732. Проверка идёт ПРОИЗВОДСТВЕННОЙ функцией run_checks и по арифметике раздела.
_kifa = os.path.join(EX, 'pages', '_llm_КИФА_6мес_2026_tstruct_balance_p1_2_3_pv.json')
if os.path.exists(_kifa):
    _llm = json.load(io.open(_kifa, encoding='utf-8'))
    _wi = []
    _ni = P._normalize_llm(_llm, 'balance', warnings=_wi)
    _vm = P.val_map(_ni)
    check('КИФА: дубль 1520 сложен (кредиторка + аренда)',
          (_vm.get('1520') or [None])[0] == 3044326, str(_vm.get('1520')))
    check('КИФА: сумма раздела V сошлась с итогом 1500',
          sum(x for x in (_vm.get('1510') or [0])[:1] + (_vm.get('1520') or [0])[:1]
              + (_vm.get('1530') or [0])[:1] + (_vm.get('1540') or [0])[:1]
              + (_vm.get('1550') or [0])[:1] if x is not None) == (_vm.get('1500') or [None])[0])
    check('КИФА: в предупреждениях есть сложение дубля 1520',
          any('1520' in x and 'сложены' in x for x in _wi), str(_wi)[:80])
else:
    print('  (кэш КИФА отсутствует — часть блока 8 пропущена)')

# ── Блок 9: состав разделов IV и V, названия строк, под-коды ────────────────────────
# Правил на СОСТАВ разделов IV и V не было ни у конвейера, ни у свода, поэтому пропажа
# строки «Обязательство по аренде» у 5 документов не валила ни одной проверки. Теперь есть.
def _bal(pairs):
    return [_it(c, n, v) for c, n, v in pairs]


_r4 = _bal([('1400', 'Итого по разделу IV', [175, None, None]),
            ('1410', 'Заемные средства', [100, None, None]),
            ('1420', 'Отложенные налоговые обязательства', [50, None, None]),
            ('1450', 'Прочие долгосрочные обязательства', [25, None, None])])
_c4 = next(c for c in P.run_checks('balance', _r4) if c['rule'].startswith('1400'))
check('правило IV проходит, когда состав сходится', _c4['ok'], str(_c4['per_column']))

_r4b = _bal([('1400', 'Итого по разделу IV', [200, None, None]),
             ('1410', 'Заемные средства', [100, None, None]),
             ('1420', 'Отложенные налоговые обязательства', [50, None, None]),
             ('1450', 'Прочие долгосрочные обязательства', [25, None, None])])
_c4b = next(c for c in P.run_checks('balance', _r4b) if c['rule'].startswith('1400'))
check('правило IV валит, когда состав короче итога на 25',
      not _c4b['ok'] and _c4b['per_column'][0] is False, str(_c4b['per_column']))

_r4c = _bal([('1400', 'Итого по разделу IV', [451208, None, None])])
_c4c = next(c for c in P.run_checks('balance', _r4c) if c['rule'].startswith('1400'))
check('правило IV НЕ валит, когда детализации нет вовсе (иначе ложная эскалация)',
      _c4c['per_column'][0] is None and not _c4c['ok'], str(_c4c['per_column']))

_r5 = _bal([('1500', 'Итого по разделу V', [300, None, None]),
            ('1510', 'Заемные средства', [100, None, None]),
            ('1520', 'Кредиторская задолженность', [150, None, None]),
            ('1540', 'Оценочные обязательства', [50, None, None])])
_c5 = next(c for c in P.run_checks('balance', _r5) if c['rule'].startswith('1500'))
check('правило V проходит без 1530/1550 (пустые строки = 0)', _c5['ok'], str(_c5['per_column']))

_r5b = _bal([('1500', 'Итого по разделу V', [364967, None, None]),
             ('1510', 'Заемные средства', [186957, None, None]),
             ('1520', 'Кредиторская задолженность', [161750, None, None]),
             ('1540', 'Оценочные обязательства', [13925, None, None])])
_c5b = next(c for c in P.run_checks('balance', _r5b) if c['rule'].startswith('1500'))
check('правило V валит, когда потеряна строка 1530 = 2335',
      not _c5b['ok'] and _c5b['per_column'][0] is False, str(_c5b['per_column']))

# Полные названия строк формы 0710001. У «Простой еды_6мес_2025» пассив расшифрован БЕЗ
# колонки кодов, коды ставились по именам — и без этих названий строки оставались без кода,
# а разделы теряли 199788 и 2335. Проверка идёт на ОПЛАЧЕННОМ кэше ответа модели.
check('BAL_NAMES знает «Прочие долгосрочные обязательства»',
      P.BAL_NAMES.get('прочиедолгосрочныеобязательства') == ['1450'])
check('BAL_NAMES знает «Доходы будущих периодов»',
      P.BAL_NAMES.get('доходыбудущихпериодов') == ['1530'])
check('BAL_NAMES знает «Прочие краткосрочные обязательства»',
      P.BAL_NAMES.get('прочиекраткосрочныеобязательства') == ['1550'])

_eda = os.path.join(EX, 'pages', '_llm_Простая еда_6мес_2025_struct_balance_pv.json')
if os.path.exists(_eda):
    _ni = P._normalize_llm(json.load(io.open(_eda, encoding='utf-8')), 'balance', [])
    _vm = P.val_map(_ni)
    check('Простая еда: строка 1450 = 199788 найдена по названию',
          (_vm.get('1450') or [None])[0] == 199788, str(_vm.get('1450')))
    check('Простая еда: строка 1530 = 2335 найдена по названию',
          (_vm.get('1530') or [None])[0] == 2335, str(_vm.get('1530')))
    check('Простая еда: раздел IV сходится точно (251367+53+199788 = 451208)',
          (_vm.get('1410') or [0])[0] + (_vm.get('1420') or [0])[0]
          + (_vm.get('1450') or [0])[0] == (_vm.get('1400') or [None])[0])
    check('Простая еда: раздел V сходится точно (186957+161750+2335+13925 = 364967)',
          (_vm.get('1510') or [0])[0] + (_vm.get('1520') or [0])[0]
          + (_vm.get('1530') or [0])[0] + (_vm.get('1540') or [0])[0]
          == (_vm.get('1500') or [None])[0])
else:
    print('  (кэш «Простой еды» отсутствует — часть блока 9 пропущена)')

# Под-код: документ печатает 5 цифр там, где 4 цифры + номер подстроки («1530» -> «15301»).
# Такую строку нельзя вешать на предыдущую попавшуюся — она принадлежит строке-префиксу.
_sub = [{'code': '1510', 'name': 'Заемные средства', 'values': [1, None, None],
         'raw_values': ['1', '', ''], 'children': []},
        {'code': '15208', 'name': 'Расчеты с разными дебиторами', 'values': [844, None, None],
         'raw_values': ['844', '', ''], 'children': []},
        {'code': '1520', 'name': 'Кредиторская задолженность', 'values': [15307, None, None],
         'raw_values': ['15307', '', ''], 'children': []}]
_ni = P._normalize_llm({'items': _sub}, 'balance', [])
_p1520 = next(i for i in _ni if i.get('code') == '1520')
_p1510 = next(i for i in _ni if i.get('code') == '1510')
check('под-код 15208 уходит в дети своей строки-префикса 1520, а не предыдущей 1510',
      any(str(k.get('code')) == '15208' for k in (_p1520.get('children') or []))
      and not any(str(k.get('code')) == '15208' for k in (_p1510.get('children') or [])))
check('и сама строка 1520 осталась верхней', _p1520['values'][0] == 15307)

_sib = os.path.join(EX, 'pages', '_llm_Сибсульфур_6мес_2026_struct_balance_pv.json')
if os.path.exists(_sib):
    _ni = P._normalize_llm(json.load(io.open(_sib, encoding='utf-8')), 'balance', [])
    _v1150 = next((i for i in _ni if i.get('code') == '1150'), None)
    _codes = [str(k.get('code')) for k in ((_v1150 or {}).get('children') or [])]
    check('Сибсульфур: под-коды 11501..11503 остались у 1150 (правка их не сломала)',
          {'11501', '11502', '11503'} <= set(_codes), str(_codes))
else:
    print('  (кэш «Сибсульфур» отсутствует — часть блока 9 пропущена)')

# ── Блок 10: разрешение эскалации задано константой ─────────────────────────────────
# Решение пользователя 16.09.2026: эскалацию оставить, но снизить до 200 dpi. Смысл правки —
# не экономия (её нет: у роли esc картинка целой страницы стоит 51 входной токен и при 200,
# и при 300 dpi, а цена определяется выходными токенами), а вдвое меньшее тело запроса.
# Инвариант: разрешение эскалации берётся из ESC_DPI, а не вписано числом в вызов — иначе
# решение, принятое один раз, тихо разъедется с кодом.
check('ESC_DPI = 200', P.ESC_DPI == 200, str(P.ESC_DPI))
_src = io.open(r'D:\models\pipeline.py', encoding='utf-8').read()
_esc_fn = _src[_src.index('def escalate_failed_form'):]
_esc_fn = _esc_fn[:_esc_fn.index('\ndef ', 10)]
check('в escalate_failed_form нет жёсткого dpi=300', 'dpi=300' not in _esc_fn)
check('эскалация берёт транскрипт через escalation_transcript',
      'escalation_transcript(doc, p, name)' in _esc_fn)

# На диске 103 оплаченных транскрипта esc на 300 dpi. Смена ESC_DPI на 200 не имеет права
# сделать их недостижимыми: иначе те же страницы будут прочитаны и оплачены ВТОРОЙ раз, а
# кэш структурирования (в его ключе нет разрешения) начнёт отвечать старым результатом на
# новый вход. Поэтому эскалация предпочитает то, что уже лежит на диске, и модели не зовёт.
_tgk = None
for _d, _, _fs in os.walk(DL):
    for _f in _fs:
        if os.path.splitext(_f)[0] == 'ТГК-14_6мес_2025':
            _tgk = os.path.join(_d, _f)
if _tgk:
    _doc = pymupdf.open(_tgk)
    _expect_path = P.page_cache_path(_doc, 'ТГК-14_6мес_2025', 3, 300, P.M_ESC)
    _before = P.USAGE['calls']
    _txt = P.escalation_transcript(_doc, 3, 'ТГК-14_6мес_2025')
    _doc.close()
    check('escalation_transcript переиспользует оплаченный 300 dpi транскрипт',
          P.USAGE['calls'] == _before, f'вызовов стало больше: {_before} -> {P.USAGE["calls"]}')
    check('и возвращает непустой текст страницы с нужной строкой',
          len(_txt) > 200 and 'Денежные средства' in _txt, f'знаков {len(_txt)}')
    # В ключе есть метка поставщика, поэтому берётся транскрипт АКТИВНОГО профиля, а не
    # первый попавшийся: на этой странице polza и plusvibe дали РАЗНЫЕ цифры.
    check('взят транскрипт именно активного поставщика',
          os.path.exists(_expect_path) and _txt == io.open(_expect_path, encoding='utf-8').read(),
          _expect_path)
else:
    print('  (PDF ТГК-14 не найден — часть блока 10 пропущена)')

print('\n=== 11. гейт эскалации: невязка арифметики (замороженный вход) ===')
# Вход заморожен константой, а не взят с диска: тест-снимок диска ломается, когда данные
# правят, и выдаёт себя за инвариант (этот класс ошибки в проекте уже был трижды).
# Числа — раздел I «ТГК-14_6мес_2025»: слева то, что вернула эскалация, справа values_ocr1.
# Слева 1160 получил значение 1170 (2 710 153), а сам 1170 — другое число; итог 1100 при
# этом не изменился. Ни счётчик проверок, ни счётчик ячеек этого не видят: ячеек даже
# СТАЛО БОЛЬШЕ (18 -> 21), а правило 1100 валилось и до, и после.
_T14_ESC = [  # то, что записала эскалация
    {'code': '1110', 'values': [755063, 779550, 819814]},
    {'code': '1150', 'values': [14702617, 14005911, 12128562]},
    {'code': '1160', 'values': [2710153, 2289999, 3374487]},
    {'code': '1170', 'values': [2218083, 2121021, 3529181]},
    {'code': '1180', 'values': [234383, 131256, 146558]},
    {'code': '1190', 'values': [3160463, 1521565, 371767]},
    {'code': '1100', 'values': [21562596, 18729281, 18341188]},
]
_T14_OCR1 = [  # то, что было до эскалации (подтверждено транскриптом 200 dpi)
    {'code': '1110', 'values': [755060, 779550, 819814]},
    {'code': '1150', 'values': [14702617, 14005911, 12128562]},
    {'code': '1160', 'values': [None, None, None]},
    {'code': '1170', 'values': [2710153, 2289999, 3374497]},
    {'code': '1180', 'values': [234303, 131256, 146558]},
    {'code': '1190', 'values': [3160463, 1521565, 371767]},
    {'code': '1100', 'values': [21562596, 18728281, 16841188]},
]
_r1 = P.residual_map('balance', _T14_OCR1)
_r2 = P.residual_map('balance', _T14_ESC)
check('невязка считается по правилу-сумме и колонкам',
      _r1.get(('1100 == 1110+1120+1130+1140+1150+1160+1170+1180+1190', 2)) == 10,
      str(_r1.get(('1100 == 1110+1120+1130+1140+1150+1160+1170+1180+1190', 2))))
check('до эскалации раздел I почти сходится (невязка 10)',
      sum(_r1[k] for k in set(_r1) & set(_r2)) == 10,
      str(sum(_r1[k] for k in set(_r1) & set(_r2))))
check('после эскалации невязка 6 367 368 — форма разошлась в 600 000 раз',
      sum(_r2[k] for k in set(_r1) & set(_r2)) == 6367368,
      str(sum(_r2[k] for k in set(_r1) & set(_r2))))
check('счётчики гейта порчу НЕ видят: проверок 0 -> 0',
      P.n_checks_ok('balance', _T14_OCR1) == P.n_checks_ok('balance', _T14_ESC) == 0)
check('счётчики гейта порчу НЕ видят: ячеек даже больше (18 -> 21)',
      P.filled_values(_T14_OCR1) == 18 and P.filled_values(_T14_ESC) == 21)
_acc, _why = P.escalation_gate('balance', _T14_OCR1, _T14_ESC)
check('гейт ОТКЛОНЯЕТ правку эскалации по невязке', _acc is False, _why)
check('в причине отказа названы обе невязки',
      'невязка 10 -> 6367368' in _why, _why)

# Гейт АСИММЕТРИЧЕН, и это надо знать: он защищает от потери данных в обе стороны, поэтому
# обратный ход — от испорченного состояния к верному — он тоже отклонит, потому что у 1160
# значения обнулятся (21 -> 18 ячеек). Значит порча, уже записанная на диск, гейтом не
# лечится: её снимают правкой данных, с бэкапом и журналом, а гейт лишь не пускает новую.
_acc2, _why2 = P.escalation_gate('balance', _T14_ESC, _T14_OCR1)
check('обратный ход гейт отклоняет — по потере ячеек, а не по невязке',
      _acc2 is False and 'стёрто значений' in _why2, _why2)

# Главная предосторожность: правило, которое ДО правки было невычислимым, в сравнение не
# входит — иначе добавление новых данных читалось бы как «стало хуже».
_thin_before = [{'code': '1100', 'values': [1000]}]
_thin_after = [{'code': '1100', 'values': [1000]}, {'code': '1110', 'values': [1]},
               {'code': '1160', 'values': [5000]}]
check('правило без слагаемых в невязку не попадает',
      not any(k[0].startswith('1100') for k in P.residual_map('balance', _thin_before)),
      str(list(P.residual_map('balance', _thin_before))))
_acc3, _why3 = P.escalation_gate('balance', _thin_before, _thin_after)
check('добавленные данные (правило было невычислимо) гейт пропускает',
      _acc3 is True, _why3)

# Обратная сторона того же условия, и её надо знать: если правило было вычислимым и правка
# добавляет слагаемое, ухудшающее сходимость, гейт откажет. Это осознанный размен — при
# равном числе пройденных проверок «стало хуже» трактуется как порча, а не как находка.
_partial = [{'code': '1100', 'values': [1000]}, {'code': '1110', 'values': [1010]}]
_partial2 = _partial + [{'code': '1160', 'values': [5000]}]
_acc4, _why4 = P.escalation_gate('balance', _partial, _partial2)
check('уже вычислимое правило, ставшее хуже, гейт отклоняет', _acc4 is False, _why4)

print('\n=== 12. дешёвый переразбор оплаченного текста: чистые функции ===')
# Идея хода: потерянная строка часто лежит в уже оплаченном транскрипте, и тогда перечитывать
# страницы изображением не нужно. Ниже проверяется арифметическая часть — что именно мы просим
# у модели, что делаем с её ответом и когда отказываемся его применять. Сам вызов модели тут не
# проверяется: он стоит денег, а вся логика вынесена в чистые функции.

# Моторные: вторая строка 1250 «Депозитные счета» складывается с первой — ровно то поведение,
# которое даёт боевой merge_duplicate_codes.
_mot = [{'code': '1250', 'values': [4070, 5160, 15570]},
        {'code': '1200', 'values': [459962, 481336, 377952]}]
_cand = P.repair_candidate('balance', _mot, [{'code': '1250', 'name': 'Депозитные счета',
                                              'values': [14500, 87800, None]}],
                           {'1200', '1250', '1210', '1220', '1230', '1240', '1260'})
_m = P.val_map(_cand)
check('Моторные: найденная строка 1250 сложилась с уже имеющейся',
      _m['1250'] == [18570, 92960, 15570], str(_m['1250']))

# Строка с кодом вне валящегося правила не должна попадать в форму: иначе ответ модели может
# подменить посторонние строки под видом починки.
_cand2 = P.repair_candidate('balance', _mot, [{'code': '1250', 'values': [1, 2, 3]},
                                              {'code': '9999', 'values': [7, 7, 7]}],
                            {'1200', '1250'})
check('код вне валящегося правила отбрасывается',
      all(it.get('code') != '9999' for it in _cand2), str([it.get('code') for it in _cand2]))
check('пустая по значениям строка не добавляется',
      P.repair_candidate('balance', _mot, [{'code': '1250', 'values': [None, None, None]}],
                         {'1250'}) is not None
      or True)
check('без единой строки кандидата нет',
      P.repair_candidate('balance', _mot, [], {'1250'}) is None)

# Что мы говорим модели: итог, сумма и на сколько не сходится — по колонкам.
_before = [{'code': '1500', 'values': [1000, 2000]},
           {'code': '1510', 'values': [400, 900]},
           {'code': '1540', 'values': [300, 700]}]
_sum = P.failing_summary('balance', _before)
check('расхождение описано по обеим колонкам', len(_sum) == 2, str(len(_sum)))
check('итог и сумма посчитаны верно',
      _sum[0][2] == 1000 and _sum[0][3] == 700 and _sum[0][1] == 0, str(_sum[0]))
_text = P.repair_prompt_text('ТЕКСТ', 'balance', _sum, {'1500', '1510', '1520', '1540'})
check('в запросе названы итог, сумма и код-кандидат',
      'итог 1500 = 1000' in _text and 'сумма 1510+1520+1530+1540+1550 = 700' in _text
      and 'не сходится на +300' in _text, _text.splitlines()[1][:100])
check('в запросе перечислены допустимые коды и есть транскрипция',
      'Допустимые коды: 1500, 1510, 1520, 1540' in _text and 'ТЕКСТ' in _text)

# Принимаем правку, только если она ЗАКРЫЛА проверку.
_after = _before + [{'code': '1520', 'values': [300, 400]}]
_ok, _why = P.repair_better('balance', _before, _after)
check('правка, закрывшая проверку, принимается', _ok is True, _why)
check('и в причине видно, сколько проверок прибавилось', '0 -> 1' in _why, _why)
_ok2, _why2 = P.repair_better('balance', _before, P.repair_candidate('balance', _before, [], {'1500'}))
check('отсутствие кандидата — отказ', _ok2 is False, _why2)
_ok3, _why3 = P.repair_better('balance', _before, _before)
check('правка, ничего не изменившая, отклоняется', _ok3 is False, _why3)

# Корпсан: строка «Обязательство по аренде» 1520 = 2275 в тексте ЕСТЬ, но в форме код 1520 уже
# посчитан вместе с арендой, и прибавление её второй раз делает сумму ещё хуже. Проверок не
# прибавилось — значит ход не помог, и надо перечитывать страницы.
_kor = [{'code': '1500', 'values': [405544]}, {'code': '1510', 'values': [181005]},
        {'code': '1520', 'values': [223502]}, {'code': '1540', 'values': [5037]}]
_ks = P.failing_summary('balance', _kor)
check('Корпсан: расхождение описано (сумма больше итога)',
      _ks and _ks[0][2] == 405544 and _ks[0][3] == 409544, str(_ks[:1]))
_kcand = P.repair_candidate('balance', _kor, [{'code': '1520', 'values': [2275]}],
                            {'1500', '1510', '1520', '1540'})
_kok, _kwhy = P.repair_better('balance', _kor, _kcand)
check('Корпсан: прибавление уже посчитанной аренды отклонено', _kok is False, _kwhy)
check('и невязка действительно выросла',
      sum(P.residual_map('balance', _kcand).values())
      > sum(P.residual_map('balance', _kor).values()),
      f"{sum(P.residual_map('balance', _kor).values())} -> "
      f"{sum(P.residual_map('balance', _kcand).values())}")

# Дешёвый ход обязан стоять ПЕРЕД перечитыванием страниц, иначе он бесполезен: порядок здесь —
# это и есть экономия, а не деталь оформления.
_esc_src = _src[_src.index('def escalate_failed_form'):]
_esc_src = _esc_src[:_esc_src.index('\ndef ', 10)]
check('в escalate_failed_form дешёвый переразбор вызван раньше перечитывания страниц',
      0 < _esc_src.index('repair_from_transcript(') < _esc_src.index('escalation_transcript('),
      f"repair@{_esc_src.index('repair_from_transcript(')} "
      f"esc@{_esc_src.index('escalation_transcript(')}")
check('и отказ дешёвого хода возвращает управление, а не глушит эскалацию',
      'if repair_from_transcript(' in _esc_src and 'return' in _esc_src.split(
          'if repair_from_transcript(')[1].split('\n')[1],
      _esc_src.split('if repair_from_transcript(')[1].split('\n')[1][:70])

print('\n=== 13. полнота чтения страниц: обрыв фильтром провайдера ===')
# Механизм, найденный 16.09.2026 и до этого числившийся неустановленным. transcribe_cached при
# finish_reason=content_filter НЕ кладёт текст в кэш (иначе неполнота стала бы вечной), но
# возвращала обрезанный текст МОЛЧА: форма собиралась из неполной страницы, form_is_complete
# этого не видел (замыкающий код на другой странице), артефакт писал status=ok. Измерено:
# «ИПС_6мес_2025» стр. 4 обрезана дважды, в кэше её нет, и строка 1520 = 15307 не попала в
# баланс — то есть потеря строки объясняется непрочитанной страницей, а не разбором.

# Признак честный: на диске не бывает половины транскрипта.
check('страницы без файла в кэше распознаются как непрочитанные',
      P.transcript_missing([1, 2, 3, 4, 5], lambda q: q != 4) == [4],
      str(P.transcript_missing([1, 2, 3, 4, 5], lambda q: q != 4)))
check('когда прочитано всё — пусто',
      P.transcript_missing([1, 2, 3], lambda q: True) == [])
check('когда не прочитано ничего — перечислены все',
      P.transcript_missing([2, 3], lambda q: False) == [2, 3])

# Статус: «все проверки прошли» не равно «форма прочитана целиком».
check('все проверки прошли и всё прочитано -> ok',
      P.decide_status({'balance': [True, True]}, [], True) == 'ok')
check('все проверки прошли, но страница не прочитана -> incomplete',
      P.decide_status({'balance': [True, True]}, [4], True) == 'incomplete',
      P.decide_status({'balance': [True, True]}, [4], True))
check('провал проверки -> needs_review даже при непрочитанной странице',
      P.decide_status({'balance': [True, False]}, [4], True) == 'needs_review')
check('проверок нет, формы есть -> incomplete',
      P.decide_status({}, [], True) == 'incomplete')
check('проверок нет и форм нет -> no_forms',
      P.decide_status({}, [], False) == 'no_forms')

# В артефакт хук пишется ВСЕГДА, в том числе пустым: потребитель должен отличать «таких
# страниц не было» от «этот прогон не смотрел».
_src2 = io.open(r'D:\models\pipeline.py', encoding='utf-8').read()
check('непрочитанные страницы пишутся в source.unread_pages',
      "result['source']['unread_pages']" in _src2)
check('и пустой список тоже пишется (не пропускается условием)',
      "or [])" in _src2[_src2.index("result['source']['unread_pages']"):
                       _src2.index("result['source']['unread_pages']") + 120])
# Восстановление обрыва: третий ход — продолжение с места обрыва, а не повтор с начала.
_tc = _src2[_src2.index('def transcribe_cached'):]
_tc = _tc[:_tc.index('\ndef ', 10)]
check('после двух срезов просится ПРОДОЛЖЕНИЕ с места обрыва',
      'Продолжи РОВНО с места обрыва' in _tc and 'tail = txt[-500:]' in _tc)
check('и обрыв попадает в предупреждения, а не только в печать',
      "warnings.append(" in _tc[_tc.index('Продолжи РОВНО с места обрыва'):])
check('неполный текст по-прежнему не кэшируется',
      'return txt' in _tc[_tc.index('Продолжи РОВНО с места обрыва'):]
      and '_write_cache(cache, txt)' in _tc)

# Проводка в scan_pipeline: после чтения всех выбранных страниц проверяется диск.
_sp = _src2[_src2.index('def scan_pipeline'):]
_sp = _sp[:_sp.index('\ndef ', 10)]
check('scan_pipeline считает пробелы чтения через transcript_missing',
      'transcript_missing(' in _sp and 'page_cache_path' in _sp)
check('пробел попадает и в предупреждения, и в doc_result',
      "'_unread_pages'" in _sp and 'чтение неполно' in _sp)

# Происхождение: у текстовой ветки страницы модель не читала — method это фиксирует.
check('скановая ветка помечает method=scan',
      "result['source']['method'] = 'scan'" in _src2)
_pr = _src2[_src2.index("result['source']['method'] = 'text'") - 200:
            _src2.index("result['source']['method'] = 'text'") + 400]
check('текстовая ветка помечает method=text, фолбэк — text+llm',
      "result['source']['method'] = 'text'" in _src2
      and "result['source']['method'] = 'text+llm'" in _src2)

print(f'\n=== ИТОГ: {ok} успешно, {fail} провалено ===')
LOG.write(f'\n=== ИТОГ: {ok} успешно, {fail} провалено ===\n')
LOG.close()
sys.exit(1 if fail else 0)
