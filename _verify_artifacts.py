# -*- coding: utf-8 -*-
"""Приёмка артефактов: сходятся ли прочитанные цифры и где именно подозрение на чтение.

Зачем. Цель правил — не «привести суммы», а заметить НЕВЕРНО ПРОЧИТАННУЮ ЦИФРУ. Провал
правила сам по себе этого не доказывает: невязка возникает и тогда, когда строка прочитана
верно, но в JSON оказалась вне итога родителя (типовой случай — «Обязательство по аренде»
отдельной строкой внутри раздела V). Перечитывание страницы в 300 dpi лечит только первый
случай, поэтому различать их обязательно: иначе провал покупает эскалацию там, где чинить
надо разбор.

Что проверяется по каждому артефакту:
  1. провенанс — записаны ли method / provider / ocr_model;
  2. вердикт каждого правила, ПЕРЕСЧИТАННЫЙ по items (сохранённым checks верить нельзя:
     их писали прежние версии правил);
  3. для каждого провала — невязка по колонке и попытка её ОБЪЯСНИТЬ: есть ли в том же
     разделе строка, которая в сумму не вошла, а её значение равно невязке. Объяснилось —
     это разбор, не чтение;
  4. status: сохранённый против пересчитанного;
  5. слой правок corrections.json против триажа: есть ли пометка на каждое подозрение на
     чтение, не поехали ли данные под пометкой, не устарела ли правка.

Модели не вызываются, кэш не пишется, артефакты не меняются. Стоимость прогона — ноль.

Использование:
    python _verify_artifacts.py              # отчёт в stdout
    python _verify_artifacts.py --strict     # код возврата 1, если есть расхождения
    python _verify_artifacts.py --md ФАЙЛ    # дополнительно записать отчёт в markdown
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline as P

FORMS = ('balance', 'income_statement', 'cash_flow')
FORM_RU = {'balance': 'баланс', 'income_statement': 'ОФР', 'cash_flow': 'ОДДС'}

# Правила-суммы без знаков: по ним невязку можно посчитать точно и объяснить. Правила со
# знаками сюда не входят намеренно — их невязка зависит от соглашения о знаках, и
# «объяснение» по ней было бы догадкой.
SUM_RULES = {
    'balance': [
        ('1400', ('1410', '1420', '1430', '1440', '1450')),
        ('1500', ('1510', '1520', '1530', '1540', '1550')),
    ],
}

TOL = 2


def rows_deep(items, depth=0, parent=None):
    for it in items or []:
        yield it, depth, parent
        yield from rows_deep(it.get('children'), depth + 1, it)


def explain_residual(resid, total, parts, items, col):
    """Строка, объясняющая невязку, или None.

    Объясняющей считается строка, которая В СУММУ НЕ ВОШЛА, а её значение равно невязке.
    Не вошла — значит либо лежит вложенной (val_map видит только верхний уровень), либо
    её код не назван среди слагаемых правила. Вложенная строка с кодом слагаемого (так
    модель печатает «Обязательство по аренде» — с кодом 1520) тоже объясняет невязку:
    в сумму она не попала именно из-за вложенности.
    """
    top = {id(it) for it in items or []}
    for it, depth, parent in rows_deep(items):
        code = it.get('code')
        if id(it) in top and (code == total or code in parts):
            continue                      # это сам итог или уже посчитанное слагаемое
        if code == total:
            continue
        vals = it.get('values') or []
        v = vals[col] if col < len(vals) else None
        if v is None:
            continue
        if abs(resid - v) <= TOL:
            return {'name': (it.get('name') or '')[:70], 'code': code,
                    'value': v, 'depth': depth,
                    'parent': (parent or {}).get('code')}
    return None


def triage(form_key, items):
    """Разбор правил-сумм раздела: [(правило, колонка, невязка, объяснение|None)]."""
    m = P.val_map(items)
    n = max((len(it.get('values') or []) for it in items), default=0)
    out = []
    for total, parts in SUM_RULES.get(form_key, ()):
        tvals = m.get(total) or []
        for c in range(n):
            tot = tvals[c] if c < len(tvals) else None
            if tot is None:
                continue
            add = [(m.get(k) or [None] * (c + 1))[c] for k in parts]
            add = [v for v in add if v is not None]
            if not add:
                continue
            resid = tot - sum(add)
            if abs(resid) <= TOL:
                continue
            out.append((f'{total} == {"+".join(parts)}', c, resid,
                        explain_residual(resid, total, parts, items, c)))
    return out


def check_artifact(path):
    """Отчёт по одному артефакту."""
    name = os.path.basename(path)
    d = json.load(open(path, encoding='utf-8'))
    src = d.get('source') or {}
    rep = {'file': name, 'doc': os.path.splitext(name)[0],
           'status_saved': d.get('status'),
           'status_live': None, 'provenance': [], 'forms': [],
           'reading': [], 'reading_cols': [], 'structure': [], 'fail': [],
           'unverified': []}

    for key in ('method', 'provider', 'ocr_model'):
        if not src.get(key):
            rep['provenance'].append(key)

    live = {}
    for form_key in FORMS:
        form = d.get(form_key)
        if not form:
            continue
        items = form.get('items') or []
        chks = P.run_checks(form_key, items)
        # status считается по ok (как в decide_status: «проверено и сходится»), а провалом
        # для отчёта считается только verdict='fail' — правило без данных это не провал.
        live[form_key] = [bool(c['ok']) for c in chks]
        f = {'form': form_key, 'ru': FORM_RU[form_key], 'rules': [],
             'stored_status': d.get('status')}
        for c in chks:
            f['rules'].append({'rule': c['rule'], 'ok': c['ok'],
                               'verdict': c.get('verdict'),
                               'per_column': c['per_column']})
            if c.get('verdict') == 'n/a':
                rep.setdefault('unverified', []).append(
                    f'{name} | {FORM_RU[form_key]} | {c["rule"]}')
        for rule, col, resid, why in triage(form_key, items):
            rec = (f'{name} | {FORM_RU[form_key]} | {rule} | кол.{col} | невязка {resid}')
            if why:
                rep['structure'].append(rec + f' | строка «{why["name"]}» = {why["value"]} '
                                              f'(код {why["code"]}, глубина {why["depth"]}, '
                                              f'родитель {why["parent"]})')
            else:
                rep['reading'].append(rec)
                rep['reading_cols'].append((form_key, col, rule))
        for c in chks:
            if P.is_failure(c):
                rep['fail'].append(f'{name} | {FORM_RU[form_key]} | {c["rule"]} | '
                                   f'{c["per_column"]}')
        rep['forms'].append(f)

    unread = src.get('unread_pages') or []
    has_form = any(d.get(k) for k in FORMS)
    if live or has_form:
        rep['status_live'] = P.decide_status(live, unread, has_form)
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--strict', action='store_true',
                    help='вернуть код 1, если есть расхождения (для приёмки перед сборкой свода)')
    ap.add_argument('--md', metavar='ФАЙЛ', help='записать отчёт в markdown')
    args = ap.parse_args()

    files = [f for f in sorted(glob.glob(os.path.join(P.OUTDIR, '*.json')))
             if not os.path.basename(f).startswith('_')]
    reps = [check_artifact(f) for f in files]

    status_drift = [r for r in reps if r['status_live'] != r['status_saved']]
    no_prov = [r for r in reps if r['provenance']]
    reading = [x for r in reps for x in r['reading']]
    structure = [x for r in reps for x in r['structure']]
    fails = [x for r in reps for x in r['fail']]
    # Единицы счёта разные и путать их нельзя: правило получает вердикт на форму целиком
    # (провал, если хотя бы одна колонка не сошлась), а невязка считается ПО КОЛОНКЕ.
    # Поэтому невязок всегда больше, чем провалов.
    cols = len(reading) + len(structure)
    unverified = [x for r in reps for x in r['unverified']]

    # ─── слой правок: сходятся ли пометки с тем, что видно в артефактах ───
    # Сверяем именно с ТРИАЖЕМ (reading), а не с сырыми провалами: провал из-за строки
    # вне родительского итога — особенность разбора, человеку там смотреть нечего.
    import corrections as corr_mod
    corr = corr_mod.Corrections.load()
    arts = {r['doc']: json.load(open(f, encoding='utf-8')) for f, r in zip(files, reps)}
    suspicions = [(r['doc'], fk, col, rule)
                  for r in reps for (fk, col, rule) in r['reading_cols']]
    uncovered = corr_mod.uncovered(corr, suspicions)
    inv = corr_mod.invisible_entries(corr, corr_mod.svod_codes())
    findings = corr.reconcile(arts)
    by_status = {}
    for f in findings:
        by_status.setdefault(f['status'], []).append(f)
    drifted = by_status.get(corr_mod.DRIFTED, [])
    stale = by_status.get(corr_mod.STALE, [])
    norow = by_status.get(corr_mod.NO_ROW, [])
    cc = corr.counts()

    print(f'артефактов: {len(reps)}')
    print(f'провалов правил (правило x документ): {len(fails)}')
    print(f'невязок по колонкам: {cols}')
    print(f'  объяснено разбором (строка вне итога): {len(structure)}')
    print(f'  ПОДОЗРЕНИЕ НА ЧТЕНИЕ: {len(reading)}')
    print(f'правил без данных (n/a — не провал): {len(unverified)}')
    print(f'status расходится с пересчётом: {len(status_drift)}')
    print(f'артефактов с неполным провенансом: {len(no_prov)} (не блокирует приёмку)')
    print()
    print(f'слой правок corrections.json: записей {len(corr.entries)} — '
          f'спорных {cc["disputed"]}, правок {cc["corrected"]}, '
          f'подтверждено {cc["confirmed"]}, снято {cc["rejected"]}')
    print(f'  подозрений на чтение БЕЗ ПОМЕТКИ: {len(uncovered)}')
    print(f'  пометок с разошедшимися данными: {len(drifted)}')
    print(f'  устаревших правок: {len(stale)}')
    print(f'  пометок на отсутствующие строки: {len(norow)}')
    print(f'  пометок вне колонок свода (в силе, но не видны): {len(inv)}')
    print()

    if reading:
        print('--- ПОДОЗРЕНИЕ НА ЧТЕНИЕ (сюда и только сюда оправдана эскалация) ---')
        for x in reading:
            print('  ', x)
        print()
    if structure:
        print('--- НЕВЯЗКА ОБЪЯСНЕНА РАЗБОРОМ (перечитывание страницы не поможет) ---')
        for x in structure:
            print('  ', x)
        print()
    if status_drift:
        print('--- status расходится с пересчётом ---')
        for r in status_drift:
            print(f'  {r["file"]}: сохранён {r["status_saved"]!r} -> по items '
                  f'{r["status_live"]!r}')
        print()
    if no_prov:
        print('--- неполный провенанс (нет полей source.*) ---')
        for r in no_prov:
            print(f'  {r["file"]}: нет {r["provenance"]}')
        print()
    if uncovered:
        print('--- подозрение на чтение, на которое НЕТ ПОМЕТКИ в corrections.json ---')
        for doc, fk, col, rule in uncovered:
            print(f'  {doc} {FORM_RU[fk]} кол.{col}: {rule}')
        print()
    if drifted or stale or norow:
        print('--- пометки, требующие внимания ---')
        for label, group in (('ДАННЫЕ ПОЕХАЛИ', drifted), ('ПРАВКА УСТАРЕЛА', stale),
                             ('СТРОКИ НЕТ', norow)):
            for f in group:
                e = f['entry']
                print(f'  [{label}] {e["doc"]} {e["form"]} кол.{e["column"]} '
                      f'{corr_mod.target_ru(e)}: {f["why"]}')
        print()
    if inv:
        print('--- пометки вне колонок свода (в силе, но в своде не видны) ---')
        for e in inv:
            print(f'  {e["doc"]} {FORM_RU.get(e["form"], e["form"])} '
                  f'кол.{e["column"]}: {corr_mod.target_ru(e)}')
        print()

    if args.md:
        with open(args.md, 'w', encoding='utf-8') as fh:
            fh.write('# Проверка артефактов: сходятся ли прочитанные цифры\n\n')
            fh.write(f'Артефактов: {len(reps)}. Провалов правил (правило x документ): '
                     f'{len(fails)}. Невязок по колонкам: {cols} — объяснено разбором '
                     f'{len(structure)}, подозрение на чтение {len(reading)}. '
                     f'Status расходится с пересчётом: {len(status_drift)}.\n\n')
            fh.write('## Подозрение на чтение\n\n')
            for x in reading or ['нет']:
                fh.write(f'- {x}\n')
            fh.write('\n## Невязка объяснена разбором\n\n')
            for x in structure or ['нет']:
                fh.write(f'- {x}\n')
            fh.write('\n## status расходится с пересчётом\n\n')
            for r in status_drift or []:
                fh.write(f'- {r["file"]}: {r["status_saved"]!r} -> {r["status_live"]!r}\n')
            fh.write('\n## Все провалы правил\n\n')
            for x in fails or ['нет']:
                fh.write(f'- {x}\n')

            fh.write('\n## Слой правок (corrections.json)\n\n')
            fh.write(f'Записей: {len(corr.entries)} — спорных {cc["disputed"]}, '
                     f'правок {cc["corrected"]}, подтверждено {cc["confirmed"]}, '
                     f'снято {cc["rejected"]}. Артефакты в `extracted/` остаются чистым '
                     f'выводом кода, слой лежит отдельно.\n\n')
            fh.write(f'**Подозрений на чтение без пометки: {len(uncovered)}**\n\n')
            for doc, fk, col, rule in uncovered:
                fh.write(f'- {doc} | {FORM_RU[fk]} | кол.{col} | {rule}\n')
            if not uncovered:
                fh.write('- нет\n')
            fh.write(f'\n**Пометок с разошедшимися данными: {len(drifted)}. '
                     f'Устаревших правок: {len(stale)}. '
                     f'Пометок на отсутствующие строки: {len(norow)}.**\n\n')
            for label, group in (('ДАННЫЕ ПОЕХАЛИ', drifted), ('ПРАВКА УСТАРЕЛА', stale),
                                 ('СТРОКИ НЕТ', norow)):
                for f in group:
                    e = f['entry']
                    fh.write(f'- [{label}] {e["doc"]} {e["form"]} кол.{e["column"]} '
                             f'{corr_mod.target_ru(e)}: {f["why"]}\n')
            fh.write(f'\n**Пометок вне колонок свода: {len(inv)}** '
                     f'(в силе, но в своде не видны — коды не входят в колонки)\n\n')
            for e in inv:
                fh.write(f'- {e["doc"]} | {FORM_RU.get(e["form"], e["form"])} | '
                         f'кол.{e["column"]} | {corr_mod.target_ru(e)}\n')
        print(f'отчёт записан: {args.md}')

    # Приёмка смотрит только на то, что требует действия: непроверенная цифра,
    # разошедшийся status и расхождения слоя правок. Неполный провенанс — признак
    # артефакта, снятого до правки кода; он лечится перепрогоном, а не правкой,
    # поэтому в код возврата не входит.
    if args.strict and (reading or status_drift or uncovered or drifted or stale or norow):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
