# -*- coding: utf-8 -*-
r"""Масштаб дефекта: страницы пояснений, прочитанные как страницы формы.

Три предыдущих признака были неверны, и это стоит зафиксировать, потому что каждый раз
ошибка была в признаке, а не в данных:

1. Слово «пояснения» — колонка официальной формы баланса, есть почти везде.
2. Слова «ФСБУ»/«расшифровка» — есть строки самой формы («Резервы, образованные в
   соответствии с законодательством»).
3. Отсутствие шапки «Форма 07100XX» — модель не всегда переносит шапку в транскрипт.

Надёжный признак — **содержание**: страница баланса несёт коды строк 1100-1700 (шаг 10),
потому что это и есть её смысл. Страница пояснений («4.1. Наличие и движение основных
средств») кодов строк баланса не несёт — там свои таблицы с другими заголовками.

Проверено вручную: «Артген (ИСКЧ)_6мес_2025» стр. 30 — это «4. Основные средства /
4.1. Наличие и движение основных средств», и она была помечена `balance` и прочитана
как часть баланса. Значит дефект реален, вопрос только в масштабе.
"""
import io, json, os, re, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

OUT = r'D:\models\extracted'
PAGES = P.PAGESDIR

BAL_CODES = [str(1100 + 10 * i) for i in range(60)]          # 1100..1690
BAL_CODES += ['1700', '2400', '2410', '2500', '4500']
CODE_RE = re.compile(r'\b(1[1-7]\d0|2[45]\d0|4[1-5]\d0)\b')
NOTES_SECTION = re.compile(r'^\s*#{1,4}\s*\d+(\.\d+)*\.?\s*\S', re.M)

arts = [f for f in os.listdir(OUT) if f.endswith('.json') and not f.startswith('_')]
all_files = os.listdir(PAGES)
print('артефактов: %d' % len(arts))
print()

rows = []
for fn in sorted(arts):
    try:
        r = json.load(io.open(os.path.join(OUT, fn), encoding='utf-8'))
    except Exception:
        continue
    stem = os.path.splitext(fn)[0]
    for key in ('balance', 'income_statement', 'cash_flow'):
        d = r.get(key)
        if not d:
            continue
        for p in (d.get('transcript_pages') or []):
            hits = [f for f in all_files if f.startswith(f'{stem}_p{p}_') and f.endswith('.md')]
            if not hits:
                continue
            txt = io.open(os.path.join(PAGES, hits[0]), encoding='utf-8').read()
            codes = set(CODE_RE.findall(txt))
            rows.append({
                'stem': stem, 'form': key, 'page': p, 'n': len(txt),
                'codes': len(codes),
                'section': bool(NOTES_SECTION.search(txt[:1200])),
                'has_form_head': bool(re.search(r'Форма\s*0710\d{3}', txt)),
            })

print('страниц формы проверено: %d' % len(rows))
print()

# Страница формы без единого кода строк: либо шапка/подпись формы, либо чужой документ.
no_codes = [r for r in rows if r['codes'] == 0]
print('БЕЗ ЕДИНОГО КОДА СТРОК: %d страниц' % len(no_codes))
print('   из них с признаками разделов пояснений ("## N. Название"): %d'
      % sum(1 for r in no_codes if r['section']))
print('   из них с шапкой формы «Форма 07100XX»: %d'
      % sum(1 for r in no_codes if r['has_form_head']))
print()
print('%-38s %-17s %5s %7s %7s' % ('документ', 'форма', 'стр.', 'знаков', 'раздел'))
for r in sorted(no_codes, key=lambda x: -x['n'])[:30]:
    print('%-38s %-17s %5d %7d %7s'
          % (r['stem'][:38], r['form'], r['page'], r['n'], 'да' if r['section'] else '—'))
print()
if len(no_codes) > 30:
    print('... и ещё %d' % (len(no_codes) - 30))
print()

docs = sorted({r['stem'] for r in no_codes})
print('документов затронуто: %d из %d' % (len(docs), len(arts)))
pages_per_doc = {}
for r in no_codes:
    pages_per_doc[r['stem']] = pages_per_doc.get(r['stem'], 0) + 1
top = sorted(pages_per_doc.items(), key=lambda kv: -kv[1])[:12]
print('больше всего лишних страниц:')
for stem, n in top:
    print('   %-44s %d' % (stem[:44], n))
