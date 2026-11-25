# -*- coding: utf-8 -*-
r"""Сравнение N моделей на одних и тех же страницах баланса (прайс 17.11.2026).

Зачем отдельный скрипт. `_ab_чтение.py` сравнивает ровно две руки (текущая и кандидат).
После обновления прайса кандидатов стало четыре, и вопрос сместился: не «заменить ли
эскалацию», а «какая модель на каждой роли». Поэтому руки задаются списком, а эталоном
служит модель, которая на этих же документах уже дала 6/6 — `google/gemini-3.8-flash`.

Как читать результат:
  * `ок` — сколько правил формы сошлось (арбитр: арифметика, текстового слоя у сканов нет);
  * `коды` / `клетки` — полнота: потеря строки не ломает правило, но это потеря данных;
  * `расх` — сколько клеток отличается от эталона (там хотя бы одна модель ошиблась);
  * `₽` — фактическая стоимость руки на этих страницах.

Производственный шов сохранён: `transcribe_cached` + `llm_structure_form` + `_normalize_llm`
+ `run_checks`. Кэш раздельный по модели, поэтому руки не переиспользуют чтение друг друга.

Запуск:
  python _ab_модели.py --docs "Кокс_9мес_2026.pdf,Рубеж_9мес_2026.pdf"
  python _ab_модели.py --forms balance,income_statement
"""
import json, os, sys

sys.path.insert(0, r'D:\models')
import pipeline as P
from _ab_чтение import read_form, probe, cells

SRC = r'D:\data-scraping\downloads'
OUT = r'D:\models\_ab_модели.json'

REF = 'google/gemini-3.8-flash'

# Кандидаты под роли. Цены — ₽/1 млн (вход/выход) из прайса 17.11.2026.
ARMS = [
    ('эталон gemini-3.8', 'google/gemini-3.8-flash', (4.72, 23.58), 'main сейчас'),
    ('sonnet-5.5',        'claude-sonnet-5.5',       (22.88, 114.40), 'esc'),
    ('sol 6.1',           'gpt-6.1-sol',             (11.00, 55.00), 'esc, OpenAI'),
    ('terra 6.1',         'gpt-6.1-terra',           (7.12, 35.60), 'esc/main, OpenAI'),
    ('luna 6',            'gpt-6-luna',              (3.00, 19.07), 'main, OpenAI'),
    ('luna 6 purple',     'gpt-6-luna:purple',       (0.72, 3.56), 'main, самый дешёвый'),
]


def diff_vs_ref(ref_items, items):
    ra, rb = cells(ref_items), cells(items)
    out = []
    for code in sorted(set(ra) | set(rb)):
        va, vb = ra.get(code) or [], rb.get(code) or []
        for i in range(max(len(va), len(vb))):
            x = va[i] if i < len(va) else None
            y = vb[i] if i < len(vb) else None
            if x != y:
                out.append((code, i, x, y))
    return out


def main(names, forms):
    report = []
    for k, n in enumerate(names, 1):
        path = n if os.path.isabs(n) else os.path.join(SRC, n)
        name = os.path.basename(path)
        print(f'===== [{k}/{len(names)}] {name}', flush=True)
        # страницы баланса берём из уже оплаченного артефакта; базовый прогон стоит 0
        art = os.path.join(P.OUTDIR, os.path.splitext(name)[0] + '.json')
        if not os.path.exists(art):
            print(f'  артефакта нет — сначала прогоните pipeline.py на {name}')
            continue
        base = json.load(open(art, encoding='utf-8'))
        doc = P.pymupdf.open(path)
        try:
            for form_key in forms:
                res = base.get(form_key) or {}
                pages = (res.get('transcript_pages') or [])[:8]
                if not pages:
                    print(f'  {form_key}: страниц нет — пропуск')
                    continue
                print(f'  {form_key}: страницы {pages}', flush=True)
                arm_data, ref_items = {}, None
                for label, model, price, role in ARMS:
                    items, u, err = read_form(doc, name, form_key, pages, model)
                    pr = probe(items, form_key) if items else dict(
                        checks=0, ok=0, fail=0, na=0, fail_rules=[], codes=0, filled=0, complete=False)
                    if model == REF:
                        ref_items = items
                    arm_data[label] = dict(model=model, price=price, role=role,
                                           usage=u, error=err, items=items, **pr)
                    print(f'    {label:<20} {u["cost"]:>7.3f} ₽ {u["seconds"]:>6.1f} с  '
                          f'ок {pr["ok"]}/{pr["checks"]}  коды {pr["codes"]:>3}  '
                          f'клетки {pr["filled"]:>4}'
                          + (f'  ОТКАЗ: {err[:70]}' if err else ''), flush=True)
                for label, d in arm_data.items():
                    d['diff_vs_ref'] = len(diff_vs_ref(ref_items, d['items'])) if ref_items else None
                    d['diff_sample'] = (diff_vs_ref(ref_items, d['items'])[:12]
                                        if ref_items else [])
                    d.pop('items')
                report.append(dict(file=name, form=form_key, pages=pages,
                                   arms={k: v for k, v in arm_data.items()}))
                print('    расхождения с эталоном: ' + ', '.join(
                    f'{k}={v["diff_vs_ref"]}' for k, v in arm_data.items()), flush=True)
        finally:
            doc.close()
        json.dump(report, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    json.dump(report, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print()
    print('=== СВОДКА ===')
    labels = [a[0] for a in ARMS]
    print(f'{"форма":<28}' + ''.join(f'{l[:13]:>15}' for l in labels))
    print(f'{"":28}' + ''.join(f'{"ок/расх ₽":>15}' for _ in labels))
    for r in report:
        row = f'{r["file"][:18] + "/" + r["form"][:6]:<28}'
        for l in labels:
            d = r['arms'][l]
            row += f'{str(d["ok"]) + "/" + str(d["diff_vs_ref"]):>10}{d["usage"]["cost"]:>5.2f}'
        print(row)
    print()
    for l in labels:
        costs = [r['arms'][l]['usage']['cost'] for r in report]
        oks = [r['arms'][l]['ok'] for r in report]
        fails = [r['arms'][l]['error'] for r in report if r['arms'][l]['error']]
        print(f'  {l:<20} всего {sum(costs):.2f} ₽  проверок ок {sum(oks)}/{6 * len(report)}'
              + (f'  отказов {len(fails)}' if fails else ''))
    print(f'  -> {OUT}')


if __name__ == '__main__':
    args = sys.argv[1:]
    forms = ('balance',)
    if '--forms' in args:
        i = args.index('--forms')
        forms = tuple(args[i + 1].split(','))
        args = args[:i] + args[i + 2:]
    names = []
    if '--docs' in args:
        i = args.index('--docs')
        names = [x.strip() for x in args[i + 1].split(',') if x.strip()]
        args = args[:i] + args[i + 2:]
    names += args
    if not names:
        print('укажите --docs "файл1.pdf,файл2.pdf"')
        sys.exit(2)
    main(names, forms)