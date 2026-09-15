# -*- coding: utf-8 -*-
r"""Окупаемость эскалации — только случаи, подтверждённые журналом предупреждений.

Кэш страниц переживает прогоны, поэтому наличие файла `_esc_<форма>` ещё не значит,
что эскалация была в ТОМ прогоне, чей JSON сохранён. Признак настоящего случая —
предупреждение, начинающееся с имени формы:
  '<форма>: fixed by escalation ...'
  '<форма>: escalation did not fully reconcile ...'
  '<форма>: эскалация отклонена — ...'
"""
import io, os, json, re

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
ESC_PAGE = 0.708

cases = {}
for f in os.listdir(PAGES):
    m = re.search(r'_esc_(balance|income_statement|cash_flow)', f)
    if m:
        stem = re.sub(r'^_llm_', '', re.sub(r'\.pdf_esc_.*$', '', f))
        cases.setdefault(stem, set()).add(m.group(1))

rows = []
for stem, forms in sorted(cases.items()):
    path = os.path.join(EX, stem + '.json')
    if not os.path.exists(path):
        continue
    doc = json.load(io.open(path, encoding='utf-8'))
    warns = doc.get('warnings') or []
    for form in sorted(forms):
        related = [w for w in warns if w.startswith(form + ':')]
        live = [w for w in related if re.search(
            r'fixed by escalation|did not fully reconcile|эскалация отклонена', w)]
        if not live:
            continue  # кэш остался от другого прогона
        d = doc.get(form) or {}
        tp = [p for p in (d.get('transcript_pages') or []) if isinstance(p, int)]
        pages = len(tp[:8])
        items = d.get('items') or []
        corr = sum(1 for it in items if it.get('corrected_by'))
        conf = sum(1 for it in items if it.get('confirmed_by'))
        chks = [c for c in (doc.get('checks') or []) if c['form'] == form]
        ok = all(c.get('ok') for c in chks) if chks else None
        kind = ('отклонена' if any('отклонена' in w for w in live)
                else 'не сошлось' if any('not fully reconcile' in w for w in live)
                else 'сошлось')
        rows.append((stem, form, pages, corr, conf, ok, kind))

print('=== эскалация: только подтверждённые журналом случаи ===')
print('%-30s %-17s %5s %5s %5s %-9s %s'
      % ('документ', 'форма', 'стр.', 'испр', 'подтв', 'проверки', 'итог'))
print('-' * 96)
tot = 0
for stem, form, pages, corr, conf, ok, kind in rows:
    tot += pages
    print('%-30s %-17s %5d %5d %5d %-9s %s'
          % (stem[:30], form, pages, corr, conf,
             {True: 'пройдены', False: 'ПРОВАЛ', None: '?'}[ok], kind))
print('-' * 96)
print('случаев: %d, страниц: %d, транскрипция %.2f ₽'
      % (len(rows), tot, tot * ESC_PAGE))
print()
use = [r for r in rows if r[3]]
nouse = [r for r in rows if not r[3]]
print('исправили строки:   %d случаев, %d стр. (%.2f ₽)'
      % (len(use), sum(r[2] for r in use), sum(r[2] for r in use) * ESC_PAGE))
print('не исправили:       %d случаев, %d стр. (%.2f ₽)'
      % (len(nouse), sum(r[2] for r in nouse), sum(r[2] for r in nouse) * ESC_PAGE))
print()
print('=== почему не исправили ===')
for stem, form, pages, corr, conf, ok, kind in nouse:
    print('  %-30s %-17s стр.%2d %.2f ₽  %-12s проверки: %s'
          % (stem[:30], form, pages, pages * ESC_PAGE, kind,
             {True: 'пройдены', False: 'ПРОВАЛ', None: '?'}[ok]))
json.dump([{'stem': r[0], 'form': r[1], 'pages': r[2], 'corrected': r[3],
            'confirmed': r[4], 'ok': r[5], 'kind': r[6]} for r in rows],
          io.open(r'D:\models\_esc_payoff3.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
