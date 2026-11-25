# -*- coding: utf-8 -*-
r"""Выбор модели и варианта маршрута по стоимости — до прогона, а не после.

Зачем. Прайс поставщика меняется постоянно, вместе с ним меняются и варианты адресов:
17.11.2026 базовый `claude-sonnet-5` отдавал Cxc за 24.64/123.2, 24.11.2026 — Sub5max
за 87/432. Выбирать модель «на глаз» по цене за миллион токенов нельзя: ранг зависит от
соотношения вход/выход, а у ролей оно разное. Замер по журналу (16 754 вызова):

    main    1311 вх / 3177 вых на вызов  — 71% выхода
    detect 14918 вх / 1243 вых           —  8% выхода
    esc     1181 вх / 3211 вых           — 73% выхода

`detect` почти целиком входная, `main` и `esc` — выходные, поэтому «дешёвый вход» не
означает «дешёвый прогон». Скрипт считает стоимость на вызов по реальному профилю роли
и сортирует варианты по ней.

Что важно помнить при чтении вывода. Дешёвый вариант — это другой апстрим за шлюзом,
и качество там не обязано совпадать: `:network` кончился 503 на четырёх вызовах из
четырёх, haiku-5.5 и sonnet-5.5 путают разряды. Числа здесь — про деньги. Перед сменой
варианта нужен слепой замер качества на наших документах (`_ab_модели.py`).

Запуск:
  python choose_model.py                          # все три роли, варианты текущих моделей
  python choose_model.py --role esc               # только эскалация
  python choose_model.py --role detect --model deepseek-v4.1-flash
  python choose_model.py --top 15                 # 15 самых дешёвых вариантов из прайса
  python choose_model.py --role detect --compare "deepseek-v4.1-flash:yellow,gpt-6-luna:purple"
  python choose_model.py --role detect --profile 14918:1243    # профиль задан вручную
  python choose_model.py --prices "D:\models\модели и цены\Книга3.xlsx" --calls 500

Профиль не константа. Он зависит от качества исходных PDF: замер по журналу даёт долю
выхода у main 32…85%, у detect 1…90%, у esc 37…97%. Поэтому скрипт печатает диапазон
и отдельно проверяет, меняется ли победитель при доле выхода 5% и 95%. Внутри одной модели
дешёвый вариант обычно дешевле по обеим осям и ранг не меняется; при сравнении РАЗНЫХ
моделей он может перевернуться — тогда печатается предупреждение, и профиль надо задать
явно через --profile.
"""
import argparse
import glob
import io
import json
import os
import sys

MODELS = r'D:\models'
sys.path.insert(0, MODELS)

USAGE_DEFAULT = os.path.join(MODELS, 'plusvibe-usage.ndjson')
DOWNLOADS = os.path.join(os.path.expanduser('~'), 'Downloads')


# ─── прайс поставщика ──────────────────────────────────────────────────────
def newest_price_file(folder=DOWNLOADS):
    """Свежайший .xlsx в Downloads — так файл прайса и попадает на машину."""
    files = sorted(glob.glob(os.path.join(folder, '*.xlsx')),
                   key=os.path.getmtime, reverse=True)
    return files[0] if files else None


def _num(v):
    """Число из ячейки: в прайсе встречается и «4,72», и 4.72."""
    if v is None or v == '':
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace('\u00a0', '').replace(' ', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def parse_prices(path):
    """[(модель, поставщик, вариант, адрес, вход, выход)] из листа прайса.

    Строки-разделители групп («━━━ claude-sonnet-5 ━━━») задают текущую модель;
    строки с адресом в колонке «model (для API)» — варианты.
    """
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    out, group, stamp = [], '', None
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        cells = list(row) + [None] * (6 - len(row))
        a, vendor, variant, addr, pin, pout = cells[:6]
        if i == 0 and a:
            stamp = str(a)
            continue
        if isinstance(a, str) and a.strip().startswith('━'):
            group = a.strip().strip('━').strip()
            continue
        # строка заголовка: в колонке «Модель» стоит «Модель», а в колонке адреса —
        # «model (для API)». Без этой проверки шапка становилась «вариантом» с пустой ценой
        if isinstance(a, str) and a.strip().lower() == 'модель':
            continue
        if not addr:
            continue
        out.append((group, str(vendor or '').strip(), str(variant or '').strip(),
                    str(addr).strip(), _num(pin), _num(pout)))
    wb.close()
    return out, stamp


# ─── профиль токенов из журнала ────────────────────────────────────────────
def base_name(address):
    """`anthropic/claude-sonnet-5:cxc` -> `claude-sonnet-5`: без вендора и без варианта."""
    a = str(address or '').split('/')[-1]
    return a.split(':')[0].strip()


def token_profile(path, roles):
    """{роль: (вход/вызов, выход/вызов, вызовов)} по журналу usage и ролям профиля.

    Роль определяется по базовому имени модели: в журнале адрес может быть записан без
    вендорного префикса и с хвостом варианта.
    """
    want = {base_name(addr): role for role, addr in roles.items() if addr}
    agg = {role: [0, 0, 0] for role in roles}
    if not os.path.exists(path):
        return {}
    for line in io.open(path, encoding='utf-8'):
        try:
            r = json.loads(line)
        except Exception:
            continue
        role = want.get(base_name(r.get('model')))
        if not role:
            continue
        a = agg[role]
        a[0] += r.get('prompt_tokens') or 0
        a[1] += r.get('completion_tokens') or 0
        a[2] += 1
    return {role: (p / n, c / n, n) for role, (p, c, n) in agg.items() if n}


def _quantile(xs, p):
    xs = sorted(xs)
    if not xs:
        return 0.0
    k = (len(xs) - 1) * p
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def share_spread(path, roles):
    """{роль: (доля выхода p10, доля выхода p90)} — насколько профиль роли неоднороден.

    Профиль не константа: он зависит от качества исходных PDF. Замер по журналу:
    у main доля выхода 32…85%, у detect 1…90%, у esc 37…97%. Одно среднее это скрывает,
    поэтому диапазон печатается рядом с расчётом.
    """
    want = {base_name(addr): role for role, addr in roles.items() if addr}
    acc = {role: [] for role in roles}
    if not os.path.exists(path):
        return {}
    for line in io.open(path, encoding='utf-8'):
        try:
            r = json.loads(line)
        except Exception:
            continue
        role = want.get(base_name(r.get('model')))
        if not role:
            continue
        a = r.get('prompt_tokens') or 0
        b = r.get('completion_tokens') or 0
        if a + b:
            acc[role].append(b / (a + b))
    return {role: (_quantile(v, .1), _quantile(v, .9)) for role, v in acc.items() if v}


def cheapest_at_share(rows, tokens_total, share, calls):
    """(стоимость, адрес) самого дешёвого варианта при заданной доле выхода."""
    best = None
    for rec in rows:
        pin, pout = rec[4], rec[5]
        if pin is None or pout is None:
            continue
        c = (tokens_total * (1 - share) / 1e6 * pin
             + tokens_total * share / 1e6 * pout) * calls
        if best is None or c < best[0]:
            best = (c, rec[3])
    return best


def cost_per_calls(pin, pout, tokens_in, tokens_out, calls=1000):
    """Стоимость N вызовов при данном профиле токенов, ₽."""
    if pin is None or pout is None:
        return None
    return (tokens_in / 1e6 * pin + tokens_out / 1e6 * pout) * calls


# ─── вывод ─────────────────────────────────────────────────────────────────
def fmt(x):
    return '—' if x is None else f'{x:,.2f}'.replace(',', ' ')


def show(rows, role, prof, calls, current, spread=None):
    tokens_in, tokens_out, n_calls = prof
    total = tokens_in + tokens_out
    share = tokens_out / total if total else 0
    src = (f'профиль по {n_calls} вызовам' if n_calls else 'профиль задан вручную')
    tail = f'; в журнале доля выхода {spread[0]:.0%}…{spread[1]:.0%}' if spread else ''
    print(f'\n{role}: {src} — {tokens_in:.0f} вх / {tokens_out:.0f} вых на вызов '
          f'(выход {share:.0%}{tail}), считаю за {calls} вызовов')
    print(f'{"адрес":44s} {"вариант":24s} {"вх/вых":>15s} {"₽":>11s}  {"×":>5s}')
    # база сравнения — текущий адрес роли, а не самый дешёвый вариант: тогда ×1.00
    # означает «как сейчас», и экономия читается без пересчёта
    base = None
    for group, vendor, variant, addr, pin, pout in rows:
        if addr == current:
            base = cost_per_calls(pin, pout, tokens_in, tokens_out, calls)
    if base is None and rows:
        base = cost_per_calls(rows[0][4], rows[0][5], tokens_in, tokens_out, calls)
    for group, vendor, variant, addr, pin, pout in rows:
        c = cost_per_calls(pin, pout, tokens_in, tokens_out, calls)
        if c is None:
            continue
        mark = '  ← сейчас' if addr == current else ''
        print(f'{addr:44s} {variant[:24]:24s} {fmt(pin)}/{fmt(pout):>8s} '
              f'{c:11.2f}  {c / base:5.2f}{mark}')
    # Ранг зависит от профиля только тогда, когда у вариантов РАЗНЫЕ соотношения вход/выход.
    # Внутри одной модели дешёвый вариант обычно дешевле по обеим осям, и профиль на выбор
    # не влияет. Проверяем это явно, а не обещаем.
    lo = cheapest_at_share(rows, total, 0.05, calls)
    hi = cheapest_at_share(rows, total, 0.95, calls)
    if lo and hi:
        if lo[1] == hi[1]:
            print(f'  ранг устойчив к профилю: при доле выхода 5%…95% дешевле {lo[1]}')
        else:
            print(f'  ВНИМАНИЕ: ранг зависит от профиля — при 5% выхода дешевле {lo[1]}, '
                  f'при 95% — {hi[1]}. Задайте профиль явно через --profile, '
                  f'если корпус отличается от того, по которому снят журнал.')
    return base


def main():
    ap = argparse.ArgumentParser(description='Стоимость вариантов моделей на реальном профиле токенов')
    ap.add_argument('--role', choices=('main', 'detect', 'esc'), default=None)
    ap.add_argument('--model', default=None,
                    help='фильтр по имени модели или группы (подстрока, без учёта регистра)')
    ap.add_argument('--top', type=int, default=None,
                    help='показать N самых дешёвых вариантов по всему прайсу')
    ap.add_argument('--prices', default=None, help='файл прайса .xlsx (по умолчанию свежий в Downloads)')
    ap.add_argument('--usage', default=USAGE_DEFAULT, help='журнал вызовов .ndjson')
    ap.add_argument('--calls', type=int, default=1000, help='за сколько вызовов считать')
    ap.add_argument('--compare', default=None,
                    help='адреса через запятую — сравнить разные модели между собой; '
                         'профиль берётся у роли из --role (по умолчанию main)')
    ap.add_argument('--profile', default=None,
                    help='профиль на вызов «вход:выход», например 1181:3211 — когда корпус '
                         'отличается от того, по которому снят журнал')
    args = ap.parse_args()

    path = args.prices or newest_price_file()
    if not path or not os.path.exists(path):
        sys.exit('нет файла прайса: укажите --prices путь.xlsx')
    prices, stamp = parse_prices(path)
    if not prices:
        sys.exit(f'в {path} не нашлось ни одной строки с адресом модели')
    print(f'прайс: {path}')
    if stamp:
        print(f'в файле: {stamp}')

    import providers as PR
    profile = PR.active()
    roles = dict(profile.roles)
    prof = token_profile(args.usage, roles)
    spreads = share_spread(args.usage, roles)
    if args.profile:
        try:
            _in, _out = (float(x) for x in args.profile.replace(' ', '').split(':'))
        except ValueError:
            sys.exit('--profile ожидает «вход:выход» на вызов, например 1181:3211')
        prof = {role: (_in, _out, 0) for role in roles}
        spreads = {}
    if not prof:
        sys.exit(f'в журнале {args.usage} нет вызовов ни по одной роли профиля — '
                 f'профиль ролей: {roles}')

    def rows_for(role, needle=None):
        current = roles.get(role)
        target = base_name(current) if role else None
        out = []
        for rec in prices:
            group, vendor, variant, addr, pin, pout = rec
            hay = f'{group} {addr} {variant}'.lower()
            if needle and needle.lower() not in hay:
                continue
            if role and not needle and base_name(addr) != target and group != target:
                continue
            out.append(rec)
        return sorted(out, key=lambda r: cost_per_calls(r[4], r[5],
                                                        prof[role][0], prof[role][1], 1) or 0)

    if args.top:
        # самый дешёвый вариант по всему прайсу — для поиска альтернатив, не для решения
        tokens_in, tokens_out, _n = max(prof.values(), key=lambda t: t[2])
        ranked = sorted(prices, key=lambda r: cost_per_calls(r[4], r[5], tokens_in, tokens_out, 1) or 0)
        print(f'\n{args.top} самых дешёвых вариантов прайса при профиле '
              f'{tokens_in:.0f} вх / {tokens_out:.0f} вых на вызов:')
        print(f'{"адрес":44s} {"вариант":24s} {"вх/вых":>15s} {"₽":>11s}')
        for rec in ranked[:args.top]:
            c = cost_per_calls(rec[4], rec[5], tokens_in, tokens_out, args.calls)
            if c is None:
                continue
            print(f'{rec[3]:44s} {rec[2][:24]:24s} {fmt(rec[4])}/{fmt(rec[5]):>8s} {c:11.2f}')
        return

    if args.compare:
        # Сравнение РАЗНЫХ моделей: у них разные соотношения вход/выход, поэтому ранг
        # здесь действительно может зависеть от профиля — страж в show() это и печатает.
        role = args.role or 'main'
        if role not in prof:
            sys.exit(f'для сравнения нужен профиль роли {role!r}, а вызовов этой роли '
                     f'в журнале нет — задайте профиль через --profile вход:выход')
        by_addr = {rec[3]: rec for rec in prices}
        wanted = [a.strip() for a in args.compare.split(',') if a.strip()]
        rows = [by_addr[a] for a in wanted if a in by_addr]
        missing = [a for a in wanted if a not in by_addr]
        if missing:
            print(f'нет в прайсе: {", ".join(missing)}')
        if not rows:
            sys.exit('ни одного адреса из --compare нет в прайсе')
        rows = sorted(rows, key=lambda r: cost_per_calls(
            r[4], r[5], prof[role][0], prof[role][1], 1) or 0)
        show(rows, f'сравнение моделей (профиль {role})', prof[role], args.calls, None,
             spreads.get(role))
        print('\nЦена — не качество: дешёвый вариант обслуживается другим апстримом. '
              'Перед сменой нужен слепой замер на наших документах (_ab_модели.py).')
        return

    targets = [args.role] if args.role else [r for r in ('main', 'detect', 'esc') if r in prof]
    for role in targets:
        if role not in prof:
            print(f'\n{role}: в журнале нет вызовов этой роли — профиль неизвестен, пропускаю')
            continue
        rows = rows_for(role, args.model)
        if not rows:
            print(f'\n{role}: в прайсе нет строк по фильтру {args.model!r}')
            continue
        show(rows, role, prof[role], args.calls, roles.get(role), spreads.get(role))

    print('\nЦена — не качество: дешёвый вариант обслуживается другим апстримом. '
          'Перед сменой нужен слепой замер на наших документах (_ab_модели.py).')


if __name__ == '__main__':
    main()
