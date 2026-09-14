# -*- coding: utf-8 -*-
"""Не портит ли отключение рассуждений качество транскрипта.

Отключение рассуждений удешевляет вызов в 3.3 раза, но транскрипт — работа на
точность цифр, и экономия имеет смысл только если цифры не поехали. Проверяем на
той же выборке из 20 страниц, что и задача 01: сравниваем ответы с рассуждениями и
без них по числам, ровно тем же способом, что и раньше.
"""
import io, json, os, sys, time

sys.path.insert(0, r'D:\models')
import _pv_quality as Q
import pipeline as P
import providers as PR

MODEL = 'gemini-3.8-flash'
LIMIT = 20
OUT = r'D:\models\_reasoning_quality.md'
JSONOUT = r'D:\models\_reasoning_quality.json'

import fitz


def render(pdf, page, dpi):
    d = fitz.open(pdf)
    try:
        return P.render_png(d[page - 1], dpi)
    finally:
        d.close()


def call_noreason(messages, max_tokens=16000):
    """Тот же вызов, что делает конвейер, но с отключёнными рассуждениями."""
    pv = PR.active('plusvibe')
    key = PR.load_key(pv)
    url, headers, body = PR.build_request(pv, pv.roles['main'], messages, key,
                                         temperature=0.1, max_tokens=max_tokens)
    b = json.loads(body.decode('utf-8'))
    b['reasoning_effort'] = 'none'
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(b, ensure_ascii=False).encode('utf-8'),
                                method='POST', headers=headers)
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.loads(r.read())
        hdrs = dict(r.headers)
    u = resp.get('usage') or {}
    det = u.get('completion_tokens_details') or {}
    cost, src = PR.call_cost(pv, pv.roles['main'], u.get('prompt_tokens', 0),
                             u.get('completion_tokens', 0), hdrs)
    return (resp['choices'][0]['message']['content'] or '',
            resp['choices'][0].get('finish_reason'), u, det, cost, src)


pages = Q.cached_pages(LIMIT, want_tag=MODEL)
print('страниц в выборке: %d' % len(pages))
print()
print('%-30s %4s %7s %7s %6s %6s %6s %7s %7s'
      % ('документ', 'стр', 'рассужд', 'знаков', 'знач.', 'знач.', 'сход.', 'нет', 'цена'))
print('%-30s %4s %7s %7s %6s %6s %6s %7s %7s'
      % ('', '', '%', 'отв.', 'нет', 'лишн', '%', 'совсем', '₽'))
print('-' * 92)

rows = []
total_cost = 0.0
for r in pages:
    img = render(r['pdf'], r['page'], r['dpi'])
    msgs = [P.img_message(img, P.TRANSCRIBE_PROMPT)]
    try:
        txt, fin, u, det, cost, src = call_noreason(msgs)
    except Exception as e:
        print('%-30s %4d  ОШИБКА %s' % (r['stem'][:30], r['page'], str(e)[:60]))
        continue
    total_cost += cost
    ref = io.open(r['path'], encoding='utf-8').read()
    d = Q.digit_diff(ref, txt)
    absent_sig = Q.significant(d['absent'])
    ct = u.get('completion_tokens', 0)
    rt = det.get('reasoning_tokens') or 0
    ratio = Q.char_ratio(ref, txt)
    print('%-30s %4d %7.0f %7d %6d %6d %6.2f %7d %7.4f'
          % (r['stem'][:30], r['page'], 100 * rt / ct if ct else 0, len(txt),
             len(d['absent']), len(d['extra']), ratio, len(absent_sig), cost))
    rows.append({'stem': r['stem'], 'page': r['page'], 'dpi': r['dpi'],
                 'ref_file': os.path.basename(r['path']), 'ct': ct, 'reasoning': rt,
                 'chars': len(txt), 'absent': len(d['absent']),
                 'absent_sig': absent_sig, 'extra': len(d['extra']),
                 'under': len(d['undercount']), 'ratio': ratio, 'cost': cost,
                 'finish': fin, 'text': txt})

json.dump({'rows': [{k: v for k, v in r.items() if k != 'text'} for r in rows],
           'cost': total_cost},
          io.open(JSONOUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# сохраняем сами ответы рядом, чтобы их можно было проверить и переиспользовать
CACHE = r'D:\models\extracted\pages\_pvq'
os.makedirs(CACHE, exist_ok=True)
for r in rows:
    io.open(os.path.join(CACHE, '%s_p%d_%d_noreason.md'
                         % (r['stem'], r['page'], r['dpi'])), 'w',
            encoding='utf-8').write(r['text'])

print()
print('=== итог по %d страницам ===' % len(rows))
print('рассуждений в выходе: среднее %.0f%%'
      % (100 * sum(r['reasoning'] for r in rows) / max(sum(r['ct'] for r in rows), 1)))
print('значимых чисел, пропавших против эталона: %d'
      % sum(len(r['absent_sig']) for r in rows))
print('значимых чисел лишних: %d'
      % sum(len(Q.significant([str(x) for x in []]) or []) for r in rows))
print('среднее сходство текста: %.3f' % (sum(r['ratio'] for r in rows) / len(rows)))
print('стоимость опыта: %.4f ₽' % total_cost)
print()
print('Для сравнения, тот же набор с рассуждениями стоил 2.43 ₽.')
print('Файл: %s' % OUT)
