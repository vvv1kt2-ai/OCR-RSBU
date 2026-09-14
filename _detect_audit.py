# -*- coding: utf-8 -*-
r"""Аудит детекции: совпадает ли разметка страниц с тем, что на странице на самом деле.

Бесплатно и на уже оплаченных данных. Транскрипт страницы (200 dpi, основная модель)
в шапке содержит код формы по ОКУД, поэтому он и служит судьёй: детекция говорит
«страница 5 — это баланс», а транскрипт страницы 5 показывает, что там на самом деле.

Зачем это до сравнения поставщиков: у эскалации эталон оказался ненадёжным, и было бы
ошибкой повторить ту ошибку здесь — сначала проверяем, годится ли эталон детекции.
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
print('метка основной модели для Polza: len=%d sha1=%s'
      % (len(MAIN_TAG), __import__('hashlib').sha1(MAIN_TAG.encode()).hexdigest()[:8]))

TR = re.compile(r'^(.+)_p(\d+)_200_(.+?)_([0-9a-f]{10})\.md$')


def transcript(stem, page, tag=MAIN_TAG):
    for fn in os.listdir(PAGES):
        m = TR.match(fn)
        if m and m.group(1) == stem and int(m.group(2)) == page and m.group(3) == tag:
            return io.open(os.path.join(PAGES, fn), encoding='utf-8').read()
    return None


def classify(txt):
    """какая форма на странице, по её же транскрипту.

    Порядок проверок важен: страница пояснений в шапке содержит сразу оба названия —
    «Пояснения к бухгалтерскому балансу И отчету о финансовых результатах», — поэтому
    пояснения проверяются первыми. Иначе пояснения выглядят как отчёт о финрезультатах.
    """
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


res_files = sorted(f for f in os.listdir(EX)
                   if f.endswith('.json') and not f.startswith('_'))
agree = Counter()
mismatch = []
unknown = []
detected_but_no_transcript = []

for rf in res_files:
    stem = os.path.splitext(rf)[0]
    doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
    for form in ('balance', 'income_statement', 'cash_flow'):
        fd = doc.get(form) or {}
        for p in (fd.get('transcript_pages') or []):
            if not isinstance(p, int):
                continue
            txt = transcript(stem, p)
            if txt is None:
                detected_but_no_transcript.append((stem, form, p))
                continue
            got = classify(txt)
            if got == form:
                agree[form] += 1
            elif got == 'other':
                unknown.append((stem, form, p))
            else:
                mismatch.append((stem, form, p, got))

print()
print('=== совпадает ли детекция с тем, что в транскрипте страницы ===')
print('согласны: %s' % dict(agree))
print('транскрипта нет: %d' % len(detected_but_no_transcript))
print('транскрипт не опознан: %d' % len(unknown))
print('РАСХОЖДЕНИЙ: %d' % len(mismatch))
kinds = Counter('%s -> %s' % (f, g) for _, f, _, g in mismatch)
print('виды расхождений: %s' % dict(kinds))
print()
for kind in sorted(kinds, key=lambda k: -kinds[k]):
    print('--- %s (%d) ---' % (kind, kinds[kind]))
    for stem, form, p, got in mismatch:
        if '%s -> %s' % (form, got) == kind:
            print('  %-32s стр.%d' % (stem[:32], p))
print()
total = sum(agree.values()) + len(mismatch) + len(unknown)
if total:
    print('точность детекции Polza по транскриптам: %d из %d = %.1f%%'
          % (sum(agree.values()), total, 100 * sum(agree.values()) / total))

# --- полнота: страницы с кодом формы, которых детекция не заметила ----------
print()
print('=== полнота: не пропустила ли детекция страницу с кодом формы ===')
import fitz

missed = []
checked_docs = 0
for rf in res_files:
    stem = os.path.splitext(rf)[0]
    pdf = os.path.join(DL, stem + '.pdf')
    if not os.path.exists(pdf):
        continue
    try:
        d = fitz.open(pdf)
    except Exception:
        continue
    try:
        # какие страницы вообще имеют текстовый слой с кодом формы
        layer_forms = {}
        for i in range(d.page_count):
            t = d[i].get_text()
            if len(t) < 100:
                continue
            for code, form in (('0710001', 'balance'), ('0710002', 'income_statement'),
                               ('0710004', 'cash_flow'), ('0710005', 'cash_flow')):
                if code in t:
                    layer_forms.setdefault(form, set()).add(i + 1)
                    break
        if not layer_forms:
            continue
        checked_docs += 1
        doc = json.load(io.open(os.path.join(EX, rf), encoding='utf-8'))
        for form, pages in layer_forms.items():
            det = set(p for p in ((doc.get(form) or {}).get('transcript_pages') or [])
                      if isinstance(p, int))
            for p in sorted(pages - det):
                missed.append((stem, form, p))
    finally:
        d.close()

print('документов с текстовым слоем, где виден код формы: %d' % checked_docs)
print('страниц с кодом формы, которых детекция НЕ взяла: %d' % len(missed))
for stem, form, p in missed[:25]:
    print('  %-32s стр.%-3d форма=%s' % (stem[:32], p, form))
