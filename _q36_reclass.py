# -*- coding: utf-8 -*-
r"""Q36: how many of the cross-year conflicts are explained by regrouping?

Detector B flags every row whose value on a date shared by the same emitter's 2025 and
2026 reports differs. Most such rows are NOT extraction errors: a later report regroups
line items, so one code rises while another falls by the same amount and the form total
is unchanged. The decisive question is therefore the FORM TOTAL, not the row.

For each (emitter, form, shared date) this script compares the form total — 1600/1700 for
the balance, 2400 for the income statement, 4400/4500 for the cash flow — and classifies:

  итог совпал        the totals are equal; every row difference is regrouping
  итог ±2            the totals differ by at most 2 units: digit-level noise
  итог разошёлся     the totals differ materially: a real discrepancy to check against PDF

Writes `_q36_reclass.md`. Read-only.
"""
import os, re, json, glob, collections, datetime

EX = r'D:\models\extracted'
FORMS = ('balance', 'income_statement', 'cash_flow')
TOTALS = {'balance': ('1600', '1700'), 'income_statement': ('2400',),
          'cash_flow': ('4400', '4500')}
MONTHS = {'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
          'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12}


def date_key(label):
    s = re.sub(r'\s+', ' ', str(label or '')).strip()
    m = re.search(r'(\d{1,2})\s+([А-Яа-яЁё]+)\s+(\d{4})', s)
    if m and m.group(2).lower() in MONTHS:
        return '%s-%02d-%02d' % (m.group(3), MONTHS[m.group(2).lower()], int(m.group(1)))
    m = re.search(r'(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})', s)
    if m:
        return '%s-%02d-%02d' % (m.group(3), int(m.group(2)), int(m.group(1)))
    return None


def dates(res):
    out = {}
    for i, c in enumerate((res or {}).get('columns') or []):
        k = date_key(c)
        if k:
            out.setdefault(k, i)
    return out


def flat(res):
    """(code, name) -> item, whole tree"""
    out = {}
    for it in (res or {}).get('items') or []:
        for rec in [it] + (it.get('children') or []):
            out.setdefault((str(rec.get('code')), (rec.get('name') or '').strip()), rec)
    return out


def top(res):
    out = {}
    for it in (res or {}).get('items') or []:
        if it.get('code'):
            out.setdefault(str(it['code']), it)
    return out


def val(item, idx):
    if item is None:
        return None
    v = item.get('values') or []
    return v[idx] if idx < len(v) else None


def total_of(res, form, idx):
    """the form's own total, tried in order (1600, then 1700, ...)"""
    t = top(res)
    for code in TOTALS.get(form, ()):
        x = val(t.get(code), idx)
        if x is not None:
            return code, x
    return None, None


docs = {}
for f in sorted(glob.glob(os.path.join(EX, '*.json'))):
    b = os.path.basename(f)
    if b.startswith('_'):
        continue
    docs[b[:-5]] = json.load(open(f, encoding='utf-8'))

by_emitter = collections.defaultdict(dict)
for key in docs:
    m = re.match(r'^(.*)_6мес_(\d{4})$', key)
    if m:
        by_emitter[m.group(1)][m.group(2)] = key

cases = []
for emitter, years in sorted(by_emitter.items()):
    if '2025' not in years or '2026' not in years:
        continue
    a, b = docs[years['2025']], docs[years['2026']]
    for form in FORMS:
        da, db = dates(a.get(form)), dates(b.get(form))
        fa, fb = flat(a.get(form)), flat(b.get(form))
        ta, tb = top(a.get(form)), top(b.get(form))
        for d in sorted(set(da) & set(db)):
            ia, ib = da[d], db[d]
            rows = []
            for key in sorted(set(fa) & set(fb), key=lambda x: (str(x[0]), x[1])):
                x, y = val(fa[key], ia), val(fb[key], ib)
                if x is None or y is None or x == y:
                    continue
                rows.append({'code': key[0], 'name': key[1][:34], 'v2025': x, 'v2026': y,
                             'diff': y - x})
            if not rows:
                continue
            ca, va = total_of(a.get(form), form, ia)
            cb, vb = total_of(b.get(form), form, ib)
            tdiff = None if (va is None or vb is None) else vb - va
            if tdiff is None:
                kind = 'итог не найден'
            elif tdiff == 0:
                kind = 'итог совпал'
            elif abs(tdiff) <= 2:
                kind = 'итог ±2'
            else:
                kind = 'итог разошёлся'
            cases.append({'emitter': emitter, 'form': form, 'date': d, 'rows': rows,
                          'total_code': ca or cb, 'total_2025': va, 'total_2026': vb,
                          'total_diff': tdiff, 'kind': kind,
                          'max_row_diff': max(abs(r['diff']) for r in rows),
                          'abs_row_sum': sum(abs(r['diff']) for r in rows)})

def fmt(v):
    """1234567 -> '1 234 567', the way the reports print it"""
    return '{:,}'.format(int(v)).replace(',', ' ')


def transcript_files(stem, form):
    """page transcripts of this document that belong to this form's pages"""
    d = docs.get(stem) or {}
    res = d.get(form) or {}
    pages = [p for p in (res.get('transcript_pages') or []) if isinstance(p, int)]
    out = []
    for p in pages:
        out.extend(glob.glob(os.path.join(EX, 'pages', '%s_p%d_*.md' % (stem, p))))
    return out


def in_own_transcript(stem, form, value):
    """does the document's own transcript print this exact number?"""
    if value is None:
        return None
    needle = fmt(value)
    for p in transcript_files(stem, form):
        try:
            if needle in open(p, encoding='utf-8').read():
                return True
        except Exception:
            pass
    return False


kinds = collections.Counter(c['kind'] for c in cases)
row_total = sum(len(c['rows']) for c in cases)

# fidelity: for every pair whose form total differs, does each JSON reproduce its own
# transcript? If yes, the difference is printed in the source, not introduced by OCR.
stem_of = {}
for k in docs:
    m = re.match(r'^(.*)_6мес_(\d{4})$', k)
    if m:
        stem_of[(m.group(1), m.group(2))] = k

for c in cases:
    if c['kind'] == 'итог совпал':
        continue
    s25, s26 = stem_of.get((c['emitter'], '2025')), stem_of.get((c['emitter'], '2026'))
    c['fidelity_2025'] = in_own_transcript(s25, c['form'], c['total_2025']) if s25 else None
    c['fidelity_2026'] = in_own_transcript(s26, c['form'], c['total_2026']) if s26 else None


L = ['# Q36: разбор расхождений на совпадающих датах\n',
     'Дата прогона: %s\n' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
     'Пар (эмитент, форма, общая дата) с расхождениями: **%d**' % len(cases),
     'Строк в них: **%d**\n' % row_total,
     '| вердикт по ИТОГУ формы | пар | строк |',
     '|---|---|---|']
for k in ('итог совпал', 'итог ±2', 'итог разошёлся', 'итог не найден'):
    if kinds.get(k):
        L.append('| %s | %d | %d |' % (k, kinds[k],
                                       sum(len(c['rows']) for c in cases if c['kind'] == k)))

L.append('\n## Вывод\n')
explained = kinds.get('итог совпал', 0) + kinds.get('итог ±2', 0)
L.append('Из %d пар **%d** (%d%%) объясняются перегруппировкой или цифровым шумом: '
         'итог формы совпадает или расходится на 1–2 единицы, а расхождения строк — '
         'это перенос сумм между статьями.\n'
         % (len(cases), explained, round(100 * explained / max(1, len(cases)))))

L.append('## Пары, где итог формы разошёлся материально\n')
L.append('| эмитент | форма | дата | код итога | 2025 | 2026 | разница | строк | макс. расхождение строки |')
L.append('|---|---|---|---|---|---|---|---|---|')
mat = [c for c in cases if c['kind'] == 'итог разошёлся']
for c in sorted(mat, key=lambda x: -abs(x['total_diff'])):
    L.append('| %s | %s | %s | %s | %s | %s | %s | %d | %s |' % (
        c['emitter'], c['form'], c['date'], c['total_code'], c['total_2025'],
        c['total_2026'], c['total_diff'], len(c['rows']), c['max_row_diff']))

L.append('\n## Верность «JSON ↔ собственный транскрипт» для расходящихся итогов\n')
L.append('Проверка: печатает ли собственный транскрипт документа ровно то число, которое '
         'попало в JSON. Если да — расхождение напечатано в самих отчётах, а не внесено '
         'распознаванием.\n')
L.append('| эмитент | форма | итог 2025 | найден в транскрипте 2025 | итог 2026 | найден в транскрипте 2026 | вердикт |')
L.append('|---|---|---|---|---|---|---|')
for c in sorted(cases, key=lambda x: (x['emitter'], x['form'])):
    if c['kind'] == 'итог совпал':
        continue
    f1, f2 = c.get('fidelity_2025'), c.get('fidelity_2026')
    if f1 and f2:
        verdict = 'напечатано в отчётах — не ошибка распознавания'
    elif f1 is False or f2 is False:
        verdict = '**нет в своём транскрипте — проверить**'
    else:
        verdict = 'не проверено'
    L.append('| %s | %s | %s | %s | %s | %s | %s |' % (
        c['emitter'], c['form'], c['total_2025'], f1, c['total_2026'], f2, verdict))

L.append('\n## Все пары\n')
L.append('| эмитент | форма | дата | вердикт | разница итога | строк | примеры строк (2025 -> 2026) |')
L.append('|---|---|---|---|---|---|---|')
for c in sorted(cases, key=lambda x: (x['emitter'], x['form'])):
    ex = '; '.join('%s %s->%s' % (r['code'], r['v2025'], r['v2026']) for r in c['rows'][:4])
    L.append('| %s | %s | %s | %s | %s | %d | %s |' % (
        c['emitter'], c['form'], c['date'], c['kind'], c['total_diff'], len(c['rows']), ex))

open(r'D:\models\_q36_reclass.md', 'w', encoding='utf-8').write('\n'.join(L))
json.dump(cases, open(r'D:\models\_q36_reclass.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print('pairs              :', len(cases))
print('rows               :', row_total)
print('by verdict         :', dict(kinds))
print('material total diff:')
for c in sorted(mat, key=lambda x: -abs(x['total_diff'])):
    print('   %-24s %-16s %s total %s -> %s (%s), rows %d'
          % (c['emitter'], c['form'], c['date'], c['total_2025'], c['total_2026'],
             c['total_diff'], len(c['rows'])))
print('report -> D:\\models\\_q36_reclass.md')
