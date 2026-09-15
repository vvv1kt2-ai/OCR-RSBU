# -*- coding: utf-8 -*-
r"""Точный масштаб: у кого find_form_pages возвращает непустой словарь БЕЗ страниц.

Дефект срабатывает не на всех «пустых» документах, а только там, где условие `if not fp`
оказывается ложным, то есть словарь непустой, хотя страниц в нём нет: `{'income_statement': []}`.
Если find_form_pages вернул `{}` — запасной ход в скановую ветку работает.

Поэтому считаем не «нет форм в слое», а ровно форму ответа:
  {}                      -> запасной ход сработает, документ спасён;
  {'X': []}               -> ОШИБКА: запасной ход пропущен, документ выйдет пустым;
  {'X': [стр...]}         -> норма, форма найдена в слое.

Замер бесплатный, вызовов модели нет.
"""
import os, sys

sys.path.insert(0, r'D:\models')
import pipeline as P

bug, safe, ok, scan_only = [], [], [], []
for root, _, files in os.walk(P.DOWNLOADS):
    for fn in sorted(files):
        if not fn.lower().endswith('.pdf'):
            continue
        try:
            doc = P.pymupdf.open(os.path.join(root, fn))
        except Exception:
            continue
        n = len(doc)
        chars = sum(len(p.get_text().strip()) for p in doc)
        garbled = [p for p in range(1, n + 1) if P._garbled_page(doc[p - 1])]
        has_text = chars > 200 and len(garbled) < max(2, n // 4)
        if not has_text:
            scan_only.append(fn)
            doc.close()
            continue
        want = P.wanted_forms(fn)
        fp = P.find_form_pages(doc)
        fp = {k: list(v) for k, v in fp.items() if k in want}
        img = [p for p in range(1, n + 1)
               if doc[p - 1].get_images(full=True) and len(doc[p - 1].get_text().strip()) < 600]
        doc.close()
        if any(fp.values()):
            ok.append(fn)
        elif fp and img:
            bug.append((fn, {k: len(v) for k, v in fp.items()}, len(img), n))
        elif not fp and img:
            safe.append((fn, len(img), n))
        else:
            ok.append(fn)

print('документов: текстовых %d, скановых %d' % (len(ok) + len(bug) + len(safe), len(scan_only)))
print()
print('=== ДЕФЕКТ: непустой словарь без страниц -> запасной ход пропущен, документ пустой')
print('    таких: %d' % len(bug))
for fn, d, nimg, n in bug:
    print('    %-44s %s, сканов %d из %d стр.' % (fn[:44], d, nimg, n))
print()
print('=== безопасно: словарь пустой -> запасной ход в скановую ветку сработает')
print('    таких: %d' % len(safe))
for fn, nimg, n in safe:
    print('    %-44s сканов %d из %d стр.' % (fn[:44], nimg, n))
print()
print('=== форма найдена в слое, дефекта нет: %d' % len(ok))
