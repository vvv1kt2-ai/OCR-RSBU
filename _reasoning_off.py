# -*- coding: utf-8 -*-
"""Можно ли снизить рассуждения у основной модели и что это даёт.

Один настоящий вызов показал 58% рассуждений в выходных токенах. Если режим
управляется параметром запроса, это крупнейший рычаг экономии: рассуждения
оплачиваются как выход, а нам нужен дословный транскрипт.

Три варианта параметра, по одной странице каждый: ≈ 0.12 ₽ на всё.
"""
import io, json, os, sys, time, urllib.request

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR

PDF = r'D:\data-scraping\downloads\Артген (ИСКЧ)_6мес_2026.pdf'
PAGE, DPI = 3, 200

import fitz
doc = fitz.open(PDF)
img = P.render_png(doc[PAGE - 1], DPI)
doc.close()

pv = PR.active('plusvibe')
key = PR.load_key(pv)
msgs = [P.img_message(img, P.TRANSCRIBE_PROMPT)]
url, headers, body = PR.build_request(pv, pv.roles['main'], msgs, key,
                                      temperature=0.1, max_tokens=8192)
base = json.loads(body.decode('utf-8'))
print('базовое тело запроса, поля:', sorted(base.keys()))
print()

VARIANTS = [
    ('как сейчас (ничего не шлём)', {}),
    ('reasoning_effort=none', {'reasoning_effort': 'none'}),
    ('reasoning_effort=low', {'reasoning_effort': 'low'}),
    ('thinking_budget=0', {'thinking_budget': 0}),
    ('extra_body.thinking_config', {'extra_body': {'thinking_config': {'thinking_budget': 0}}}),
]

print('%-28s %8s %8s %8s %9s %7s' % ('вариант', 'вход', 'выход', 'из них', 'знаков', 'цена ₽'))
print('%-28s %8s %8s %8s %9s %7s' % ('', 'тк', 'тк', 'рассужд.', 'ответа', ''))
print('-' * 78)
rows = []
for label, extra in VARIANTS:
    b = dict(base)
    b.update(extra)
    data = json.dumps(b, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST', headers=headers)
    try:
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=300) as r:
            resp = json.loads(r.read())
            hdrs = dict(r.headers)
        u = resp.get('usage') or {}
        det = u.get('completion_tokens_details') or {}
        rt = det.get('reasoning_tokens') or 0
        ct = u.get('completion_tokens', 0)
        txt = resp['choices'][0]['message']['content'] or ''
        cost, _ = PR.call_cost(pv, pv.roles['main'], u.get('prompt_tokens', 0), ct, hdrs)
        print('%-28s %8d %8d %8d %9d %7.4f'
              % (label, u.get('prompt_tokens', 0), ct, rt, len(txt), cost))
        rows.append({'label': label, 'extra': extra, 'pt': u.get('prompt_tokens', 0),
                     'ct': ct, 'reasoning': rt, 'chars': len(txt), 'cost': cost,
                     'finish': resp['choices'][0].get('finish_reason')})
    except urllib.error.HTTPError as e:
        msg = e.read()[:180].decode('utf-8', 'replace')
        print('%-28s ОТКАЗ %s: %s' % (label, e.code, msg.replace('\n', ' ')[:110]))
        rows.append({'label': label, 'extra': extra, 'error': '%s %s' % (e.code, msg)})
    except Exception as e:
        print('%-28s ОШИБКА %s' % (label, str(e)[:110]))
        rows.append({'label': label, 'extra': extra, 'error': str(e)[:200]})

json.dump(rows, io.open(r'D:\models\_reasoning_probe.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print()
tot = sum(r.get('cost', 0) for r in rows)
print('стоимость опыта: %.4f ₽' % tot)
