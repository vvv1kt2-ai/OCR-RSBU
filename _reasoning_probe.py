# -*- coding: utf-8 -*-
"""Один настоящий вызов с полным разбором usage: сколько токенов ушло на рассуждения.

Стоит около 0.10 ₽ — это цена одной страницы на PlusVibe. Прямого ответа в журналах
нет: chat() читает только prompt_tokens и completion_tokens, а поля с токенами
рассуждений не смотрит никогда. Здесь ответ поставщика разбирается целиком.
"""
import io, json, os, sys, base64

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR

DOC = r'D:\data-scraping\downloads'  # уточним ниже
PAGE = 3
DPI = 200

# берём документ, для которого транскрипт уже есть, чтобы было с чем сравнить
PAGES = r'D:\models\extracted\pages'
cands = sorted(f for f in os.listdir(PAGES)
               if f.endswith('.md') and '_p%d_%d_' % (PAGE, DPI) in f)
print('кандидатов с готовым транскриптом:', len(cands))
print('берём:', cands[0] if cands else 'нет')

stem = cands[0].rsplit('_p%d_%d_' % (PAGE, DPI), 1)[0]
print('документ:', stem)

pdf = None
for root, _, files in os.walk(r'D:\data-scraping\downloads'):
    for f in files:
        if f.lower().endswith('.pdf') and os.path.splitext(f)[0] == stem:
            pdf = os.path.join(root, f)
            break
    if pdf:
        break
print('PDF:', pdf)
if not pdf:
    sys.exit('PDF не найден')

pv = PR.active('plusvibe')
if hasattr(P, 'render_png_page'):
    img = P.render_png_page(pdf, PAGE, DPI)
else:
    import fitz
    doc = fitz.open(pdf)
    img = P.render_png(doc[PAGE - 1], DPI)   # уже base64-строка
    doc.close()
print('картинка: %d знаков base64' % len(img))

key = PR.load_key(pv)
msgs = [P.img_message(img, P.TRANSCRIBE_PROMPT)]
url, headers, body = PR.build_request(pv, pv.roles['main'], msgs, key,
                                      temperature=0.1, max_tokens=8192)

import urllib.request
req = urllib.request.Request(url, data=body, method='POST', headers=headers)
with urllib.request.urlopen(req, timeout=300) as r:
    data = json.loads(r.read())
    hdrs = dict(r.headers)

print()
print('=== полный usage от поставщика ===')
print(json.dumps(data.get('usage'), ensure_ascii=False, indent=1))
print()
print('=== finish_reason ===', data['choices'][0].get('finish_reason'))
txt = data['choices'][0]['message']['content'] or ''
print('=== длина ответа ===', len(txt), 'знаков')
u = data.get('usage') or {}
ct = u.get('completion_tokens', 0)
det = u.get('completion_tokens_details') or {}
print()
print('знаков на выходной токен: %.2f' % (len(txt) / ct if ct else 0))
if det:
    print('детализация выходных токенов:', json.dumps(det, ensure_ascii=False))
    rt = det.get('reasoning_tokens') or 0
    if rt:
        print('доля рассуждений: %.0f%%' % (100 * rt / ct))
print()
print('=== стоимость этого вызова ===')
cost, src = PR.call_cost(pv, pv.roles['main'], u.get('prompt_tokens', 0), ct, hdrs)
print('%.4f ₽ (%s)' % (cost, src))
print()
print('=== первые 300 знаков ответа ===')
print(txt[:300])
