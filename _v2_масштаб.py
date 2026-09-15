# -*- coding: utf-8 -*-
r"""Масштаб: сколько страниц без кодов строк попадает в формы при старой и новой подсказке.

Идея замера: детекция дешёвая (0.0016 ₽ за страницу), а транскрипты для многих страниц уже
есть на диске. Поэтому можно прогнать детекцию новой подсказкой и проверить её метки по
УЖЕ ОПЛАЧЕННЫМ транскриптам — бесплатно.

Что сравнивается на одних и тех же документах:
  было — метки из артефакта (подсказка V1), страницы из `transcript_pages`;
  стало — метки V2 (постраничная детекция), те же проверки по тем же транскриптам.

Метрика: сколько страниц, помеченных формой, не содержат ни одного кода строк 1100-1700.
Это и есть пояснения, прочитанные как форма.

Ограничение, которое надо помнить при чтении: страницу, которую V2 помечает формой, но
которой нет в старых транскриптах, проверить бесплатно нельзя — её придётся читать. Такие
страницы считаются отдельно и в вывод не подмешиваются.
"""
import io, json, os, re, sys, collections

sys.path.insert(0, r'D:\models')
import pipeline as P

OUT = r'D:\models\extracted'
PAGES = P.PAGESDIR
CODE_RE = re.compile(r'\b(1[1-7]\d0|2[45]\d0|4[1-5]\d0)\b')

# документы, где V1 прочитала больше всего страниц без кодов строк
DOCS = [d for d in os.environ.get('V2_DOCS', '').split('|') if d]


def find_pdf(stem):
    for root, _, files in os.walk(P.DOWNLOADS):
        for fn in files:
            if os.path.splitext(fn)[0] == stem:
                return os.path.join(root, fn)
    return None


def transcript_of(stem, p):
    """текст страницы из любого уже лежащего транскрипта, или None"""
    hits = [f for f in os.listdir(PAGES)
            if f.startswith(f'{stem}_p{p}_') and f.endswith('.md')]
    if not hits:
        return None
    return io.open(os.path.join(PAGES, hits[0]), encoding='utf-8').read()


def has_codes(txt):
    return bool(CODE_RE.search(txt)) if txt else None


if not DOCS:
    print('не заданы документы (V2_DOCS)'); sys.exit(0)

cost0, calls0 = P.USAGE['cost_rub'], P.USAGE['calls']
rows = []
for stem in DOCS:
    path = find_pdf(stem)
    art = os.path.join(OUT, stem + '.json')
    if not path or not os.path.exists(art):
        print('%s: нет PDF или артефакта' % stem); continue
    r = json.load(io.open(art, encoding='utf-8'))
    before = set()
    for key in ('balance', 'income_statement', 'cash_flow'):
        d = r.get(key)
        if d:
            before |= set(d.get('transcript_pages') or [])

    doc = P.pymupdf.open(path)
    npages = len(doc)
    warnings = []
    try:
        pm = P.detect_pages_per_page(doc, list(range(1, npages + 1)), npages, warnings,
                                     stem + '.pdf')
    except Exception as e:
        print('%s: детекция упала: %s' % (stem, e)); doc.close(); continue
    after = {p['page'] for p in pm if p.get('form') in P.FORM_LABELS}
    notes = {p['page'] for p in pm if p.get('form') == 'notes'}
    audit = {p['page'] for p in pm if p.get('form') == 'audit'}
    doc.close()

    def stat(pages):
        with_txt = [p for p in pages if transcript_of(stem, p) is not None]
        codeless = [p for p in with_txt if not has_codes(transcript_of(stem, p))]
        return len(pages), len(with_txt), len(codeless), sorted(codeless)

    b_all, b_txt, b_bad, b_list = stat(before)
    a_all, a_txt, a_bad, a_list = stat(after)
    rows.append((stem, npages, (b_all, b_txt, b_bad), (a_all, a_txt, a_bad),
                 sorted(notes), sorted(audit), b_list, a_list))
    print('%-32s страниц %3d: было форм %2d (проверено %2d, без кодов %2d), '
          'стало %2d (проверено %2d, без кодов %2d), notes %d, audit %d'
          % (stem[:32], npages, b_all, b_txt, b_bad, a_all, a_txt, a_bad,
             len(notes), len(audit)))

print()
print('=' * 78)
print('%-32s %6s %22s %22s' % ('документ', 'стр.', 'БЫЛО (форм/без кодов)', 'СТАЛО'))
tb = ta = tbb = tab = 0
for stem, npages, b, a, notes, audit, bl, al in rows:
    tb += b[0]; ta += a[0]; tbb += b[2]; tab += a[2]
    print('%-32s %6d %22s %22s'
          % (stem[:32], npages, '%d / %d' % (b[0], b[2]), '%d / %d' % (a[0], a[2])))
print('%-32s %6s %22s %22s' % ('ИТОГО', '', '%d / %d' % (tb, tbb), '%d / %d' % (ta, tab)))
print()
print('цена замера: %.4f ₽, вызовов %d' % (P.USAGE['cost_rub'] - cost0,
                                            P.USAGE['calls'] - calls0))
print()
print('Было без кодов строк: %d страниц. Стало: %d.' % (tbb, tab))
if rows:
    print()
    print('что именно перестало попадать в формы (страницы без кодов, было/стало):')
    for stem, npages, b, a, notes, audit, bl, al in rows:
        if bl:
            print('   %-30s было %s' % (stem[:30], bl[:12]))
            print('   %-30s стало %s' % ('', al[:12] or 'пусто'))
