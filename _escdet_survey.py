# -*- coding: utf-8 -*-
r"""Разведка перед проверкой эскалации и детекции: объём, арбитры, цена повтора.

Нужна, чтобы не гадать о размере выборки. Печатает только сводку.
"""
import io, os, re, json, sys

sys.path.insert(0, r'D:\models')
import pipeline as P          # кладёт pylibs в sys.path
import providers as PR
import fitz

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
DL = r'D:\data-scraping\downloads'

res_files = sorted(f for f in os.listdir(EX)
                   if f.endswith('.json') and not f.startswith('_'))
print('результатов документов: %d' % len(res_files))

one = json.load(io.open(os.path.join(EX, res_files[0]), encoding='utf-8'))
print('пример: %s' % res_files[0])
print('  верхние поля: %s' % sorted(one.keys()))
for k, v in sorted(one.items()):
    if isinstance(v, dict) and k not in ('source',):
        print('  %s -> %s' % (k, sorted(v.keys())[:8]))
    elif isinstance(v, list) and v and isinstance(v[0], dict):
        print('  %s[%d] -> %s' % (k, len(v), sorted(v[0].keys())[:8]))

# --- артефакты эскалации ----------------------------------------------------
esc = [f for f in os.listdir(PAGES) if f.startswith('_llm_') and '_esc_' in f
       and f.endswith('.json')]
det = [f for f in os.listdir(PAGES) if f.startswith('_llm_') and f.endswith('_detect.json')]
print()
print('артефактов эскалации: %d' % len(esc))
print('артефактов детекции: %d' % len(det))
print('пример имени эскалации: %s' % (esc[0] if esc else 'нет'))
print('пример имени детекции : %s' % (det[0] if det else 'нет'))

# --- где текстовый слой -----------------------------------------------------
def has_layer(pdf, page):
    try:
        d = fitz.open(pdf)
    except Exception:
        return None
    try:
        if page < 1 or page > d.page_count:
            return None
        return len(d[page - 1].get_text())
    finally:
        d.close()


# --- что эскалировалось и во что это обойдётся ------------------------------
pv = PR.active('plusvibe')
PIN, POUT = pv.price_of(pv.roles['esc'])
print()
print('цена эскалации у PlusVibe: %s/%s ₽ за 1М' % (PIN, POUT))

rows = []
for rf in res_files:
    stem = os.path.splitext(rf)[0]
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    # какие формы эскалировались — по наличию артефакта.
    # имя артефакта содержит расширение файла: _llm_<имя.pdf>_esc_<форма>[_pv].json
    forms = []
    for f in esc:
        m = re.match(r'_llm_%s\.pdf_esc_(.+?)(?:_pv)?\.json$' % re.escape(stem), f)
        if m:
            forms.append(m.group(1))
    if not forms:
        continue
    pages = set()
    for fk in forms:
        fd = doc.get(fk) or {}
        for p in (fd.get('transcript_pages') or []):
            pages.add(p)
    pdf = os.path.join(DL, stem + '.pdf')
    layers = {}
    for p in sorted(pages):
        layers[p] = has_layer(pdf, p)
    rows.append({'stem': stem, 'forms': forms, 'pages': sorted(pages),
                 'layers': layers})

print()
print('=== документы, где эскалация сработала ===')
print('%-34s %-26s %5s %8s %10s' % ('документ', 'формы', 'стр.', 'со слоем', 'цена ₽'))
print('-' * 90)
tot_pages = tot_cost = 0
for r in rows:
    nlay = sum(1 for v in r['layers'].values() if v and v > 200)
    # оценка: страница 300 dpi в эскалации стоила ~4781 pt и ~1932 ct
    cost = len(r['pages']) * (4781 / 1e6 * PIN + 1932 / 1e6 * POUT)
    tot_pages += len(r['pages'])
    tot_cost += cost
    print('%-34s %-26s %5d %8d %10.2f'
          % (r['stem'][:34], ','.join(r['forms'])[:26], len(r['pages']), nlay, cost))
print('-' * 90)
print('%-34s %-26s %5d %8s %10.2f' % ('ИТОГО', '', tot_pages, '', tot_cost))
print()
print('документов с эскалацией: %d из %d' % (len(rows), len(res_files)))
print('оценка полного повтора эскалации у PlusVibe: %.2f ₽' % tot_cost)

# --- кандидаты на проверку эскалации: где текстовый слой сумеет рассудить ---
print()
print('=== где есть чем судить (текстовый слой > 200 знаков) ===')
n = 0
for r in rows:
    good = [p for p, v in r['layers'].items() if v and v > 200]
    if good:
        n += 1
        print('  %-34s стр. %s' % (r['stem'][:34], good))
print('таких документов: %d' % n)

json.dump(rows, io.open(r'D:\models\_escdet_survey.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print()
print('-> _escdet_survey.json')
