# -*- coding: utf-8 -*-
"""Проекция экономии — на парных измерениях, а не на догадке о знаках на токен.

Парное измерение с одной и той же страницы:
  как сейчас          : выход 3193, из них рассуждения 2412, текст  781
  reasoning_effort=none: выход  801, из них рассуждения    0, текст  801
Текст 781 против 801 — параметр снимает рассуждения и не трогает сам транскрипт.

Отсюда доля текста в выходе для основной модели берётся как отношение измеренного
выхода без рассуждений к среднему выходу на вызов в корпусном прогоне. Выборка из 20
страниц — самые крупные страницы корпуса, текста в них больше среднего, поэтому
оценка экономии получается заниженной, то есть осторожной.
"""
import io, json, hashlib, sys

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR

NQ = json.load(io.open(r'D:\models\_reasoning_quality.json', encoding='utf-8'))
U = json.load(io.open(r'D:\models\_pv_usage.json', encoding='utf-8'))
UROWS = U['rows'] if isinstance(U, dict) else U
pv = PR.active('plusvibe')

text_ct = sum(r['ct'] for r in NQ['rows'])
text_chars = sum(r['chars'] for r in NQ['rows'])
n = len(NQ['rows'])
print('=== парные измерения ===')
print('20 крупных страниц без рассуждений: выход %d тк, знаков %d, в среднем %d тк/стр'
      % (text_ct, text_chars, text_ct / n))
print('знаков на текстовый токен: %.2f' % (text_chars / text_ct))

main = [r for r in UROWS if r['len'] == 23][0]
avg_ct = main['ct'] / main['calls']
print('корпусный прогон, основная модель: %d вызовов, %d тк, в среднем %.0f тк/вызов'
      % (main['calls'], main['ct'], avg_ct))
print()
share = (text_ct / n) / avg_ct
print('доля текста в выходе: %d / %.0f = %.0f%%' % (text_ct / n, avg_ct, 100 * share))
print('(рассуждения — остальные %.0f%%)' % (100 * (1 - share)))

# --- цены -------------------------------------------------------------------
PRICES = {'main': (3.78, 18.86), 'esc': (49.03, 245.15), 'detect': (0.76, 3.02)}
pvmap = {}
for role in ('detect', 'main', 'esc'):
    pvmap[hashlib.sha1(pv.roles[role].encode()).hexdigest()[:10]] = role
for role in ('detect', 'main', 'esc'):
    pvmap.setdefault(
        hashlib.sha1(P.ACTIVE_PROFILE.roles[role].encode()).hexdigest()[:10], role)

# Параметр снимает рассуждения только у основной модели: у эскалации (Anthropic)
# доля рассуждений и без того мала и на параметр она не отзывается, у детекции
# рассуждений 92%, но она стоит копейки.
ROLE_SHARE = {'main': share, 'esc': 1.0, 'detect': 1.0}

print()
print('=== проекция, наш прогон 20 документов, цены PlusVibe ===')
print('%-8s %10s %10s %11s %11s %9s' % ('роль', 'выход тк', 'после', 'цена ₽',
                                         'цена после', 'экономия'))
print('-' * 68)
tn = to = 0.0
for r in UROWS:
    role = pvmap.get(r['sha1'], '?')
    pin, pout = PRICES.get(role, (0, 0))
    sh = ROLE_SHARE.get(role, 1.0)
    now = r['pt'] / 1e6 * pin + r['ct'] / 1e6 * pout
    off = r['pt'] / 1e6 * pin + r['ct'] * sh / 1e6 * pout
    tn += now
    to += off
    print('%-8s %10d %10d %11.2f %11.2f %9.2f'
          % (role, r['ct'], int(r['ct'] * sh), now, off, now - off))
print('-' * 68)
print('%-8s %10s %10s %11.2f %11.2f %9.2f' % ('ИТОГО', '', '', tn, to, tn - to))
print()
print('пилот (20 документов): %.0f ₽ -> %.0f ₽' % (tn, to))
print('полный корпус (×8.8):  %.0f ₽ -> %.0f ₽' % (tn * 8.8, to * 8.8))
print()
goal = 300
print('Цель %d ₽ за полный прогон: %s' % (goal,
      'ДОСТИГНУТА (%.0f ₽)' % (to * 8.8) if to * 8.8 <= goal
      else 'не достигнута (%.0f ₽)' % (to * 8.8)))
print()
print('Для сравнения:')
print('  Polza, как сейчас        : 986 ₽ пилот -> ~4100 ₽ корпус (измерено)')
print('  PlusVibe, как сейчас     : %.0f ₽ -> ~%.0f ₽' % (tn, tn * 8.8))
print('  PlusVibe без рассуждений : %.0f ₽ -> ~%.0f ₽' % (to, to * 8.8))
json.dump({'text_share_main': share, 'pilot_now': tn, 'pilot_off': to,
           'corpus_now': tn * 8.8, 'corpus_off': to * 8.8},
          io.open(r'D:\models\_reasoning_saving.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
