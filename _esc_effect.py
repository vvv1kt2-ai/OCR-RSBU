# -*- coding: utf-8 -*-
r"""Помогает ли эскалация: проходит ли проверка после неё.

Эскалация запускается только тогда, когда арифметическая проверка формы не прошла.
Значит исходное состояние известно: проверка падала. Здесь смотрится, что стало с
проверкой в итоговом результате — то есть сработала ли дорогая часть конвейера.

Бесплатно: только чтение уже посчитанных результатов.
"""
import io, os, re, json, sys
from collections import Counter

sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')

res_files = sorted(f for f in os.listdir(EX)
                   if f.endswith('.json') and not f.startswith('_'))

esc = {}
for f in os.listdir(PAGES):
    m = re.match(r'_llm_(.+?)\.pdf_esc_(.+?)(?:_pv)?\.json$', f)
    if m:
        esc.setdefault(m.group(1), []).append(m.group(2))

print('=== что стало с проверкой там, где сработала эскалация ===')
print('%-32s %-18s %6s %-46s' % ('документ', 'форма', 'прошла', 'правило'))
print('-' * 104)
stat = Counter()
rows = []
for rf in res_files:
    stem = os.path.splitext(rf)[0]
    if stem not in esc:
        continue
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    for form in esc[stem]:
        ch = [c for c in (doc.get('checks') or []) if c.get('form') == form]
        if not ch:
            continue
        for c in ch:
            ok = bool(c.get('ok'))
            stat['ok' if ok else 'fail'] += 1
            rule = re.sub(r'\s+', ' ', str(c.get('rule') or ''))[:46]
            print('%-32s %-18s %6s %-46s'
                  % (stem[:32], form[:18], 'да' if ok else 'НЕТ', rule))
            rows.append({'stem': stem, 'form': form, 'ok': ok,
                         'rule': c.get('rule'),
                         'per_column': c.get('per_column')})
print('-' * 104)
print('проверок по эскалированным формам: %d, из них проходят: %d, падают: %d'
      % (stat['ok'] + stat['fail'], stat['ok'], stat['fail']))

# --- сколько раз эскалация была отклонена защитой ---------------------------
print()
print('=== предупреждения про эскалацию в результатах ===')
warn = Counter()
for rf in res_files:
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    for w in (doc.get('warnings') or []):
        if 'эскалац' in w or 'escalat' in w:
            warn[re.sub(r'\d+', 'N', w)[:78]] += 1
for w, n in warn.most_common():
    print('  %3d  %s' % (n, w))
if not warn:
    print('  нет')

# --- статус документов ------------------------------------------------------
print()
print('=== статус документов ===')
st = Counter()
for rf in res_files:
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    st[doc.get('status')] += 1
print(dict(st))

json.dump(rows, io.open(r'D:\models\_esc_effect.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
