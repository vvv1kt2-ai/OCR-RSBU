# -*- coding: utf-8 -*-
r"""Сквозная проверка гейта эскалации БЕЗ оплаты.

Прогоняю настоящую `escalate_failed_form` на сохранённых артефактах, но подменяю
`pipeline.chat` на функцию, которая падает. Если прогон дошёл до конца — значит все
транскрипты и результат структурирования взяты из кэша, и ни одного платного вызова
не сделано. Так проверяется не рассуждение о коде, а сам код.

Ожидание:
  - Славянск ЭКО_6мес_2025: два исправления подтверждены текстом -> применяются;
  - ТГК-14_6мес_2025: значение 11061647 в отправленном тексте ОТСУТСТВУЕТ ->
    исправление не применяется, в предупреждениях появляется запись.
"""
import io, os, json, sys, copy

sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
SRC = r'D:\data-scraping\downloads'


class PaidCall(Exception):
    pass


def forbid(*a, **k):
    raise PaidCall('платный вызов LLM: тест этого не допускает')


P.chat = forbid   # ключевая подмена

CASES = [
    ('Славянск ЭКО_6мес_2025', 'balance'),
    ('ТГК-14_6мес_2025', 'balance'),
]

for stem, form in CASES:
    path = None
    for root, _, files in os.walk(SRC):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                path = os.path.join(root, fn)
    print('=' * 78)
    print('%s  форма %s' % (stem, form))
    if not path:
        print('  PDF не найден'); continue
    saved = json.load(io.open(os.path.join(EX, stem + '.json'), encoding='utf-8'))
    result = copy.deepcopy(saved)
    if not result.get(form):
        print('  формы нет в артефакте'); continue
    print('  значения ДО:')
    for it in (result[form].get('items') or []):
        if it.get('corrected_by') or it.get('values_ocr1'):
            print('     код %s: values=%s ocr1=%s' % (it.get('code'), it.get('values'),
                                                      it.get('values_ocr1')))
    warnings = []
    doc = P.pymupdf.open(path)
    try:
        P.escalate_failed_form(doc, form, result, warnings, name=os.path.basename(path))
    except PaidCall as e:
        print('  ОШИБКА: код попытался сделать платный вызов — %s' % e)
        doc.close(); continue
    finally:
        try:
            doc.close()
        except Exception:
            pass
    print('  значения ПОСЛЕ:')
    for it in (result[form].get('items') or []):
        if it.get('code') in ('1100', '1240', '1250'):
            print('     код %s: values=%s ocr1=%s corrected=%s confirmed=%s'
                  % (it.get('code'), it.get('values'), it.get('values_ocr1'),
                     it.get('corrected_by'), it.get('confirmed_by')))
    print('  предупреждения эскалации:')
    for w in warnings:
        print('     %s' % w[:190])
    print()
print('=' * 78)
print('Если выше не было ни одного PaidCall — значит весь прогон обошёлся кэшем.')
