# -*- coding: utf-8 -*-
r"""Догон двух документов, упавших в прогоне: ИПС_6мес_2025 и Нижегородец Восток_6мес_2026.

Они падали на HTTP 400 «Некорректный запрос», исчерпав повторы, поэтому их артефакты на диске
остались СТАРЫМИ копиями бэкапа — их легко принять за результат нового прогона, и в сравнении
данных они были исключены. Здесь перегоняем их, чтобы пилот был полным (41 из 41).

Сбои поставщика не списываются (0.01 ₽ за все 16 754 вызова на не-200 статусы), поэтому
повтор стоит денег только при успехе.
"""
import io, json, os, shutil, sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402

OUT = r'D:\models\extracted'
KEEP = os.path.join(OUT, '_backup_v2_failed')
DOCS = ['ИПС_6мес_2025', 'Нижегородец Восток_6мес_2026']


def find_pdf(stem):
    for root, _, files in os.walk(P.DOWNLOADS):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


os.makedirs(P.OUTDIR, exist_ok=True)
os.makedirs(KEEP, exist_ok=True)
for stem in DOCS:
    src = os.path.join(OUT, stem + '.json')
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(KEEP, stem + '.json'))

for stem in DOCS:
    path = find_pdf(stem)
    if not path:
        print('%s: PDF не найден' % stem, flush=True)
        continue
    c0 = P.USAGE['cost_rub']
    try:
        r = P.process(path)
        status = r.get('status')
    except Exception as e:
        status = 'СБОЙ: %s' % str(e)[:70]
        r = {}
    forms, pages = [], 0
    for k in ('balance', 'income_statement', 'cash_flow'):
        d = r.get(k)
        if d:
            pages += len(d.get('transcript_pages') or [])
            forms.append('%s:%d' % (k, len(d.get('items') or [])))
    print('%-30s %-14s %6.3f ₽  %s  страниц %d'
          % (stem, status, P.USAGE['cost_rub'] - c0, ', '.join(forms) or 'форм нет', pages),
          flush=True)

print()
print('всего: %.3f ₽, вызовов %d' % (P.USAGE['cost_rub'], P.USAGE['calls']))
