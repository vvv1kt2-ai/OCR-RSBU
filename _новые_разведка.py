# -*- coding: utf-8 -*-
r"""Разведка НОВЫХ отчётов (9мес) в D:/data-scraping/downloads: объём и текстовый слой.

Без вызовов LLM. Решает, есть ли на чём делать A/B эскалации:
эскалация запускается арифметическим провалом, а провал виден только там,
где форма прочитана, — то есть нужны сканы без текстового слоя.

Пишет `_новые_разведка.csv`, на экран — сводка.
"""
import os, io, csv, sys, re
sys.path.insert(0, r'D:/models')
import pipeline  # noqa: F401  (добавляет pylibs в sys.path)
import fitz

SRC = r'D:/data-scraping/downloads'
OUT = r'D:/models/_новые_разведка.csv'
FORMS = re.compile(r'071000[125]')

rows = []
for fn in sorted(os.listdir(SRC)):
    if not fn.lower().endswith('.pdf'):
        continue
    path = os.path.join(SRC, fn)
    try:
        doc = fitz.open(path)
    except Exception as e:
        rows.append(dict(file=fn, pages=0, text_pages=0, ratio=0.0, chars=0,
                         forms=[], err=str(e)[:60]))
        continue
    n = doc.page_count
    tp = 0
    chars = 0
    forms = set()
    for i in range(n):
        try:
            t = doc[i].get_text() or ''
        except Exception:
            t = ''
        chars += len(t)
        if len(t.strip()) > 50:
            tp += 1
        m = FORMS.search(t)
        if m:
            forms.add(m.group(0))
    doc.close()
    rows.append(dict(file=fn, pages=n, text_pages=tp,
                     ratio=round(tp / float(n), 3) if n else 0.0, chars=chars,
                     forms=';'.join(sorted(forms)), err=''))

with io.open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

tot_pages = sum(r['pages'] for r in rows)
tot_text = sum(r['text_pages'] for r in rows)
print(f'документов: {len(rows)}   страниц: {tot_pages}   с текстом: {tot_text} '
      f'({100.0 * tot_text / max(1, tot_pages):.1f}%)')
buckets = {'0% — чистый скан': [], '1-49% — смешанный': [],
           '50-89% — в основном текст': [], '90-100% — текст': []}
for r in rows:
    if not r['pages']:
        continue
    x = r['ratio']
    k = ('0% — чистый скан' if x == 0 else '1-49% — смешанный' if x < 0.5
         else '50-89% — в основном текст' if x < 0.9 else '90-100% — текст')
    buckets[k].append(r)
for k, v in buckets.items():
    print(f'  {k:28} {len(v):3} док.  {sum(r["pages"] for r in v):5} стр.')
print()
print('документы БЕЗ текстового слоя (кандидаты на A/B):')
for r in sorted(buckets['0% — чистый скан'], key=lambda r: r['pages']):
    print(f'  {r["file"]:44} {r["pages"]:4} стр.')
