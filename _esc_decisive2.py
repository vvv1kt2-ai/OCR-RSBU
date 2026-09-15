# -*- coding: utf-8 -*-
r"""Тест А (исправленный): видно ли правильное значение на 200 dpi.

Прошлая версия искала число слитно ('92891924'), а в транскриптах разряды разделены
пробелами ('92 891 924'), поэтому не находила НИЧЕГО даже на 300 dpi — это и выдало
ошибку. Нормализую текст: убираю пробелы между цифрами.
"""
import io, os, re, json

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
CACHE = re.compile(r'^(?P<stem>.+)_p(?P<p>\d+)_(?P<dpi>\d+)_(?P<rest>.+)\.md$')


def load(dpi):
    out = {}
    for f in os.listdir(PAGES):
        m = CACHE.match(f)
        if m and int(m.group('dpi')) == dpi:
            out.setdefault(m.group('stem'), {})[int(m.group('p'))] = f
    return out


c200, c300 = load(200), load(300)


def norm(text):
    """'92 891 924' -> '92891924' (только внутри чисел)"""
    return re.sub(r'(?<=\d)[\s\u00a0](?=\d)', '', text or '')


def text_of(cache, stem, p):
    f = (cache.get(stem) or {}).get(p)
    if not f:
        return None
    return norm(io.open(os.path.join(PAGES, f), encoding='utf-8').read())


print('=== ТЕСТ А: правильное значение на 200 dpi против 300 dpi ===')
print()
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
            code = str(it.get('code'))
            old = it.get('values_ocr1') or []
            new = it.get('values') or []
            for i, (o, n) in enumerate(zip(old, new)):
                if o == n or n is None:
                    continue
                dn = re.sub(r'\D', '', str(n))
                if not dn:
                    continue
                w200 = [p for p in tp if (text_of(c200, stem, p) or '').find(dn) >= 0]
                w300 = [p for p in tp if (text_of(c300, stem, p) or '').find(dn) >= 0]
                print('%s  %s  код %s  кол.%d' % (stem, form, code, i))
                print('   было %s -> стало %s' % (o, n))
                print('   правильное значение видно: 200 dpi %s | 300 dpi %s'
                      % (w200 if w200 else 'НЕТ', w300 if w300 else 'НЕТ'))
print()
print('=== ТЕСТ Б: разделение экономии на «засорение» и «выбор страниц» ===')
print()
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
        hit = []
        for p in tp:
            t = text_of(c200, stem, p) or ''
            if any(re.search(r'(?<!\d)%s(?!\d)' % c, t) for c in bad):
                hit.append(p)
        rows.append((stem, form, len(tp), hit))

print('%-32s %-17s %5s %5s  %s' % ('документ', 'форма', 'стр.', 'нужных', 'страницы с кодами'))
print('-' * 84)
tot = need = 0
for stem, form, np_, hit in rows:
    tot += np_
    need += len(hit)
    print('%-32s %-17s %5d %5d  %s' % (stem[:32], form, np_, len(hit), hit))
print('-' * 84)
print('страниц прочитано: %d, содержат провалившиеся коды: %d' % (tot, need))
print()
print('ВАЖНО: большие случаи (8 стр.) — это засорение пояснениями (правка 2),')
print('а не избыточность выбора страниц. Разделяю:')
big = [r for r in rows if r[2] > 4]
small = [r for r in rows if r[2] <= 4]
print('  случаев с >4 страницами: %d, страниц %d, из них нужных %d'
      % (len(big), sum(r[2] for r in big), sum(len(r[3]) for r in big)))
print('     -> экономия здесь = правка 2 (пояснения), не выбор страниц')
print('  случаев с <=4 страницами: %d, страниц %d, из них нужных %d'
      % (len(small), sum(r[2] for r in small), sum(len(r[3]) for r in small)))
print('     -> экономия здесь = собственно выбор страниц')
