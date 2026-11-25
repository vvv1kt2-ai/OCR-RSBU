# -*- coding: utf-8 -*-
r"""A/B моделей на ОДНИХ И ТЕХ ЖЕ страницах: независимое чтение баланса.

Постановка. Вопрос не «исправит ли дешёвая модель чужую ошибку», а «прочитает ли она
страницу не хуже». Это разные вопросы, и второй измерим всегда, а первый — только когда
арифметика формы уже не сходится. На пилоте новых отчётов провалов не оказалось ни одного,
поэтому эскалация не запускалась ни разу и сравнивать было нечего. Здесь обе модели читают
баланс ЗАНОВО, с одних и тех же отрендеренных страниц, и сравниваются между собой.

Арбитр — арифметика формы, а не мнение. У сканов нет текстового слоя, поэтому «верно» можно
установить только тем, что́ конвейер и так проверяет: сходятся ли итоги с слагаемыми
(`pipeline.run_checks`). Модель, у которой больше проверок сошлось, прочитала страницу лучше —
это утверждение слабее «прочитала верно», но проверяемое.

Что ещё меряется:
  * сколько кодов строк найдено (потеря строки — тоже ошибка чтения);
  * сколько клеток заполнено;
  * на скольких клетках две модели РАСХОДЯТСЯ — там хотя бы одна ошиблась, и это верхняя
    граница суммарной ошибки двух моделей;
  * деньги и время на каждую руку.

Производственный шов сохранён: те же `transcribe_cached`, `llm_structure_form`, `_normalize_llm`,
`run_checks`. Разница только в имени модели — а имя входит в ключ кэша, поэтому руки не
переиспользуют чтение друг друга и каждая платит ровно за себя.

Запуск:
  python _ab_чтение.py                       # документы из _новые_пилот.json
  python _ab_чтение.py файл.pdf ...
  python _ab_чтение.py --forms balance ...   # какие формы сравнивать
"""
import copy, json, os, sys, time

sys.path.insert(0, r'D:\models')
import pipeline as P

SRC = r'D:\data-scraping\downloads'
PILOT = r'D:\models\_новые_пилот.json'
OUT = r'D:\models\_ab_чтение.json'

# Руки. A — то, что стоит на эскалации сейчас; B — кандидат; C — контроль: модель,
# которая читает эти же страницы в проде (main), чтобы видеть, не хуже ли кандидат её.
ARMS = [
    ('A', 'anthropic/claude-sonnet-5:cxc'),       # текущая эскалация, живой канал
    ('B', 'claude-haiku-5.5'),                    # кандидат
]


def _reset_usage():
    P.USAGE['calls'] = 0
    P.USAGE['prompt'] = 0
    P.USAGE['completion'] = 0
    P.USAGE['cost_rub'] = 0.0


def _usage():
    return dict(calls=P.USAGE['calls'], prompt=P.USAGE['prompt'],
                completion=P.USAGE['completion'], cost=round(P.USAGE['cost_rub'], 4))


def _transcribe(doc, p, name, model, tries=4):
    """Чтение страницы с повтором на сетевых сбоях.

    Замер идёт через настоящий `transcribe_cached`, и это правильно: он же пишет кэш.
    Но шлюз в этот час отдаёт 502 примерно на каждой пятой странице, а `transcribe_cached`
    после трёх попыток бросает исключение — и документ выпадает из замера целиком. Повтор
    здесь только сокращает число выпавших документов; он ничего не меняет в результате,
    потому что каждый успешный ответ по-прежнему кэшируется штатно.
    """
    last = None
    for i in range(tries):
        try:
            return P.transcribe_cached(doc, p, name=name, dpi=P.ESC_DPI, model=model)
        except Exception as e:
            last = e
            print(f'      стр.{p}: попытка {i + 1}/{tries} не удалась ({str(e)[:60]})', flush=True)
            time.sleep(4 * (i + 1))
    raise last


def read_form(doc, name, form_key, pages, model):
    """Прочитать и структурировать форму одной моделью. Возвращает (items, usage, err).

    Шов ловится, а не роняет замер. `llm_structure_form` бросает исключение, когда ответ
    модели не разбирается как JSON (`extract_json`), и на замере это означает не «модель
    сломала прогон», а «модель не выдала пригодный ответ» — ровно тот факт, который надо
    измерить. Поэтому отказ фиксируется как результат руки, а не как падение скрипта.
    """
    _reset_usage()
    t0 = time.time()
    err = ''
    try:
        parts = []
        for p in pages:
            txt = _transcribe(doc, p, name, model)
            parts.append(f'=== СТРАНИЦА {p} ===\n{txt}')
    except Exception as e:
        u = _usage()
        u['seconds'] = round(time.time() - t0, 1)
        u['pages'] = len(pages)
        return [], u, f'чтение не удалось: {str(e)[:200]}'
    transcript = '\n\n'.join(parts)
    tag = (f'{os.path.splitext(name)[0]}_ab_{form_key}_p{"_".join(map(str, pages))}'
           f'_{P.model_tag(model)}')
    llm, items = None, []
    try:
        llm = P.cached_llm(tag, lambda: P.llm_structure_form(transcript, form_key, model=model)[0])
        items = P._normalize_llm(copy.deepcopy(llm), form_key)
    except Exception as e:
        err = f'структурирование: {type(e).__name__}: {e}'[:280]
        try:
            raw_path = os.path.join(P.PAGESDIR, f'_raw_{tag}.txt')
            txt, fin = P.chat([{'role': 'user', 'content':
                                f'Ниже транскрипция страниц отчетности: {P.FORM_TITLES[form_key]}.\n'
                                f'Структурируй в JSON. {P.SCHEMA_HINT}\n\nТРАНСКРИПЦИЯ:\n{transcript}'}],
                              model, temperature=0, max_tokens=32000)
            open(raw_path, 'w', encoding='utf-8').write(txt)
            err += f' | finish={fin}, len={len(txt)}, хвост: {txt[-120:]!r}'
        except Exception as e2:
            err += f' | повтор тоже упал: {str(e2)[:120]}'
    u = _usage()
    u['seconds'] = round(time.time() - t0, 1)
    u['pages'] = len(pages)
    return items, u, err


def probe(items, form_key):
    """Что можно измерить у одной редакции формы."""
    chks = P.run_checks(form_key, items)
    ok = [c for c in chks if c.get('ok')]
    fail = [c for c in chks if not c.get('ok') and c.get('verdict') != 'n/a']
    na = [c for c in chks if c.get('verdict') == 'n/a']
    return dict(
        checks=len(chks), ok=len(ok), fail=len(fail), na=len(na),
        fail_rules=[c.get('rule') for c in fail],
        codes=len({str(it.get('code')) for it in items
                   if it.get('code') and str(it.get('code')).isdigit()}),
        filled=P.filled_values(items),
        complete=P.form_is_complete(form_key, items),
    )


def cells(items):
    out = {}
    for it in items or []:
        for rec in [it] + (it.get('children') or []):
            c = rec.get('code')
            if c:
                out[str(c)] = list(rec.get('values') or [])
    return out


def diff(a, b):
    """Расхождения двух редакций по клеткам: список (код, колонка, A, B)."""
    ca, cb = cells(a), cells(b)
    out = []
    for code in sorted(set(ca) | set(cb)):
        va, vb = ca.get(code) or [], cb.get(code) or []
        for i in range(max(len(va), len(vb))):
            x = va[i] if i < len(va) else None
            y = vb[i] if i < len(vb) else None
            if x != y:
                out.append((code, i, x, y))
    return out


def base_pages(path, name):
    """Страницы баланса и состояние ДО эскалации — из оплаченного кэша, бесплатно."""
    out = os.path.join(P.OUTDIR, os.path.splitext(name)[0] + '.json')
    saved = open(out, 'rb').read() if os.path.exists(out) else None
    orig = P.escalate_failed_form
    P.escalate_failed_form = lambda *a, **k: None
    _reset_usage()
    try:
        r = P.process(path)
    finally:
        P.escalate_failed_form = orig
        if saved is not None:
            with open(out, 'wb') as f:
                f.write(saved)
    u = _usage()
    return r, u


def main(names, forms=('balance',)):
    report = []
    for i, n in enumerate(names, 1):
        path = n if os.path.isabs(n) else os.path.join(SRC, n)
        name = os.path.basename(path)
        print(f'===== [{i}/{len(names)}] {name}', flush=True)
        r, u0 = base_pages(path, name)
        print(f'  базовый прогон: {u0["cost"]} ₽ (кэш; ноль = всё уже оплачено)', flush=True)
        doc = P.pymupdf.open(path)
        try:
            for form_key in forms:
                res = r.get(form_key) or {}
                pages = res.get('transcript_pages') or []
                if not pages:
                    print(f'  {form_key}: страниц нет — пропуск')
                    continue
                if len(pages) > 8:
                    pages = pages[:8]
                print(f'  {form_key}: страницы {pages}', flush=True)
                arms = {}
                for label, model in ARMS:
                    items, u, err = read_form(doc, name, form_key, pages, model)
                    pr = probe(items, form_key) if items else dict(
                        checks=0, ok=0, fail=0, na=0, fail_rules=[], codes=0, filled=0, complete=False)
                    arms[label] = dict(model=model, items=items, usage=u, probe=pr, error=err)
                    print(f'    {label} {model}: {u["cost"]} ₽ {u["seconds"]} с; '
                          f'проверок ок {pr["ok"]}/{pr["checks"]}, '
                          f'провалов {pr["fail"]}, кодов {pr["codes"]}, '
                          f'клеток {pr["filled"]}'
                          + (f'  ОТКАЗ: {err[:100]}' if err else ''), flush=True)
                # контроль: что дала модель, читавшая эти же страницы в проде
                base_probe = probe(res['items'], form_key)
                d = diff(arms['A']['items'], arms['B']['items'])
                print(f'    расхождений A/B по клеткам: {len(d)}'
                      + (f'; примеры {d[:3]}' if d else ''), flush=True)
                print(f'    базовая (main) для справки: ок {base_probe["ok"]}/'
                      f'{base_probe["checks"]}, провалов {base_probe["fail"]}', flush=True)
                report.append(dict(
                    file=name, form=form_key, pages=pages,
                    base=base_probe,
                    a=dict(model=arms['A']['model'], usage=arms['A']['usage'],
                           error=arms['A']['error'], **arms['A']['probe']),
                    b=dict(model=arms['B']['model'], usage=arms['B']['usage'],
                           error=arms['B']['error'], **arms['B']['probe']),
                    diff_count=len(d), diff=d[:60],
                ))
        finally:
            doc.close()
        json.dump(report, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    json.dump(report, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print()
    print('=== ИТОГ ===')
    print(f'{"документ":<32}{"форма":<18}{"A ок":>6}{"B ок":>6}{"всего":>7}{"расх":>6}{"₽ A":>8}{"₽ B":>8}')
    for x in report:
        print(f'{x["file"][:31]:<32}{x["form"]:<18}{x["a"]["ok"]:>6}{x["b"]["ok"]:>6}'
              f'{x["a"]["checks"]:>7}{x["diff_count"]:>6}'
              f'{x["a"]["usage"]["cost"]:>8}{x["b"]["usage"]["cost"]:>8}')
    tot_a = sum(x['a']['usage']['cost'] for x in report)
    tot_b = sum(x['b']['usage']['cost'] for x in report)
    print(f'  стоимость: A {tot_a:.2f} ₽, B {tot_b:.2f} ₽')
    print(f'  -> {OUT}')


if __name__ == '__main__':
    args = sys.argv[1:]
    forms = ('balance',)
    if '--forms' in args:
        i = args.index('--forms')
        forms = tuple(args[i + 1].split(','))
        args = args[:i] + args[i + 2:]
    if args:
        names = args
    else:
        rows = json.load(open(PILOT, encoding='utf-8'))
        names = [x['file'] for x in rows if x.get('status') == 'ok']
        print('документы пилота со status=ok:', names)
    if names:
        main(names, forms)