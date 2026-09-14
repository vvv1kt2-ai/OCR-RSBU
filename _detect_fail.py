# -*- coding: utf-8 -*-
r"""Почему у PlusVibe отказывает детекция: рассуждения съедают весь max_tokens.

Из лога прогонов: HTTP 502 с текстом «Поставщик вернул ответ без текста: весь заданный
вами max_tokens ушёл на внутренние рассуждения модели». Детекция у конвейера вызывается
с max_tokens=1200 (группами по 8 страниц) и 4000 (мелкие документы), а модель детекции
PlusVibe тратит на рассуждения больше, чем весь этот предел, — текста не остаётся.

Проверяются три способа починки, по одному вызову каждый:
  как сейчас (1200)          — воспроизводим отказ;
  больше предела (4000)      — даём рассуждениям место;
  reasoning_effort=none      — снимаем рассуждения.
"""
import io, json, os, sys, time, urllib.request

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR
import fitz

PDF = r'D:\data-scraping\downloads\Сибсульфур_6мес_2026.pdf'
pv = PR.active('plusvibe')
key = PR.load_key(pv)


def call(group, max_tokens, extra=None, tag=''):
    d = fitz.open(PDF)
    try:
        npages = d.page_count
        cm = [{'role': 'user', 'content': [
            {'type': 'text',
             'text': P.DETECT_PROMPT + f' (Страницы {group[0]}-{group[-1]} из {npages})'}]}]
        for j in group:
            cm[0]['content'].extend(
                P.img_parts(P.render_png(d[j - 1], 120), f'СТРАНИЦА {j}'))
    finally:
        d.close()
    url, headers, body = PR.build_request(pv, P.M_DETECT, cm, key,
                                          temperature=0, max_tokens=max_tokens)
    b = json.loads(body.decode('utf-8'))
    if extra:
        b.update(extra)
    req = urllib.request.Request(url, data=json.dumps(b, ensure_ascii=False).encode('utf-8'),
                                method='POST', headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            resp = json.loads(r.read())
        u = resp.get('usage') or {}
        det = u.get('completion_tokens_details') or {}
        txt = resp['choices'][0]['message']['content'] or ''
        fin = resp['choices'][0].get('finish_reason')
        n_pages = len(P.salvage_pages_map(txt, npages))
        return {'ok': True, 'pt': u.get('prompt_tokens'), 'ct': u.get('completion_tokens'),
                'reasoning': det.get('reasoning_tokens') or 0, 'chars': len(txt),
                'finish': fin, 'parsed': n_pages, 'sec': time.time() - t0}
    except urllib.error.HTTPError as e:
        raw = e.read()[:400].decode('utf-8', 'replace')
        msg = ''
        try:
            msg = json.loads(raw).get('error', {}).get('message', '')
        except Exception:
            msg = raw
        return {'ok': False, 'code': e.code, 'msg': msg[:150], 'sec': time.time() - t0}
    except Exception as e:
        return {'ok': False, 'code': '?', 'msg': str(e)[:150], 'sec': time.time() - t0}


GROUP = [25, 26, 27, 28, 29, 30, 31, 32]
print('=== детекция группы из 8 страниц, модель детекции PlusVibe ===')
print('модель: len=%d' % len(P.M_DETECT))
print()
print('%-26s %6s %8s %6s %10s %8s %8s' % ('вариант', 'вход', 'выход', 'рассужд',
                                          'знаков', 'страниц', 'сек'))
print('-' * 78)
CASES = [
    ('как сейчас (1200)', 1200, None),
    ('предел 4000', 4000, None),
    ('предел 8000', 8000, None),
    ('1200 + effort=none', 1200, {'reasoning_effort': 'none'}),
    ('4000 + effort=none', 4000, {'reasoning_effort': 'none'}),
]
rows = []
for label, mt, extra in CASES:
    r = call(GROUP, mt, extra)
    r['label'] = label
    rows.append(r)
    if r['ok']:
        print('%-26s %6s %8s %6s %10d %8s %8.0f'
              % (label, r['pt'], r['ct'], r['reasoning'], r['chars'], r['parsed'],
                 r['sec']))
    else:
        print('%-26s ОТКАЗ HTTP %s: %s' % (label, r['code'], r['msg'][:90]))
print()
print('=== что это значит ===')
bad = [r for r in rows if not r['ok']]
print('вариантов с отказом: %d из %d' % (len(bad), len(rows)))
for r in bad:
    print('  %-26s %s' % (r['label'], r['msg'][:120]))
json.dump(rows, io.open(r'D:\models\_detect_fail.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print()
print('токены: pt=%d ct=%d, стоимость %.4f ₽'
      % (P.USAGE['prompt'], P.USAGE['completion'], P.USAGE['cost_rub']))
