# -*- coding: utf-8 -*-
r"""Настоящий объём и окупаемость эскалации.

Прошлый замер спутал кэш СТРУКТУРИРОВАНИЯ (`_esc_<форма>`, один файл на форму) со
страницами. Страницы лежат под ключом `{stem}_p{стр}_{dpi}_{модель}...`. Считаю
страницы 300 dpi по `transcript_pages` формы (эскалация берёт их, обрезая до 8) и
сверяю итог с измеренными 59.48 ₽ на 84 вызова эскалации.
"""
import io, os, json, re, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
ESC_PAGE = 0.708

# страницы 300 dpi, реально лежащие в кэше
cache300 = {}
for f in os.listdir(PAGES):
    m = re.match(r'^(.*)_p(\d+)_300_', f)
    if m:
        cache300.setdefault(m.group(1), set()).add(int(m.group(2)))

# документы, где эскалация запускалась (по кэшу структурирования)
esc_struct = {}
for f in os.listdir(PAGES):
    m = re.search(r'_esc_(balance|income_statement|cash_flow)', f)
    if m:
        stem = re.sub(r'^_llm_', '', re.sub(r'\.pdf_esc_.*$', '', f))
        esc_struct.setdefault(stem, set()).add(m.group(1))

rows = []
for stem, forms in sorted(esc_struct.items()):
    path = os.path.join(EX, stem + '.json')
    doc = json.load(io.open(path, encoding='utf-8')) if os.path.exists(path) else {}
    for form in sorted(forms):
        d = doc.get(form) or {}
        tp = [p for p in (d.get('transcript_pages') or []) if isinstance(p, int)]
        pages = tp[:8] if len(tp) > 8 else tp
        items = d.get('items') or []
        corr = sum(1 for it in items if it.get('corrected_by'))
        conf = sum(1 for it in items if it.get('confirmed_by'))
        chks = [c for c in (doc.get('checks') or []) if c['form'] == form]
        ok = all(c.get('ok') for c in chks) if chks else None
        # страницы, для которых в кэше есть транскрипт 300 dpi
        have = len([p for p in pages if p in cache300.get(stem, set())])
        rows.append({'stem': stem, 'form': form, 'pages': len(pages), 'in_cache': have,
                     'corrected': corr, 'confirmed': conf, 'ok': ok})

print('%-30s %-17s %5s %6s %5s %5s %-9s'
      % ('документ', 'форма', 'стр.', 'в кэше', 'испр', 'подтв', 'проверки'))
print('-' * 92)
tot = 0
for r in rows:
    tot += r['pages']
    print('%-30s %-17s %5d %6d %5d %5d %-9s'
          % (r['stem'][:30], r['form'], r['pages'], r['in_cache'], r['corrected'],
             r['confirmed'], {True: 'пройдены', False: 'ПРОВАЛ', None: '?'}[r['ok']]))
print('-' * 92)
print('случаев эскалации: %d, страниц всего: %d, оценка %.2f ₽'
      % (len(rows), tot, tot * ESC_PAGE))
print('(измерено ранее: 84 вызова эскалации, 59.48 ₽ — сюда входит и структурирование)')
print()
print('страниц 300 dpi в кэше по документам (сверка):')
print('  документов: %d, страниц: %d' % (len(cache300), sum(len(v) for v in cache300.values())))
print()
n_use = [r for r in rows if r['corrected']]
print('исправили хотя бы строку: %d из %d случаев, страниц %d (%.2f ₽)'
      % (len(n_use), len(rows), sum(r['pages'] for r in n_use),
         sum(r['pages'] for r in n_use) * ESC_PAGE))
n_none = [r for r in rows if not r['corrected']]
print('не исправили ничего:      %d случаев, страниц %d (%.2f ₽)'
      % (len(n_none), sum(r['pages'] for r in n_none),
         sum(r['pages'] for r in n_none) * ESC_PAGE))
print()
print('из «не исправивших» проверки всё же прошли (эскалация не понадобилась):')
for r in n_none:
    if r['ok']:
        print('  %-30s %-17s стр.%d' % (r['stem'][:30], r['form'], r['pages']))
json.dump(rows, io.open(r'D:\models\_esc_payoff2.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
