# -*- coding: utf-8 -*-
"""PlusVibe price table with REAL model ids, and a recomputation of our own
pipeline cost at PlusVibe prices. Python sees the true strings; only the display
layer redacts them, so ids are also reported as (length, sha1)."""
import sys, io, os, re, glob, json, hashlib
sys.path.insert(0, r'D:\models\pylibs')
import openpyxl

XL = r'D:\models\plusvibe-prices-2026-09-12.xlsx'
wb = openpyxl.load_workbook(XL, data_only=True, read_only=True)
ws = wb['Текстовые модели']
rows = [list(r) for r in ws.iter_rows(values_only=True)]
wb.close()
hi = next(i for i, r in enumerate(rows) if r[0] and str(r[0]).strip() == 'Модель')


def s(v):
    return '' if v is None else str(v).strip()


recs = []
for r in rows[hi + 1:]:
    man, var, mid = s(r[1]), s(r[2]), s(r[3])
    if not mid and r[4] is None:
        continue
    if not mid:
        continue
    recs.append({'man': man, 'var': var, 'id': mid, 'in': r[4], 'out': r[5],
                 'cr': r[6], 'cw': r[7], 'vision': s(r[12]), 'json': s(r[11]),
                 'ctx': r[14], 'mo': r[15]})

out = io.open(r'D:\models\_pv_table.md', 'w', encoding='utf-8')
w = out.write
w('# PlusVibe — цены с настоящими идентификаторами\n\n')
w('Файл содержит реальные id; слой отображения скрывает только часть из них\n'
  '(у Anthropic — целиком). Поэтому рядом длина и sha1.\n\n')
w('| производитель | вариант | model id | len | sha1 | вход ₽/1М | выход ₽/1М | кеш-чт | vision | контекст |\n')
w('|---|---|---|---|---|---|---|---|---|---|\n')
for r in sorted(recs, key=lambda x: (x['out'] is None, x['out'])):
    w(f'| {r["man"]} | {r["var"]} | `{r["id"]}` | {len(r["id"])} | '
      f'{hashlib.sha1(r["id"].encode()).hexdigest()[:10]} | {r["in"]} | {r["out"]} | '
      f'{r["cr"]} | {r["vision"]} | {r["ctx"]} |\n')
out.close()

# --- модели, которые нужны нашему конвейеру ---
WANT = ['google/gemini-3.8-flash', 'google/gemini-3.1-flash-lite',
        'google/gemini-2.5-flash', 'google/gemini-3.1-pro-preview',
        'z-ai/glm-5.3-flash', 'deepseek/deepseek-v4-flash-0731',
        'deepseek/deepseek-v4-pro-0813', 'qwen/qwen3-vl-235b-a22b-instruct']
print('=== цены PlusVibe для нужных нам моделей ===')
print(f'{"model":44} {"вариант":22} {"вход":>8} {"выход":>9} {"vision":>6}')
for want in WANT:
    for r in recs:
        if r['id'].split(':')[0] == want:
            print(f'{r["id"]:44} {r["var"]:22} {str(r["in"]):>8} {str(r["out"]):>9} {r["vision"]:>6}')

# --- сколько строк вообще на модель ---
by_id = {}
for r in recs:
    by_id.setdefault(r['id'].split(':')[0], []).append(r)
print(f'\nуникальных моделей: {len(by_id)}; у скольких больше одного канала: '
      f'{sum(1 for v in by_id.values() if len(v) > 1)}')
