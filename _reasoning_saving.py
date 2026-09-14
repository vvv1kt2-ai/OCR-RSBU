# -*- coding: utf-8 -*-
"""Проекция экономии от отключения рассуждений на весь корпус.

Отдельно проверяются три роли: у эскалации своя модель, и именно она даёт половину
цены, поэтому «работает ли параметр там» — не мелочь.
"""
import io, json, os, sys, time, urllib.request

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR
import fitz

PDF = r'D:\data-scraping\downloads\Артген (ИСКЧ)_6мес_2026.pdf'
PAGE = 3
pv = PR.active('plusvibe')
key = PR.load_key(pv)


def render(dpi):
    d = fitz.open(PDF)
    try:
        return P.render_png(d[PAGE - 1], dpi)
    finally:
        d.close()


def probe(role, dpi, extra):
    img = render(dpi)
    msgs = [P.img_message(img, P.TRANSCRIBE_PROMPT)]
    url, headers, body = PR.build_request(pv, pv.roles[role], msgs, key,
                                          temperature=0.1, max_tokens=8192)
    b = json.loads(body.decode('utf-8'))
    b.update(extra)
    req = urllib.request.Request(url, data=json.dumps(b, ensure_ascii=False).encode('utf-8'),
                                 method='POST', headers=headers)
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.loads(r.read())
        hdrs = dict(r.headers)
    u = resp.get('usage') or {}
    det = u.get('completion_tokens_details') or {}
    cost, _ = PR.call_cost(pv, pv.roles[role], u.get('prompt_tokens', 0),
                           u.get('completion_tokens', 0), hdrs)
    txt = resp['choices'][0]['message']['content'] or ''
    return {'role': role, 'extra': extra, 'pt': u.get('prompt_tokens', 0),
            'ct': u.get('completion_tokens', 0),
            'reasoning': det.get('reasoning_tokens') or 0,
            'chars': len(txt), 'cost': cost,
            'finish': resp['choices'][0].get('finish_reason')}


print('=== работает ли параметр на всех трёх ролях ===')
print('%-8s %-22s %7s %7s %8s %8s %9s' % ('роль', 'параметр', 'вход', 'выход',
                                           'рассужд', 'знаков', 'цена ₽'))
res = []
for role, dpi in (('main', 200), ('esc', 300), ('detect', 200)):
    for label, extra in (('как сейчас', {}), ('reasoning_effort=none', {'reasoning_effort': 'none'})):
        try:
            r = probe(role, dpi, extra)
            r['label'] = label
            res.append(r)
            print('%-8s %-22s %7d %7d %8d %8d %9.4f'
                  % (role, label, r['pt'], r['ct'], r['reasoning'], r['chars'], r['cost']))
        except Exception as e:
            print('%-8s %-22s ОШИБКА %s' % (role, label, str(e)[:70]))
            res.append({'role': role, 'label': label, 'error': str(e)[:200]})

json.dump(res, io.open(r'D:\models\_reasoning_roles.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print()
print('стоимость опыта: %.4f ₽' % sum(r.get('cost', 0) for r in res))

# --- проекция на весь корпус ------------------------------------------------
print()
print('=== проекция: наш прогон 20 документов, цены PlusVibe ===')
U = json.load(io.open(r'D:\models\_pv_usage.json', encoding='utf-8'))
UROWS = U['rows'] if isinstance(U, dict) else U
PRICES = {'main': (3.78, 18.86), 'esc': (49.03, 245.15), 'detect': (0.76, 3.02)}
import hashlib
pvmap = {}
for role in ('detect', 'main', 'esc'):
    pvmap[hashlib.sha1(pv.roles[role].encode()).hexdigest()[:10]] = role
for role in ('detect', 'main', 'esc'):
    pvmap.setdefault(hashlib.sha1(P.ACTIVE_PROFILE.roles[role].encode()).hexdigest()[:10], role)

# доля текстовых токенов в выходе — из опыта на 20 страницах
NQ = json.load(io.open(r'D:\models\_reasoning_quality.json', encoding='utf-8'))
text_share = (sum(r['chars'] for r in NQ['rows']) / 1.95) / sum(r['ct'] for r in NQ['rows'])
print('по опыту на 20 страницах доля текстовых токенов в выходе: %.0f%%'
      % (100 * text_share))
print()
print('%-8s %10s %10s %12s %12s %10s' % ('роль', 'выход тк', 'текст тк', 'цена ₽',
                                          'цена без', 'экономия'))
print('%-8s %10s %10s %12s %12s %10s' % ('', 'сейчас', 'без рассужд', 'сейчас',
                                          'рассужд.', '₽'))
print('-' * 74)
tot_now = tot_off = 0.0
for r in UROWS:
    role = pvmap.get(r['sha1'], '?')
    pin, pout = PRICES.get(role, (0, 0))
    now = r['pt'] / 1e6 * pin + r['ct'] / 1e6 * pout
    off = r['pt'] / 1e6 * pin + r['ct'] * text_share / 1e6 * pout
    tot_now += now
    tot_off += off
    print('%-8s %10d %10d %12.2f %12.2f %10.2f'
          % (role, r['ct'], int(r['ct'] * text_share), now, off, now - off))
print('-' * 74)
print('%-8s %10s %10s %12.2f %12.2f %10.2f'
      % ('ИТОГО', '', '', tot_now, tot_off, tot_now - tot_off))
print()
print('пилот 20 документов: %.0f ₽ -> %.0f ₽' % (tot_now, tot_off))
print('полный корпус (×8.8): %.0f ₽ -> %.0f ₽' % (tot_now * 8.8, tot_off * 8.8))
print()
print('Цель 300 ₽ за полный прогон: %s'
      % ('ДОСТИГНУТА' if tot_off * 8.8 <= 300 else 'не достигнута (%.0f ₽)' % (tot_off * 8.8)))
