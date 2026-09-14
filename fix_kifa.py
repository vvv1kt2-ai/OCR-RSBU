# -*- coding: utf-8 -*-
"""Точечное исправление: КИФА_6мес_2026 — хвост ОДДС потерян, перечитать стр. 9-10."""
import base64 as _b64
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'D:/models')
sys.path.insert(0, 'D:/models/pylibs')

import pipeline
import svod

EXTRACTED = 'D:/models/extracted'


def load(name):
    with open(f'{EXTRACTED}/{name}.json', encoding='utf-8') as f:
        return json.load(f)


def save(name, d):
    with open(f'{EXTRACTED}/{name}.json', 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


d = load('КИФА_6мес_2026')
cf_old = d['cash_flow']

doc = pipeline.pymupdf.open('D:/data-scraping/downloads/КИФА_6мес_2026.pdf')
pages = [8, 9]
pngs = []
for p in pages:
    px = doc[p].get_pixmap(dpi=200)
    out = f'D:/models/tmp/kifa2026_p{p+1}.png'
    px.save(out)
    pngs.append(out)
    print(f'  saved {out} ({px.width}x{px.height})')

prompt = ('Транскрибируй СТРОГО дословно таблицы отчета о движении денежных средств '
          '(форма 0710005) на изображениях в Markdown. Сохрани все числа как напечатано: '
          'числа в скобках оставь в скобках, прочерк оставь прочерком, разделители тысяч сохрани. '
          'Каждая строка таблицы = одна строка Markdown. Ничего не вычисляй и не дополняй.')
content = [{'type': 'text', 'text': prompt}]
for p, png_path in zip(pages, pngs):
    with open(png_path, 'rb') as f:
        b64 = _b64.b64encode(f.read()).decode()
    content.append({'type': 'text', 'text': f'\n--- СТРАНИЦА {p+1} ---'})
    content.append({'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + b64}})

txt, fin = pipeline.chat([{'role': 'user', 'content': content}], pipeline.M_MAIN, temperature=0, max_tokens=16000)
print('транскрипция finish=', fin, 'символов:', len(txt))
with open('D:/models/extracted/pages/КИФА_6мес_2026_cash_flow_p9_10_refix.md', 'w', encoding='utf-8') as f:
    f.write(txt)

result, _ = pipeline.llm_structure_form(txt, 'cash_flow')
columns = result.get('columns') if isinstance(result, dict) else None
items = result.get('items') if isinstance(result, dict) else None
warns = result.get('warnings') if isinstance(result, dict) else []
print('структурировано: колонок', len(columns or []), 'строк', len(items or []), 'warnings:', warns)

cf_new = dict(cf_old)
cf_new['columns'] = columns or cf_old.get('columns')
cf_new['items'] = items or cf_old.get('items')

fails = svod.check_cf(cf_new)
print('check_cf после перечитывания:', fails or 'OK')

print('\nВсе строки ОДДС после исправления:')
for it in cf_new.get('items') or []:
    c = it.get('code')
    if c and c.startswith('4'):
        print(f"  {c:<5} {(it.get('name') or '')[:55]:<55} {it.get('values')}")

d['cash_flow'] = cf_new
d.setdefault('warnings', []).append(
    'Хвост ОДДС (4320, 4300, 4400, 4450, 4490, 4500) был потерян при первичном структурировании; '
    'страницы 9-10 перечитаны верификацией.')
save('КИФА_6мес_2026', d)
print('\nФайл сохранён.')
