# -*- coding: utf-8 -*-
r"""Не потеряла ли новая подсказка настоящие формы?

Замер масштаба показал, что страниц формы стало 115 -> 37, а страниц без кодов строк
83 -> 2. Хорошая новость (лишнее ушло) и тревожная одновременно: если вместе с пояснениями
уехали и настоящие формы, то экономия обернулась потерей данных.

Проверка бесплатная: метки детекции уже в кэше, транскрипты уже оплачены. Смотрим, есть ли
среди страниц, которые V2 называет формами, страницы с ЗАМЫКАЮЩИМ кодом формы:
баланс 1700, ОФР 2400/2410, ОДДС 4500. Без замыкающего кода форма неполна, и именно его
отсутствие запускает эскалацию (51% цены пилота).

Сравниваем три набора:
  кэш V1  — страницы из артефакта (что читалось до правки);
  V2 формы — что V2 называет формами;
  V2 notes/audit — что V2 уводит из форм.
"""
import io, json, os, re, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

OUT = r'D:\models\extracted'
PAGES = P.PAGESDIR
TERMINAL = {'balance': '1700', 'income_statement': ('2400', '2410'), 'cash_flow': '4500'}
DOCS = [d for d in os.environ.get('V2_DOCS', '').split('|') if d]


def find_pdf(stem):
    for root, _, files in os.walk(P.DOWNLOADS):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


def transcript_of(stem, p):
    hits = [f for f in os.listdir(PAGES) if f.startswith(f'{stem}_p{p}_') and f.endswith('.md')]
    return io.open(os.path.join(PAGES, hits[0]), encoding='utf-8').read() if hits else None


def codes_in(txt):
    return set(re.findall(r'\b\d{4}\b', txt or ''))


def terminal_hit(stem, form, pages):
    """на каких из этих страниц встречается замыкающий код своей формы"""
    want = TERMINAL.get(form)
    if not want:
        return []
    want = (want,) if isinstance(want, str) else want
    hits = []
    for p in pages:
        t = transcript_of(stem, p)
        if t and codes_in(t) & set(want):
            hits.append(p)
    return hits


cost0, calls0 = P.USAGE['cost_rub'], P.USAGE['calls']
print('%-32s %-6s %-26s %-26s %s' % ('документ', 'форма', 'кэш V1 (страницы)', 'V2 формы', 'замыкающий код'))
print('-' * 118)
lost_total = 0
for stem in DOCS:
    path, art = find_pdf(stem), os.path.join(OUT, stem + '.json')
    if not path or not os.path.exists(art):
        print('%s: нет PDF или артефакта' % stem); continue
    r = json.load(io.open(art, encoding='utf-8'))
    old = {}
    for key in ('balance', 'income_statement', 'cash_flow'):
        d = r.get(key)
        if d:
            old[key] = sorted(d.get('transcript_pages') or [])

    doc = P.pymupdf.open(path)
    npages = len(doc)
    pm = P.detect_pages_per_page(doc, list(range(1, npages + 1)), npages, [], stem + '.pdf')
    doc.close()
    new = {}
    for x in pm:
        if x.get('form') in P.FORM_LABELS:
            new.setdefault(x['form'], []).append(x['page'])
    new = {k: sorted(v) for k, v in new.items()}
    notes = sorted(x['page'] for x in pm if x.get('form') == 'notes')

    for key in ('balance', 'income_statement', 'cash_flow'):
        o, n = old.get(key, []), new.get(key, [])
        oh, nh = terminal_hit(stem, key, o), terminal_hit(stem, key, n)
        lost = [p for p in oh if p not in nh]
        lost_total += len(lost)
        mark = ''
        if oh and not nh:
            mark = '  <-- ПОТЕРЯ: форма была, стала пусто'
        elif lost:
            mark = '  <-- ПОТЕРЯ страниц %s' % lost
        print('%-32s %-6s %-26s %-26s %s%s'
              % (stem[:32], key, str(o)[:26], str(n)[:26],
                 'V1 %s -> V2 %s' % (oh or '—', nh or '—'), mark))
    print('%-32s %-6s notes %s' % ('', '', notes[:24]))
    print()

print('-' * 118)
print('страниц с замыкающим кодом, потерянных при переходе: %d' % lost_total)
print('цена проверки: %.4f ₽, вызовов %d' % (P.USAGE['cost_rub'] - cost0, P.USAGE['calls'] - calls0))
print()
print('Читать так: в колонке «замыкающий код» слева — где код был при V1, справа — где он при V2.')
print('Если справа пусто, а слева было — V2 потеряла настоящую форму, и правку надо откатывать.')
