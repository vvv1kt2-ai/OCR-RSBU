# -*- coding: utf-8 -*-
r"""Платный опыт: возвращает ли потерянную строку ПЕРЕРАЗБОР УЖЕ ОПЛАЧЕННОГО текста?

Зачем. Эскалация на провале арифметики делает две дорогие вещи: перечитывает страницы
изображением (дорогая модель, вывод в тысячи токенов) и структурирует результат. Но в 4 из
9 остаточных случаев недостающая строка ЛЕЖИТ в транскрипте, который уже оплачен. Если
переразбор имеющегося текста её возвращает, перечитывание картинок не нужно — и это
снимает примерно половину цены эскалации.

Дизайн: даём модели тот же текст, что уже есть на диске, плюс подсказку о конкретном
расхождении арифметики (какой итог, какая сумма, на сколько не сходится) и просим ТОЛЬКО
недостающие строки. Вывод короткий, вход — текст, а не картинка.

Стоимость опыта печатается в конце; ключ кэша не используется намеренно, чтобы опыт нельзя
было спутать с боевым прогоном.
"""
import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, r'D:\models')
import pipeline as P  # noqa: E402
import providers as PV  # noqa: E402

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')

# документ, форма, правило, которое валится, и его слагаемые
#
# ВАЖНО про изъян дизайна, найденный уже после первого прогона. В обоих первых случаях
# недостающее значение ЧИСЛЕННО РАВНО расхождению, а расхождение я кладу в подсказку. Значит
# ответ «нашёл строку 1520 = 15307/14866/5255» неотличим от «посчитал 15307 = 88579-73272 и
# выдал за строку». Правильный контроль — документ, где строки в тексте НЕТ: там честная
# модель обязана вернуть пустой список, а не подставить расхождение. Поэтому в наборе есть
# КОНТРОЛЬ (Корпсан_6мес_2026): у него не хватает 4000, и 4000 в транскриптах баланса нет —
# число встречается только на странице ОДДС (4310/4311), то есть совпадение исключено.
CASES = [
    ('ИПС_6мес_2025', 'balance', '1500', ('1510', '1520', '1530', '1540', '1550'),
     'Итого по разделу V', '1520', [15307, 14866, 5255], 'да'),
    ('Органик парк_6мес_2025', 'balance', '1100',
     ('1110', '1120', '1130', '1140', '1150', '1160', '1170', '1180', '1190'),
     'Итого по разделу I', '1110', [None, None, 28551], 'да'),
    ('Корпсан_6мес_2026', 'balance', '1500', ('1510', '1520', '1530', '1540', '1550'),
     'Итого по разделу V', '4000', None, 'КОНТРОЛЬ: строки в тексте нет'),
]
_only = os.environ.get('OPYT_ONLY', '').strip()
if _only:
    CASES = [c for c in CASES if _only in c[0]]

print(f'профиль: {P.ACTIVE_PROFILE}   main={P.model_tag(P.M_MAIN)} (len {len(P.M_MAIN)})')
print(f'вызовов до опыта: {P.USAGE["calls"]}, pt={P.USAGE.get("pt")}, ct={P.USAGE.get("ct")}')


def paid_text(doc):
    """текст всех оплаченных транскриптов документа (любой dpi), с номерами страниц"""
    out = []
    redact = os.environ.get('OPYT_REDACT', '').strip()
    for f in sorted(glob.glob(os.path.join(PAGES, f'{doc}_p*.md'))):
        m = re.search(r'_p(\d+)_(\d+)_', os.path.basename(f))
        if m:
            t = io.open(f, encoding='utf-8', errors='replace').read()
            if redact:
                # вырезаем строки с образцом: это и есть НАСТОЯЩИЙ контроль. Первый контроль
                # («Корпсан») провалился как контроль — строка 1520 = 2 275 / 3 248 в тексте
                # БЫЛА, и модель честно её нашла. Чтобы проверить, выдумывает ли модель,
                # надо забрать у неё строку и посмотреть, вернёт ли она пустой список.
                t = '\n'.join(ln for ln in t.splitlines()
                              if redact.lower() not in ln.lower())
            out.append((int(m.group(1)), int(m.group(2)), t))
    return out


def failing_picture(doc, form_key, total, parts):
    """что именно не сходится — по артефакту, без вызовов"""
    j = json.load(io.open(os.path.join(EX, doc + '.json'), encoding='utf-8'))
    items = (j.get(form_key) or {}).get('items') or []
    m = P.val_map(items)
    tv = m.get(total)
    if not tv:
        return None
    lines = []
    for i in range(len(tv)):
        if tv[i] is None:
            continue
        add = [(k, (m.get(k) or [None] * len(tv))[i]) for k in parts]
        have = [(k, v) for k, v in add if v is not None]
        s = sum(v for _, v in have)
        lines.append(f'  колонка {i + 1}: итог {total} = {tv[i]}, '
                     f'сумма {("+".join(k for k, _ in have))} = {s}, '
                     f'не сходится на {tv[i] - s:+}')
    return lines


for doc, form_key, total, parts, total_name, expect_code, expect_vals, note in CASES:
    pages = paid_text(doc)
    print(f'\n{"=" * 72}\n{doc} / {form_key}   {note}')
    print(f'  оплаченных страниц: {len(pages)}')
    pic = failing_picture(doc, form_key, total, parts)
    if not pic:
        print('  расхождения не найти — пропуск'); continue
    print('  расхождение:')
    for ln in pic:
        print('   ', ln)
    text = '\n'.join(f'--- страница {p} ({d} dpi) ---\n{t}' for p, d, t in pages)
    prompt = (
        f'Ниже транскрипция страниц бухгалтерского баланса (форма 0710001).\n'
        f'Разобранная форма НЕ СХОДИТСЯ сама с собой:\n' + '\n'.join(pic) + '\n\n'
        f'Значит в транскрипции есть строки, которые при разборе потерялись. '
        f'Найди ТОЛЬКО эти строки — те, что объясняют расхождение. '
        f'Не пересказывай всю таблицу и не выдумывай значений: если строки в тексте нет, '
        f'верни пустой список.\n'
        f'Ответ СТРОГО JSON: {{"missing": [{{"code": "1520", "name": "...", '
        f'"values": [v1, v2, v3]}}]}}\n\nТРАНСКРИПЦИЯ:\n{text}')
    n_before, cost_before = P.USAGE['calls'], P.USAGE['cost_rub']
    txt, fin = P.chat([{'role': 'user', 'content': prompt}], P.M_MAIN,
                      temperature=0, max_tokens=1500)
    print(f'  вызовов: {P.USAGE["calls"] - n_before}, '
          f'цена: {P.USAGE["cost_rub"] - cost_before:.4f} ₽, finish={fin}')
    try:
        obj = P.extract_json(txt)
    except Exception as e:
        print(f'  JSON не разобран: {e}\n  сырой ответ: {txt[:400]}')
        continue
    missing = obj.get('missing') or []
    print(f'  найдено строк: {len(missing)}')
    for it in missing:
        print(f"    code={it.get('code')} name={(it.get('name') or '')[:40]!r} "
              f"values={it.get('values')}")
    got = [it for it in missing if str(it.get('code')) == expect_code]
    if expect_vals is None:
        print(f'  КОНТРОЛЬ: ожидаем ПУСТО (в тексте строки {expect_code} нет)  ->  '
              f'{"ВЕРНО, не выдумала" if not missing else "ВЫДУМАЛА — методу нельзя верить"}')
    else:
        print(f'  ОЖИДАЕМ {expect_code} = {expect_vals}  ->  '
              f'{"НАЙДЕНО" if got else "НЕ НАЙДЕНО"}'
              + (f', значения {got[0].get("values")}' if got else ''))

print(f'\n{"=" * 72}')
print(f'вызовов всего: {P.USAGE["calls"]}, pt={P.USAGE["prompt"]}, ct={P.USAGE["completion"]}')
print(f'цена опыта: {P.USAGE["cost_rub"]:.4f} ₽')
