# -*- coding: utf-8 -*-
r"""Доказательство дефекта детекции: она относит пояснения к балансу.

Первоисточник — файл детекции _llm_<документ>_detect.json, а не пересказ. Здесь он
сопоставляется с тем, что реально написано в транскриптах страниц, и считается, во
что это обошлось: лишние страницы транскрибируются, а эскалация берёт первые восемь
страниц списка — если список засорён пояснениями, дорогая модель читает пояснения.
"""
import io, os, re, json, sys
from collections import Counter

sys.path.insert(0, r'D:\models')
import pipeline as P
import providers as PR

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
DL = r'D:\data-scraping\downloads'
MAIN_TAG = P.model_tag(P.M_MAIN)
TR = re.compile(r'^(.+)_p(\d+)_200_(.+?)_([0-9a-f]{10})\.md$')


def transcript(stem, page):
    for fn in os.listdir(PAGES):
        m = TR.match(fn)
        if m and m.group(1) == stem and int(m.group(2)) == page and m.group(3) == MAIN_TAG:
            return io.open(os.path.join(PAGES, fn), encoding='utf-8').read()
    return None


def classify(txt):
    t = (txt or '').replace('\u00a0', ' ')
    if 'Пояснения к бухгалтерскому балансу' in t or 'Пояснения к балансу' in t:
        return 'notes'
    if '0710001' in t or 'Бухгалтерский баланс' in t:
        return 'balance'
    if '0710002' in t or 'финансовых результатах' in t:
        return 'income_statement'
    if '0710004' in t or '0710005' in t or 'движении денежных средств' in t:
        return 'cash_flow'
    return 'other'


# --- первоисточник: что сказала детекция ------------------------------------
print('=== файл детекции по документу Артген (ИСКЧ)_6мес_2025 ===')
dp = os.path.join(PAGES, '_llm_Артген (ИСКЧ)_6мес_2025_detect.json')
if os.path.exists(dp):
    m = json.load(io.open(dp, encoding='utf-8'))
    print('записей: %d' % len(m))
    by = {}
    for e in m:
        by.setdefault(e.get('form'), []).append(e.get('page'))
    for f in sorted(by):
        print('  %-18s %s' % (f, sorted(by[f])))
else:
    print('файла нет')

# --- по всем документам -----------------------------------------------------
res_files = sorted(f for f in os.listdir(EX)
                   if f.endswith('.json') and not f.startswith('_'))
pv = PR.active('plusvibe')
M_IN, M_OUT = pv.price_of(pv.roles['main'])
E_IN, E_OUT = pv.price_of(pv.roles['esc'])
# измерено на нашем прогоне: основная модель 1797 pt и 5472 ct на вызов
PAGE_COST = 1797 / 1e6 * M_IN + 5472 / 1e6 * M_OUT
ESC_COST = 4781 / 1e6 * E_IN + 1932 / 1e6 * E_OUT
print()
print('цена страницы 200 dpi у PlusVibe: %.3f ₽; страницы эскалации 300 dpi: %.3f ₽'
      % (PAGE_COST, ESC_COST))

rows = []
for rf in res_files:
    stem = os.path.splitext(rf)[0]
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    # есть ли эскалация по этому документу
    esc_forms = set()
    for f in os.listdir(PAGES):
        mm = re.match(r'_llm_%s\.pdf_esc_(.+?)(?:_pv)?\.json$' % re.escape(stem), f)
        if mm:
            esc_forms.add(mm.group(1))
    for form in ('balance', 'income_statement', 'cash_flow'):
        plist = (doc.get(form) or {}).get('transcript_pages') or []
        plist = [p for p in plist if isinstance(p, int)]
        if not plist:
            continue
        bad = []
        for p in plist:
            t = transcript(stem, p)
            if t is None:
                continue
            if classify(t) in ('notes', 'other') and classify(t) != form:
                # 'other' не улика: продолжение формы тоже без шапки
                if classify(t) == 'notes':
                    bad.append(p)
        # первые 8 страниц — то, что возьмёт эскалация
        esc_waste = 0
        if form in esc_forms:
            for p in plist[:8]:
                t = transcript(stem, p)
                if t and classify(t) == 'notes':
                    esc_waste += 1
        if bad or esc_waste:
            rows.append({'stem': stem, 'form': form, 'pages': len(plist),
                         'notes': sorted(bad), 'esc_pages': plist[:8],
                         'esc_notes': esc_waste, 'escalated': form in esc_forms})

print()
print('=== документы, где в форму попали страницы пояснений ===')
print('%-32s %-9s %5s %6s %9s %10s' % ('документ', 'форма', 'стр.', 'поясн.',
                                       'эскалация', 'цена ₽'))
print('-' * 82)
tot_pages = tot_esc = 0
cost = 0.0
for r in rows:
    c = len(r['notes']) * PAGE_COST + r['esc_notes'] * ESC_COST
    cost += c
    tot_pages += len(r['notes'])
    tot_esc += r['esc_notes']
    print('%-32s %-9s %5d %6d %9s %10.2f'
          % (r['stem'][:32], r['form'], r['pages'], len(r['notes']),
             ('да, %d из 8' % r['esc_notes']) if r['escalated'] else 'нет', c))
print('-' * 82)
print('%-32s %-9s %5s %6d %9d %10.2f' % ('ИТОГО', '', '', tot_pages, tot_esc, cost))
print()
print('документов с засорением: %d' % len(rows))
print('страниц пояснений транскрибировано зря: %d' % tot_pages)
print('из них продублировано дорогой моделью на эскалации: %d' % tot_esc)
print('оценка потерь: %.2f ₽ на %d документах пилота' % (cost, len(res_files)))
print('в пересчёте на корпус (масштаб 5.1): %.0f ₽' % (cost * 5.1))
print()
print('Это НИЖНЯЯ оценка: страницы-продолжения пояснений не имеют шапки,')
print('поэтому мой классификатор их не видит и в счёт не включает.')

json.dump(rows, io.open(r'D:\models\_detect_proof.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
