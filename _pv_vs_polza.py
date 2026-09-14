# -*- coding: utf-8 -*-
"""Same model, two providers: Polza (what we pay now) vs PlusVibe (the new one).
Polza's public model list is fetched live; PlusVibe's from its live catalog.
Our three models are identified by (length, sha1) because ids get redacted."""
import sys, io, json, hashlib

polza = json.load(io.open(r'D:\models\_polza_models.json', encoding='utf-8'))
pv = json.load(io.open(r'D:\models\_pv_catalog.json', encoding='utf-8'))
data = polza.get('data') or []
print('моделей у Polza:', len(data))
print('пример полей:', list(data[0].keys()))

# найти поля с ценой
sample = data[0]
for k, v in sample.items():
    if 'pric' in k.lower() or 'cost' in k.lower() or 'rub' in k.lower():
        print(f'  поле {k} = {json.dumps(v, ensure_ascii=False)[:160]}')

WANT_SHA = {'4f91698118': 'gemini-3.8-flash (наш OCR)',
            '3ed9437314': 'gemini-2.5-flash-lite (наш детектор)',
            '395dd451ac': 'эскалатор (наш второй)'}

by_sha = {}
for m in data:
    mid = str(m.get('id') or '')
    by_sha.setdefault(hashlib.sha1(mid.encode()).hexdigest()[:10], []).append(m)

out = io.open(r'D:\models\_pv_vs_polza.md', 'w', encoding='utf-8')
w = out.write
w('# Одна и та же модель у двух провайдеров\n\n')

for h, label in WANT_SHA.items():
    ms = by_sha.get(h)
    if not ms:
        print(f'{label}: у Polza не найдена')
        w(f'## {label} — у Polza не найдена (sha1 {h})\n\n')
        continue
    m = ms[0]
    mid = str(m.get('id'))
    w(f'## {label}\n\n')
    w(f'id: len={len(mid)} sha1={h}\n\n')
    w('```json\n' + json.dumps({k: v for k, v in m.items()
                                if k not in ('description', 'short_description')},
                               ensure_ascii=False, indent=1)[:1200] + '\n```\n\n')
    print(f'{label}: найдена у Polza, len={len(mid)}')

# PlusVibe — те же модели, все варианты
w('\n## PlusVibe — все варианты тех же моделей\n\n')
for m in pv:
    mid = str(m.get('apiModel') or '')
    h = hashlib.sha1(mid.encode()).hexdigest()[:10]
    if h not in WANT_SHA:
        continue
    w(f'\n### {WANT_SHA[h]}\n\n| вариант | addressAs | вход ₽/1М | выход ₽/1М |\n|---|---|---|---|\n')
    for v in m.get('variants') or []:
        w(f'| {v.get("label")} | `{v.get("addressAs")}` | {v.get("inputRub")} | {v.get("outputRub")} |\n')
out.close()
print('-> _pv_vs_polza.md')
