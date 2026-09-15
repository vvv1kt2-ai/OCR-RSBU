# -*- coding: utf-8 -*-
r"""Опирается ли исправленное значение на текст, который эскалация получила?

Проверяю по кэшу: для каждого случая эскалации собираю ровно тот транскрипт, который
отправлялся модели (страницы формы по 300 dpi), и ищу в нём каждое исправленное
значение. Это решает, можно ли вводить ЖЁСТКИЙ гейт «применять только подтверждённое
текстом» — или он отбросил бы и полезные исправления.

Вызовов LLM нет: транскрипты берутся из кэша по page_cache_path.
"""
import io, os, re, json, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
SRC = r'D:\data-scraping\downloads'


def norm(t):
    """пробелы внутри чисел убираем: '92 891 924' -> '92891924'"""
    return re.sub(r'(?<=\d)[\s\u00a0](?=\d)', '', t or '')


def find_pdf(stem):
    for root, _, files in os.walk(SRC):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


rows = []
for rf in sorted(f for f in os.listdir(EX) if f.endswith('.json') and not f.startswith('_')):
    stem = os.path.splitext(rf)[0]
    doc_json = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    warns = doc_json.get('warnings') or []
    for form in ('balance', 'income_statement', 'cash_flow'):
        live = [w for w in warns if w.startswith(form + ':') and re.search(
            r'fixed by escalation|did not fully reconcile|эскалация отклонена', w)]
        if not live:
            continue
        d = doc_json.get(form) or {}
        corrected = [it for it in (d.get('items') or []) if it.get('corrected_by')]
        if not corrected:
            continue
        pages = [p for p in (d.get('transcript_pages') or []) if isinstance(p, int)][:8]
        path = find_pdf(stem)
        if not path:
            rows.append((stem, form, 'нет PDF', None))
            continue
        doc = P.pymupdf.open(path)
        sent = []
        missing = []
        for p in pages:
            try:
                cp = P.page_cache_path(doc, os.path.basename(path), p, 300, P.M_ESC)
            except Exception as e:
                missing.append('%d:%s' % (p, e))
                continue
            if os.path.exists(cp):
                sent.append(norm(io.open(cp, encoding='utf-8').read()))
            else:
                missing.append(str(p))
        doc.close()
        text = '\n'.join(sent)
        for it in corrected:
            old = it.get('values_ocr1') or []
            new = it.get('values') or []
            for i, (o, n) in enumerate(zip(old, new)):
                if o == n or n is None:
                    continue
                dn = re.sub(r'\D', '', str(n))
                supported = bool(dn) and dn in text
                rows.append((stem, form, 'код %s кол.%d: %s -> %s'
                             % (it.get('code'), i, o, n),
                             {'supported': supported, 'missing': missing,
                              'pages': pages, 'digits': dn}))

print('=== исправления эскалации и опора на отправленный текст ===')
for stem, form, what, info in rows:
    if info is None:
        print('  %-30s %-17s %s' % (stem[:30], form, what))
        continue
    print('  %-30s %-17s %s' % (stem[:30], form, what))
    print('      подтверждено текстом: %s   (страницы %s%s)'
          % ('ДА' if info['supported'] else 'НЕТ', info['pages'],
             ', нет кэша: %s' % info['missing'] if info['missing'] else ''))
print()
sup = [r for r in rows if r[3] and r[3]['supported']]
uns = [r for r in rows if r[3] and not r[3]['supported']]
print('исправлений всего: %d' % len(rows))
print('  подтверждены отправленным текстом: %d' % len(sup))
print('  НЕ подтверждены:                   %d' % len(uns))
print()
if uns:
    print('НЕ подтверждённые — жёсткий гейт их отклонил бы:')
    for stem, form, what, info in uns:
        print('  %-30s %-17s %s' % (stem[:30], form, what))
else:
    print('все исправления опираются на отправленный текст —')
    print('жёсткий гейт «применять только подтверждённое» не отбросил бы полезного.')
