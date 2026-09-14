# -*- coding: utf-8 -*-
"""Classify every page of every corpus PDF: usable text layer / garbled text / no text.
Also locate pages carrying RSBU form markers, to size the truly OCR-requiring set."""
import sys, os, re, json, glob, collections
sys.path.insert(0, 'D:/models/pylibs')
import pymupdf

DL = r'D:\data-scraping\downloads'
FORM_RE = re.compile(r'0710001|0710002|0710005|Бухгалтерск\w*\s+баланс|Отч[её]т о финансовых|Отч[её]т о движении денежных', re.I)
LETTER = re.compile(r'[^\W\d_]', re.UNICODE)
CYR = re.compile(r'[а-яёА-ЯЁ]')

tot = collections.Counter()
files = {}
rows = []
for p in sorted(glob.glob(os.path.join(DL, '*.pdf'))):
    name = os.path.basename(p)
    try:
        d = pymupdf.open(p)
    except Exception as e:
        rows.append({'file': name, 'error': str(e)[:100]}); continue
    cls = collections.Counter(); form_by_cls = collections.Counter()
    for pg in d:
        t = pg.get_text('text') or ''
        s = t.strip()
        n = len(s)
        letters = LETTER.findall(s); cyr = CYR.findall(s)
        cyr_ratio = (len(cyr) / len(letters)) if letters else 0.0
        repl = s.count('\ufffd')
        has_form = bool(FORM_RE.search(s))
        if n < 50:
            c = 'none'
        elif n >= 300 and cyr_ratio >= 0.6 and repl * 20 < n:
            c = 'good'
        else:
            c = 'garbled'
        cls[c] += 1
        if has_form:
            form_by_cls[c] += 1
        tot[c] += 1
        if has_form:
            tot['form_' + c] += 1
    d.close()
    tot['files'] += 1
    tot['pages'] += sum(cls.values())
    if cls['good'] and not cls['none'] and not cls['garbled']:
        tot['files_all_good'] += 1
    if cls['none'] == sum(cls.values()):
        tot['files_all_none'] += 1
    if cls['good'] == 0:
        tot['files_no_good_text'] += 1
    if form_by_cls['good'] and form_by_cls['none'] == 0 and form_by_cls['garbled'] == 0:
        tot['files_form_in_good_text_only'] += 1
    files[name] = {'pages': sum(cls.values()), 'cls': dict(cls), 'form_by_cls': dict(form_by_cls)}
    rows.append({'file': name, 'pages': sum(cls.values()), 'good': cls['good'], 'garbled': cls['garbled'],
                 'none': cls['none'], 'form_good': form_by_cls['good'], 'form_garbled': form_by_cls['garbled'],
                 'form_none': form_by_cls['none']})

print('TOTALS', json.dumps({k: v for k, v in sorted(tot.items())}, ensure_ascii=False, indent=1))
print('\nfiles where ALL form-marker pages are in good text:',
      tot['files_form_in_good_text_only'], '/', tot['files'])
print('\n--- 20 files with most no-text pages ---')
for r in sorted([r for r in rows if 'pages' in r], key=lambda x: -x['none'])[:20]:
    print(f"  {r['file'][:44]:44} pages={r['pages']:3} good={r['good']:3} garbled={r['garbled']:3} none={r['none']:3} "
          f"| form: good={r['form_good']} garbled={r['form_garbled']} none={r['form_none']}")
print('\n--- 20 files with most garbled text pages ---')
for r in sorted([r for r in rows if 'pages' in r], key=lambda x: -x['garbled'])[:20]:
    print(f"  {r['file'][:44]:44} pages={r['pages']:3} good={r['good']:3} garbled={r['garbled']:3} none={r['none']:3} "
          f"| form: good={r['form_good']} garbled={r['form_garbled']} none={r['form_none']}")
json.dump({'totals': dict(tot), 'files': files}, open(r'D:\models\_textlayer.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
