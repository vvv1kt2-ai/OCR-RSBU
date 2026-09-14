# -*- coding: utf-8 -*-
r"""Проверка следствия: читает ли эскалация пояснения вместо баланса.

Эскалация берёт первые 8 страниц списка формы (`pipeline.py:665`). Если детекция
засорила список пояснениями, дорогая модель прочитает пояснения. Проверяется на
КЛВЗ Кристалл_6мес_2025 — там эскалация сработала, а пояснения в списке есть.
"""
import io, os, re, json, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
MAIN_TAG = P.model_tag(P.M_MAIN)
TR = re.compile(r'^(.+)_p(\d+)_200_(.+?)_([0-9a-f]{10})\.md$')


def classify(txt):
    t = (txt or '').replace('\u00a0', ' ')
    if 'Пояснения к бухгалтерскому балансу' in t or 'Пояснения к балансу' in t:
        return 'ПОЯСНЕНИЯ'
    if '0710001' in t or 'Бухгалтерский баланс' in t:
        return 'баланс'
    if '0710002' in t or 'финансовых результатах' in t:
        return 'отчёт о финрез.'
    if '0710004' in t or '0710005' in t or 'движении денежных средств' in t:
        return 'движение денег'
    return 'не опознано'


def transcript(stem, page):
    for fn in os.listdir(PAGES):
        m = TR.match(fn)
        if m and m.group(1) == stem and int(m.group(2)) == page and m.group(3) == MAIN_TAG:
            return io.open(os.path.join(PAGES, fn), encoding='utf-8').read()
    return None


STEM = 'КЛВЗ Кристалл_6мес_2025'
doc = json.load(io.open(os.path.join(EX, STEM + '.json'), encoding='utf-8'))
bal = doc.get('balance') or {}
pages = [p for p in (bal.get('transcript_pages') or []) if isinstance(p, int)]
first8 = pages[:8]

print('документ: %s' % STEM)
print('страницы формы balance по детекции: %s' % pages)
print('эскалация берёт первые 8: %s' % first8)
print()
print('%-8s %-18s %s' % ('стр.', 'что на странице', 'попала в эскалацию'))
print('-' * 52)
notes_in_esc = 0
for p in pages:
    t = transcript(STEM, p)
    kind = classify(t) if t else 'нет транскрипта'
    inesc = p in first8
    if inesc and kind == 'ПОЯСНЕНИЯ':
        notes_in_esc += 1
    print('%-8d %-18s %s' % (p, kind, 'ДА' if inesc else '—'))
print('-' * 52)
print('страниц пояснений внутри эскалации: %d из %d' % (notes_in_esc, len(first8)))
print()
print('статус документа: %s' % doc.get('status'))
print('предупреждения:')
for w in (doc.get('warnings') or []):
    print('  - %s' % w[:120])
print()
print('проверки баланса:')
for c in (doc.get('checks') or []):
    if c.get('form') == 'balance':
        print('  %-6s %s' % ('прошла' if c.get('ok') else 'НЕТ', c.get('rule')))

# что реально ушло на эскалацию — по артефакту
for f in os.listdir(PAGES):
    if f.startswith('_llm_%s.pdf_esc_balance' % STEM):
        art = json.load(io.open(os.path.join(PAGES, f), encoding='utf-8'))
        items = art.get('items') or []
        print()
        print('артефакт эскалации: %s' % f)
        print('  строк получено: %d' % len(items))
        print('  колонок: %s' % (art.get('columns') or [])[:6])
        # какие коды строк пришли — если поясничные, значит читала пояснения
        codes = []
        for it in items:
            for k in ('code', 'row', 'line'):
                if it.get(k):
                    codes.append(str(it[k]))
                    break
        print('  первые коды строк: %s' % codes[:14])
        break
