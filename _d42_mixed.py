# -*- coding: utf-8 -*-
"""How widespread is 4.2? Scan the whole corpus (no LLM): which PDFs are MIXED —
some pages carry a text layer, others are image-only? And for each, does an
image-only page sit right after a form's text pages (i.e. is a form truncated)?"""
import os, sys, io, glob, json
sys.path.insert(0, r'D:\models')
import pipeline as P
import pymupdf

DL = r'D:\data-scraping\downloads'
pdfs = sorted(glob.glob(os.path.join(DL, '*.pdf')))
rows = []
out = io.open(r'D:\models\_d42_mixed.md', 'w', encoding='utf-8')
w = out.write
w('# Дефект 4.2 — насколько широко: смешанные документы по всему корпусу\n\n')
w('| документ | стр. | с текстом | без текста | без текста стр. | формы (текст) | обрыв формы |\n')
w('|---|---|---|---|---|---|---|\n')

for p in pdfs:
    name = os.path.splitext(os.path.basename(p))[0]
    try:
        doc = pymupdf.open(p)
    except Exception as e:
        rows.append((name, 'OPEN-FAIL', str(e)[:30], '', '', ''))
        continue
    n = len(doc)
    lens = [len(pg.get_text().strip()) for pg in doc]
    empty = [i + 1 for i, L in enumerate(lens) if L < 50]
    full = [i + 1 for i, L in enumerate(lens) if L >= 50]
    mixed = bool(empty) and bool(full)
    fp = {}
    if full:
        try:
            fp = P.find_form_pages(doc)
        except Exception:
            fp = {}
    # does an image-only page immediately follow a form range?
    cut = []
    for k, pl in (fp or {}).items():
        if not pl:
            continue
        nxt = pl[-1] + 1
        if nxt in empty:
            cut.append(f'{k}@{pl[-1]}->{nxt}')
    rows.append((name, n, len(full), len(empty), empty[:14], fp, cut))
    if mixed:
        w('| {} | {} | {} | {} | {} | {} | {} |\n'.format(
            name, n, len(full), len(empty), empty[:14],
            {k: v for k, v in (fp or {}).items() if v}, ' '.join(cut) or '-'))
    doc.close()

mixed = [r for r in rows if isinstance(r[1], int) and r[2] and r[3]]
cutrows = [r for r in mixed if r[6]]
w('\n## Итог\n\n')
w(f'- всего PDF: {len(rows)}\n')
w(f'- смешанных (есть и текст, и картинки-страницы без текста): **{len(mixed)}**\n')
w(f'- из них с обрывом формы на картинке: **{len(cutrows)}**\n')
out.close()

print('PDF всего            :', len(rows))
print('смешанных            :', len(mixed))
print('с обрывом формы      :', len(cutrows))
print('--- смешанные ---')
for r in mixed:
    print(f'  {r[0][:30]:30} стр.{r[1]:3} текст {r[2]:3} пусто {r[3]:3} {r[4]}')
print('--- обрыв формы на картинке ---')
for r in cutrows:
    print(f'  {r[0][:30]:30} {r[6]}')
