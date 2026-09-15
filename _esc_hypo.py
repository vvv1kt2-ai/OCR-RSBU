# -*- coding: utf-8 -*-
r"""Три гипотезы экономии на эскалации — проверка по кэшу, без вызовов LLM.

Гипотеза 1: нужно ли 300 dpi, если та же страница уже прочитана на 200 dpi.
Гипотеза 2: сколько из прочитанных страниц вообще содержат провалившиеся коды.
Гипотеза 3: размер входа структурирования (от него зависит его цена).

Ключ кэша страницы: {stem}_p{стр}_{dpi}_{модель}{поставщик}_{отпечаток}.md
"""
import io, os, re, json, sys

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')

CACHE = re.compile(r'^(?P<stem>.+)_p(?P<p>\d+)_(?P<dpi>\d+)_(?P<rest>.+)\.md$')
# числа РСБУ: 1 234 567, 1234, -1 234; склеиваем разряды
NUM = re.compile(r'-?\d[\d\s\u00a0]*')


def numbers(text):
    out = set()
    for m in NUM.finditer(text):
        s = re.sub(r'[\s\u00a0]', '', m.group(0))
        s = s.lstrip('-')
        if 1 <= len(s) <= 12:
            out.add(s)
    return out


by_key = {}
for f in os.listdir(PAGES):
    m = CACHE.match(f)
    if not m:
        continue
    key = (m.group('stem'), int(m.group('p')))
    by_key.setdefault(key, {})[int(m.group('dpi'))] = f

both = [(k, v) for k, v in by_key.items() if 200 in v and 300 in v]
print('=== гипотеза 1: 200 dpi против 300 dpi на одной странице ===')
print('страниц, прочитанных дважды (200 и 300 dpi): %d' % len(both))
agree = 0
diff = []
for (stem, p), v in sorted(both):
    t200 = io.open(os.path.join(PAGES, v[200]), encoding='utf-8').read()
    t300 = io.open(os.path.join(PAGES, v[300]), encoding='utf-8').read()
    n200, n300 = numbers(t200), numbers(t300)
    if n200 == n300:
        agree += 1
    else:
        diff.append((stem, p, len(n200), len(n300),
                     len(n200 - n300), len(n300 - n200)))
print('чисел совпало полностью: %d из %d' % (agree, len(both)))
if diff:
    print('расхождения (документ, стр., чисел 200dpi, чисел 300dpi, только в 200, только в 300):')
    for d in diff[:12]:
        print('  %-34s стр.%-3d %4d %4d %4d %4d' % (d[0][:34], d[1], d[2], d[3], d[4], d[5]))
print()

# --- гипотеза 2: содержат ли прочитанные страницы провалившиеся коды
print('=== гипотеза 2: сколько прочитанных страниц содержат провалившиеся коды ===')
cases = []
for rf in sorted(f for f in os.listdir(EX) if f.endswith('.json') and not f.startswith('_')):
    stem = os.path.splitext(rf)[0]
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    warns = doc.get('warnings') or []
    for form in ('balance', 'income_statement', 'cash_flow'):
        live = [w for w in warns if w.startswith(form + ':') and re.search(
            r'fixed by escalation|did not fully reconcile|эскалация отклонена', w)]
        if not live:
            continue
        d = doc.get(form) or {}
        tp = [p for p in (d.get('transcript_pages') or []) if isinstance(p, int)]
        pages = tp[:8]
        bad = set()
        for c in (doc.get('checks') or []):
            if c['form'] == form and not c.get('ok'):
                bad |= set(re.findall(r'(?<![\d-])\d{4}(?![\d-])', c['rule']))
        hit = 0
        for p in pages:
            names = by_key.get((stem, p), {})
            txt = ''
            for dpi in (300, 200):
                if dpi in names:
                    txt = io.open(os.path.join(PAGES, names[dpi]), encoding='utf-8').read()
                    break
            if not txt:
                continue
            if any(re.search(r'(?<!\d)%s(?!\d)' % c, txt) for c in bad):
                hit += 1
        cases.append((stem, form, len(pages), hit, len(bad), sorted(bad)))
print('%-32s %-17s %5s %6s %5s' % ('документ', 'форма', 'стр.', 'с кодами', 'кодов'))
print('-' * 72)
tp_tot = h_tot = 0
for stem, form, np_, hit, nb, bad in cases:
    tp_tot += np_
    h_tot += hit
    print('%-32s %-17s %5d %6d %5d  %s' % (stem[:32], form, np_, hit, nb, ','.join(bad)))
print('-' * 72)
print('всего прочитано страниц: %d, из них содержат провалившиеся коды: %d (%.0f%%)'
      % (tp_tot, h_tot, 100.0 * h_tot / max(tp_tot, 1)))
print()

# --- гипотеза 3: размер входа структурирования
print('=== гипотеза 3: вход структурирования эскалации ===')
lens = []
for (stem, p), v in by_key.items():
    if 300 in v:
        lens.append(len(io.open(os.path.join(PAGES, v[300]), encoding='utf-8').read()))
if lens:
    lens.sort()
    print('транскриптов 300 dpi: %d, знаков: медиана %d, максимум %d'
          % (len(lens), lens[len(lens) // 2], lens[-1]))
    print('вход структурирования ≈ сумма по страницам формы')
json.dump([{'stem': c[0], 'form': c[1], 'pages': c[2], 'with_codes': c[3],
            'n_codes': c[4], 'codes': c[5]} for c in cases],
          io.open(r'D:\models\_esc_hypo.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
