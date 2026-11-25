# -*- coding: utf-8 -*-
"""Пересчёт артефактов ТЕКУЩИМ кодом из оплаченного кэша — без вызовов модели.

Зачем. Артефакты в `extracted/` писались разными версиями `pipeline.py` за две недели и
вдобавок правились скриптами `_fix*`. Поэтому вывод о правилах, сделанный по сохранённым
артефактам, рискует оказаться выводом о СТАРОМ коде. Обратное тоже верно: артефакт нельзя
считать доказательством того, что текущий код на этом документе работает.

Что делает. Берёт оплаченный ответ модели на структурирование формы из `extracted/pages/`,
прогоняет его через текущие `_normalize_llm` и `run_checks` и сравнивает с артефактом.
Модели не вызываются, кэш не пишется, артефакты не меняются.

Честность пары. Кэшей на одну форму бывает несколько (polza и plusvibe, целиком и по
страницам, половины A/B), а артефакт не записывает, из какого он сделан. Поэтому пара
СНАЧАЛА ПРОВЕРЯЕТСЯ: пересобранный набор верхнеуровневых кодов должен совпасть с набором
артефакта. Не совпал — кэш чужой, вывод по нему не делается, пара попадает в «не
воспроизведено». Это защита от вывода о чужом кэше: без неё «Эфферон» сравнивался бы с
кэшем, в котором нет 1700.

Выход: сколько форм воспроизвелось, где вердикт разошёлся, что не воспроизвелось и почему.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline as P

FORMS = ('balance', 'income_statement', 'cash_flow')
TERMINAL = {'balance': '1700', 'income_statement': '2400', 'cash_flow': '4500'}


def _infix_order():
    """Сначала кэш активного поставщика, потом прежнего — как их читает сам конвейер."""
    active = P._provider_infix()
    legacy = P._provider_infix(P._providers.PROFILES[P._providers.LEGACY_PROVIDER])
    out = [active]
    if legacy not in out:
        out.append(legacy)
    return out


def _foreign_infixes():
    """Суффиксы ЧУЖИХ поставщиков: файл с таким хвостом читать нельзя."""
    keep = set(_infix_order())
    return {P._provider_infix(p) for p in P._providers.PROFILES.values()} - keep


def candidates(stem, form_key, want_pages):
    """Кэши структурирования формы, лучший первым.

    Порядок доверия: постраничный добор с теми же страницами, что в артефакте -> форма
    целиком -> половины A/B. Внутри каждой группы — сначала активный поставщик.
    """
    groups = [
        [f'_llm_{stem}_tstruct_{form_key}_p*.json'],
        [f'_llm_{stem}_struct_{form_key}.json',
         f'_llm_{stem}_struct_{form_key}_?.json'],
        [f'_llm_{stem}_tstruct_{form_key}*.json'],
    ]
    foreign = _foreign_infixes()
    out = []
    for infix in _infix_order():
        for pats in groups:
            for pat in pats:
                for path in sorted(glob.glob(os.path.join(P.PAGESDIR, pat))):
                    base = os.path.basename(path)
                    if infix and not base.endswith(f'{infix}.json'):
                        continue
                    if not infix and any(base.endswith(f'{x}.json') for x in foreign):
                        continue
                    if path not in out:
                        out.append(path)
    if want_pages:
        out.sort(key=lambda p: 0 if _pages_of(p) == want_pages else 1)
    return out


def _pages_of(path):
    m = re.search(r'_p(\d+(?:_\d+)*)\.json$', os.path.basename(path))
    return [int(x) for x in m.group(1).split('_')] if m else None


def top_codes(items):
    return {it.get('code') for it in items or [] if it.get('code')}


def rebuild(stem, form_key, want_pages):
    """(items, columns, путь, предупреждения) или (None, причина)."""
    tried = []
    for path in candidates(stem, form_key, want_pages):
        try:
            llm = json.load(open(path, encoding='utf-8'))
        except Exception as e:
            tried.append(f'{os.path.basename(path)}: не читается ({e})')
            continue
        if not isinstance(llm, dict) or not llm.get('items'):
            tried.append(f'{os.path.basename(path)}: нет items')
            continue
        warns = []
        items = P._normalize_llm(json.loads(json.dumps(llm)), form_key, warnings=warns)
        yield items, llm.get('columns') or [], os.path.basename(path), warns, tried


def main():
    files = [f for f in sorted(glob.glob(os.path.join(P.OUTDIR, '*.json')))
             if not os.path.basename(f).startswith('_')]
    ok_pairs = 0
    bad_pairs = []
    drift = []
    art_fail = new_fail = 0
    for f in files:
        d = json.load(open(f, encoding='utf-8'))
        stem = os.path.splitext(os.path.basename(f))[0]
        for form_key in FORMS:
            form = d.get(form_key)
            if not form:
                continue
            art_items = form.get('items') or []
            art_codes = top_codes(art_items)
            want_pages = form.get('transcript_pages') or None
            got = None
            for items, columns, src, warns, tried in rebuild(stem, form_key, want_pages):
                new_codes = top_codes(items)
                if new_codes == art_codes:
                    got = (items, columns, src, warns)
                    break
                missing = sorted(art_codes - new_codes)
                extra = sorted(new_codes - art_codes)
                tried.append(f'{src}: коды не совпали (нет {missing[:4]}, лишние {extra[:4]})')
            if not got:
                bad_pairs.append((stem, form_key, tried[-3:]))
                continue
            ok_pairs += 1
            items, columns, src, warns = got
            old = {c['rule']: c['ok'] for c in P.run_checks(form_key, art_items)}
            new = {c['rule']: c['ok'] for c in P.run_checks(form_key, items)}
            art_fail += sum(1 for v in old.values() if v is False)
            new_fail += sum(1 for v in new.values() if v is False)
            diff = {r: (old.get(r), new.get(r)) for r in set(old) | set(new)
                    if old.get(r) != new.get(r)}
            if diff:
                drift.append((stem, form_key, src, diff, warns))
    print(f'артефактов: {len(files)}')
    print(f'форм с подтверждённой парой «артефакт <-> кэш»: {ok_pairs}')
    print(f'форм без подтверждённой пары: {len(bad_pairs)}')
    print(f'провалов правил: в артефактах {art_fail} -> на текущем коде {new_fail}')
    print()
    if bad_pairs:
        print('--- не воспроизведено (кэш чужой или отсутствует) ---')
        for stem, form_key, why in bad_pairs:
            print(f'{stem} [{form_key}]')
            for w in why:
                print(f'    {w[:150]}')
        print()
    print('--- вердикт разошёлся при подтверждённой паре ---')
    if not drift:
        print('    нет')
    for stem, form_key, src, diff, warns in drift:
        print(f'{stem} [{form_key}] из {src}')
        for rule, (a, b) in sorted(diff.items()):
            print(f'    {a} -> {b}   {rule}')
        for w in [x for x in warns if 'дубль' in x][:3]:
            print(f'    причина: {w[:120]}')


if __name__ == '__main__':
    main()
