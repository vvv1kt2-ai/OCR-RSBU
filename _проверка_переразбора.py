# -*- coding: utf-8 -*-
r"""Сухая проверка проводки дешёвого переразбора на РЕАЛЬНОМ документе, без единого вызова.

Что проверяется. Что новый ход действительно проходит весь путь на настоящих данных: берёт
оплаченный транскрипт страниц формы, строит запрос с расхождением, разбирает ответ, сверяет
значения с тем же текстом, собирает кандидата и принимает его только если проверка закрылась.

Как проверяется без денег. Подменяются `cached_llm` (возвращает заготовленный ответ и НЕ
пишет файл — иначе поддельный ответ попал бы в боевой кэш и молча отменил эскалацию в реальном
прогоне) и `chat` (падает, если его всё-таки позовут). Это ловушка на случай, если ход начнёт
звонить модели там, где обещал не звонить.
"""
import copy
import io
import json
import os
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

EX = r'D:\models\extracted'
DL = r'D:\data-scraping\downloads'
DOC = 'ИПС_6мес_2025'

j = json.load(io.open(os.path.join(EX, DOC + '.json'), encoding='utf-8'))
bal = j['balance']
items = bal['items']
pages = bal['transcript_pages']
print(f'документ: {DOC}, строк {len(items)}, страницы формы {pages}')


def find_pdf(name):
    for root, _, files in os.walk(DL):
        if name + '.pdf' in files:
            return os.path.join(root, name + '.pdf')
    return None


pdf = find_pdf(DOC)
print('PDF:', pdf)
doc = P.pymupdf.open(pdf)

print('\nоплаченные транскрипты страниц формы:')
_glob = P.cached_transcript_path
for p in pages:
    path = _glob(doc, DOC, p)
    print(f'  стр.{p}: {os.path.basename(path) if path else "НЕТ для активного поставщика"}')

# ВАЖНО, и это находка сама по себе: у «ИПС_6мес_2025» стр. 4 (раздел V) есть только в кэше
# POLZA, у plusvibe её нет вовсе — то есть под plusvibe страница формы вообще не читалась, и
# строка 1520 отсутствует именно поэтому. Для проверки логики подменяем поиск транскрипта на
# нестрогий (любой поставщик): деньги за этот текст уже уплачены, а стража результата
# (значение обязано быть в посланном тексте + проверка обязана закрыться) остаётся на месте.
def _any_transcript(doc_, name_, p_):
    stem = os.path.splitext(name_)[0]
    hits = [f for f in os.listdir(P.PAGESDIR)
            if f.startswith(f'{stem}_p{p_}_') and f.endswith('.md')]
    if not hits:
        return None
    hits.sort(key=lambda f: ('_200_' not in f, f))
    return os.path.join(P.PAGESDIR, hits[0])


P.cached_transcript_path = _any_transcript
for p in pages:
    path = _any_transcript(doc, DOC, p)
    print(f'  стр.{p} (любой поставщик): {os.path.basename(path) if path else "НЕТ"}')

fa = P.failing_summary('balance', items)
print('\nрасхождение по артефакту:')
print(P.repair_prompt_text('', 'balance', fa, {'1500', '1520'}).split('ТРАНСКРИПЦИЯ')[0][:400])

REAL_CACHED, REAL_CHAT = P.cached_llm, P.chat


def boom(*a, **k):
    raise AssertionError('вызов модели сделан там, где его быть не должно')


def run(answer, label, want=None):
    print(f'\n--- {label}')
    res = {'items': copy.deepcopy(items), 'transcript_pages': pages}
    result = {'balance': res, 'checks': [dict(form='balance', **c)
                                         for c in P.run_checks('balance', res['items'])]}
    warnings = []
    P.cached_llm = lambda tag, fn: answer
    P.chat = boom
    try:
        ok = P.repair_from_transcript(doc, 'balance', res, result,
                                      want or {'1500', '1510', '1520', '1530', '1540', '1550'},
                                      warnings, DOC)
    finally:
        P.cached_llm, P.chat = REAL_CACHED, REAL_CHAT
    print(f'  итог: {"ПРИНЯТ" if ok else "ОТКЛОНЁН"}')
    for w in warnings:
        print('  предупреждение:', w[:110])
    m = P.val_map(res['items'])
    print('  1500 =', m.get('1500'), ' 1520 =', m.get('1520'))
    for c in res.get('checks') or []:
        if c['rule'].startswith('1500'):
            print('  правило 1500 ok =', c['ok'], c['per_column'])
    return ok


# 1) честный ответ: строка, которая действительно лежит в транскрипте стр. 4
run({'missing': [{'code': '1520', 'name': 'Кредиторская задолженность',
                  'values': [15307, 14866, 5255]}]},
    'честный ответ (строка есть в тексте)')

# 2) выдуманное значение: числа нет в посланном тексте
run({'missing': [{'code': '1520', 'name': 'Кредиторская задолженность',
                  'values': [999999999, 14866, 5255]}]},
    'выдуманное значение (числа нет в тексте)')

# 3) строка с кодом вне валящегося правила
run({'missing': [{'code': '2110', 'name': 'Выручка', 'values': [15307, 14866, 5255]}]},
    'код вне валящегося правила')

# 4) пустой ответ
run({'missing': []}, 'пустой ответ')

doc.close()
