# -*- coding: utf-8 -*-
"""Точечные исправления ОДДС по итогам верификации (мандат R4-Q1a):
1. ИПС_6мес_2026: 4400 = [-17671, -49912] — знак подтверждён правилом 4500
   и балансом (1250: 8391 и 26062).
2. КИФА_6мес_2026: хвост ОДДС потерян при структурировании — перечитать стр. 9-10
   основной моделью (транскрипция + структурирование, как в конвейере).
"""
import base64 as _b64
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'D:/models')
sys.path.insert(0, 'D:/models/pylibs')

import pipeline  # noqa: E402
import svod      # noqa: E402

EXTRACTED = 'D:/models/extracted'


def load(name):
    with open(f'{EXTRACTED}/{name}.json', encoding='utf-8') as f:
        return json.load(f)


def save(name, d):
    with open(f'{EXTRACTED}/{name}.json', 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def item_by_code(items, code):
    for it in items or []:
        if it.get('code') == code:
            return it
    return None


print('== 1. ИПС_6мес_2026 ==')
d = load('ИПС_6мес_2026')
cf = d['cash_flow']
it = item_by_code(cf['items'], '4400')
print('было:', it['values'])
it['values'] = [-17671, -49912]
fails = svod.check_cf(cf)
print('check_cf после правки:', fails or 'OK')
d.setdefault('warnings', []).append(
    'Исправлено верификацией: 4400 «Сальдо денежных потоков за период» — потерян знак '
    '(должно быть отрицательным; подтверждено правилом 4500 и остатками денег в балансе 1250).')
d['status'] = 'ok' if not (svod.check_balance(d['balance']) or svod.check_is(d['income_statement']) or fails) else d.get('status')
print('status:', d['status'])
save('ИПС_6мес_2026', d)

print('== 2. КИФА_6мес_2026: перечитывание стр. 9-10 ==')
d = load('КИФА_6мес_2026')
cf_old = d['cash_flow']

doc = pipeline.pymupdf.open('D:/data-scraping/downloads/КИФА_6мес_2026.pdf')
pages = [8, 9]
pix = [doc[p].get_pixmap(dpi=200) for p in pages]
pngs = []
for p, px in zip(pages, pix):
    out = f'D:/models/tmp/kifa2026_p{p+1}.png'
    px.save(out)
    pngs.append(out)

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

columns, items, warns = pipeline.llm_structure_form(txt, 'cash_flow')
print('структурировано: колонок', len(columns or []), 'строк', len(items or []), 'warnings:', warns)
cf_new = dict(cf_old)
cf_new['columns'] = columns or cf_old.get('columns')
cf_new['items'] = items or cf_old.get('items')
fails = svod.check_cf(cf_new)
print('check_cf после перечитывания:', fails or 'OK')
for it in cf_new['items'] or []:
    if it.get('code') in ('4300', '4320', '4400', '4450', '4490', '4500'):
        print(f"  {it.get('code'):<5} {(it.get('name') or '')[:50]:<50} {it.get('values')}")
d['cash_flow'] = cf_new
d.setdefault('warnings', []).append(
    'Хвост ОДДС (4320, 4300, 4400, 4450, 4490, 4500) был потерян при первичном структурировании; '
    'страницы 9-10 перечитаны верификацией.')
save('КИФА_6мес_2026', d)
