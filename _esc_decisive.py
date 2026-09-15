# -*- coding: utf-8 -*-
r"""Решающий тест по эскалации: нужен ли 300 dpi и сколько страниц надо читать.

Тест А: был ли ПРАВИЛЬНЫЙ ответ уже виден на 200 dpi? Если да, то 300 dpi не помог,
а проблема была в структурировании — и тогда дорогую перечитку можно не делать.
Тест Б: можно ли найти страницы с провалившимися кодами по УЖЕ ОПЛАЧЕННЫМ
транскриптам 200 dpi (тогда эскалация читает 2 страницы вместо 8).
"""
import io, os, re, json

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
CACHE = re.compile(r'^(?P<stem>.+)_p(?P<p>\d+)_(?P<dpi>\d+)_(?P<rest>.+)\.md$')
ESC_PAGE = 0.708


def load(dpi):
    out = {}
    for f in os.listdir(PAGES):
        m = CACHE.match(f)
        if m and int(m.group('dpi')) == dpi:
            out.setdefault(m.group('stem'), {})[int(m.group('p'))] = f
    return out


c200, c300 = load(200), load(300)


def text_of(cache, stem, p):
    f = (cache.get(stem) or {}).get(p)
    if not f:
        return None
    return io.open(os.path.join(PAGES, f), encoding='utf-8').read()


def digits(s):
    return re.sub(r'[^\d]', '', s or '')


print('=== ТЕСТ А: был ли правильный ответ виден на 200 dpi ===')
print('(для строк, которые эскалация ИСПРАВИЛА: ищем новое значение в тексте 200 dpi)')
print()
found_any = False
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
        tp = [p for p in (d.get('transcript_pages') or []) if isinstance(p, int)][:8]
        for it in (d.get('items') or []):
            if not it.get('corrected_by'):
                continue
            found_any = True
            code = str(it.get('code'))
            old = it.get('values_ocr1') or []
            new = it.get('values') or []
            print('%s  %s  код %s' % (stem, form, code))
            for i, (o, n) in enumerate(zip(old, new)):
                if o == n:
                    continue
                dn = digits(str(n)) if n is not None else ''
                where200 = [p for p in tp if (text_of(c200, stem, p) or '').find(dn) >= 0
                            and dn]
                where300 = [p for p in tp if (text_of(c300, stem, p) or '').find(dn) >= 0
                            and dn]
                print('   кол.%d: было %s -> стало %s' % (i, o, n))
                print('       значение видно на 200 dpi: стр. %s'
                      % (where200 if where200 else 'НЕТ'))
                print('       значение видно на 300 dpi: стр. %s'
                      % (where300 if where300 else 'НЕТ'))
if not found_any:
    print('исправленных строк не найдено')
print()

print('=== ТЕСТ Б: поиск страниц с провалившимися кодами по кэшу 200 dpi ===')
rows = []
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
        tp = [p for p in (d.get('transcript_pages') or []) if isinstance(p, int)][:8]
        bad = set()
        for c in (doc.get('checks') or []):
            if c['form'] == form and not c.get('ok'):
                bad |= set(re.findall(r'(?<![\d-])\d{4}(?![\d-])', c['rule']))
        have200 = [p for p in tp if text_of(c200, stem, p) is not None]
        hit200 = [p for p in have200
                  if any(re.search(r'(?<!\d)%s(?!\d)' % c, text_of(c200, stem, p) or '')
                         for c in bad)]
        rows.append((stem, form, len(tp), len(have200), len(hit200), sorted(bad)))
print('%-32s %-17s %5s %7s %7s' % ('документ', 'форма', 'стр.', 'есть 200', 'с кодами'))
print('-' * 76)
tot = have = hit = 0
for stem, form, np_, h200, h, bad in rows:
    tot += np_
    have += h200
    hit += h
    print('%-32s %-17s %5d %7d %7d' % (stem[:32], form, np_, h200, h))
print('-' * 76)
print('прочитано эскалацией страниц: %d' % tot)
print('из них уже оплачены на 200 dpi: %d' % have)
print('из них содержат провалившиеся коды: %d' % hit)
print()
if have:
    print('если читать только страницы с кодами:')
    print('  страниц вместо %d -> %d, экономия %d стр. = %.2f ₽ на этих случаях'
          % (tot, hit, tot - hit, (tot - hit) * ESC_PAGE))
    print('  при переносе на корпус (масштаб 5.88): %.2f ₽'
          % ((tot - hit) * ESC_PAGE * 5.88))
json.dump([{'stem': r[0], 'form': r[1], 'pages': r[2], 'have200': r[3],
            'with_codes': r[4], 'codes': r[5]} for r in rows],
          io.open(r'D:\models\_esc_decisive.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
