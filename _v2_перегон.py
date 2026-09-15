# -*- coding: utf-8 -*-
r"""Перегон трёх документов после исправления дефекта текстовой ветки.

Йуми_6мес_2026, ИПС_6мес_2026, Селл-Сервис_6мес_2026 выходили ПУСТЫМИ: find_form_pages
возвращал `{'income_statement': []}` — непустой словарь без страниц, — и запасной ход в
скановую ветку не срабатывал. Теперь срабатывает, поэтому эти документы должны дать данные.

Перед прогоном сохраняем текущий (пустой) артефакт рядом, чтобы было с чем сравнить.
"""
import io, json, os, shutil, sys, time

sys.path.insert(0, r'D:\models')
import pipeline as P

OUT = r'D:\models\extracted'
KEEP = os.path.join(OUT, '_backup_v2_empty')
DOCS = ['ИПС_6мес_2026', 'Йуми_6мес_2026', 'Селл-Сервис_6мес_2026']


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
        print('%s: PDF не найден' % stem)
        continue
    c0 = P.USAGE['cost_rub']
    try:
        r = P.process(path)
        status = r.get('status')
    except Exception as e:
        status = 'failed: %s' % str(e)[:80]
        r = {}
    pages = 0
    forms = []
    for k in ('balance', 'income_statement', 'cash_flow'):
        d = r.get(k)
        if d:
            pages += len(d.get('transcript_pages') or [])
            forms.append('%s:%d' % (k, len(d.get('items') or [])))
    print('%-24s %-13s %6.3f ₽  %s  страниц %d'
          % (stem, status, P.USAGE['cost_rub'] - c0, ', '.join(forms) or 'форм нет', pages),
          flush=True)

print()
print('всего: %.3f ₽, вызовов %d' % (P.USAGE['cost_rub'], P.USAGE['calls']))
