# -*- coding: utf-8 -*-
r"""Окупаемость эскалации: сколько строк она исправила и сколько это стоило.

Эскалация — 51% цены пилота. Проверяю по кэшу и артефактам, какая её часть
исправила хотя бы одну строку, а какая отработала впустую (0 исправлений).
Впустую — это либо «документ действительно не сходится» (второе мнение), либо
отклонение защитой от чужого документа, либо провал самой эскалации.
"""
import io, os, json, re

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
ESC_PAGE = 0.708  # ₽ за страницу 300 dpi (PlusVibe), измерено

# сколько страниц эскалировалось по каждой (документ, форма)
pages = {}
for f in os.listdir(PAGES):
    m = re.search(r'_esc_(balance|income_statement|cash_flow)', f)
    if not m:
        continue
    stem = re.sub(r'^_llm_', '', re.sub(r'\.pdf_esc_.*$', '', f))
    pages.setdefault((stem, m.group(1)), set()).add(f)

rows = []
for (stem, form), files in sorted(pages.items()):
    path = os.path.join(EX, stem + '.json')
    if not os.path.exists(path):
        rows.append((stem, form, len(files), None, None, None, 'нет артефакта'))
        continue
    doc = json.load(io.open(path, encoding='utf-8'))
    d = doc.get(form) or {}
    items = d.get('items') or []
    corr = sum(1 for it in items if it.get('corrected_by'))
    conf = sum(1 for it in items if it.get('confirmed_by'))
    chks = [c for c in (doc.get('checks') or []) if c['form'] == form]
    ok = all(c.get('ok') for c in chks) if chks else None
    rejected = any('эскалация отклонена' in w for w in (doc.get('warnings') or []))
    unresolved = any('did not fully reconcile' in w for w in (doc.get('warnings') or []))
    tag = []
    if rejected:
        tag.append('отклонена защитой')
    if unresolved:
        tag.append('не сошлось')
    rows.append((stem, form, len(files), corr, conf, ok, ', '.join(tag)))

print('%-30s %-17s %5s %5s %5s %-9s %s'
      % ('документ', 'форма', 'стр.', 'испр', 'подтв', 'проверки', 'примечание'))
print('-' * 108)
tot_pages = 0
tot_cost = 0.0
useful_pages = 0
for stem, form, np_, corr, conf, ok, tag in rows:
    tot_pages += np_
    tot_cost += np_ * ESC_PAGE
    useful = bool(corr)
    if useful:
        useful_pages += np_
    print('%-30s %-17s %5d %5s %5s %-9s %s'
          % (stem[:30], form, np_, '-' if corr is None else corr,
             '-' if conf is None else conf,
             {True: 'пройдены', False: 'ПРОВАЛ', None: '?'}[ok], tag))
print('-' * 108)
print()
print('всего эскалированных (документ, форма): %d' % len(rows))
print('страниц 300 dpi: %d, стоимость %.2f ₽' % (tot_pages, tot_cost))
print()
n_useful = sum(1 for r in rows if r[3])
print('случаев, где исправлена хотя бы одна строка: %d из %d' % (n_useful, len(rows)))
print('страниц в них: %d (%.2f ₽) — это окупившаяся часть'
      % (useful_pages, useful_pages * ESC_PAGE))
print('страниц в случаях без единого исправления: %d (%.2f ₽)'
      % (tot_pages - useful_pages, (tot_pages - useful_pages) * ESC_PAGE))
print()
print('=== разбор пустых случаев ===')
for stem, form, np_, corr, conf, ok, tag in rows:
    if corr == 0:
        print('  %-28s %-17s стр.%2d %.2f ₽  %s' % (stem[:28], form, np_, np_ * ESC_PAGE, tag))
json.dump([{'stem': r[0], 'form': r[1], 'pages': r[2], 'corrected': r[3],
            'confirmed': r[4], 'checks_ok': r[5], 'note': r[6]} for r in rows],
          io.open(r'D:\models\_esc_payoff.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
