# -*- coding: utf-8 -*-
r"""Сборка и проверка файла профилей поставщиков.

Идентификаторы моделей PlusVibe в этой среде при выводе команд и чтении файлов
подменяются пустой строкой, поэтому вписать их в исходный код или в этот скрипт
руками нельзя — их невозможно ни проверить глазами, ни отредактировать. Здесь они
берутся из живого каталога и кладутся в JSON, а проверяются численно: длина и sha1.

    python verify_profiles.py            # собрать providers.json и показать сверку
    python verify_profiles.py --check    # только проверить существующий файл
"""
import io, os, sys, json, hashlib, argparse

sys.path.insert(0, r'D:\models')
import pipeline as P

CATALOG = r'D:\models\_pv_catalog.json'
OUT = r'D:\models\providers.json'
BASE = 'https://plusvibeapi.ru/v1/chat/completions'


def sha(s):
    return hashlib.sha1(str(s).encode()).hexdigest()[:10]


def load_catalog():
    if not os.path.exists(CATALOG):
        sys.exit(f'нет каталога {CATALOG} — сначала сохраните ответ GET /api/catalog')
    return json.load(io.open(CATALOG, encoding='utf-8'))


def find(cat, model):
    """запись каталога по идентификатору модели; имя в выводе не показываем"""
    h = sha(model)
    for m in cat:
        if sha(m.get('apiModel') or '') == h:
            return m
    return None


def variants(entry):
    out = []
    for v in entry.get('variants') or []:
        addr = str(v.get('addressAs') or '')
        if not addr:
            continue
        out.append({'addr': addr, 'in': v.get('inputRub'), 'out': v.get('outputRub'),
                    'label': v.get('label') or ''})
    return out


def cheapest(vs):
    return min(vs, key=lambda v: (v['in'] or 1e9) + (v['out'] or 1e9))


def preferred(vs, api_model):
    """вариант по умолчанию, если он есть: суффикс вида ':network' включает сетевой
    доступ, который для транскрипции страницы не нужен и только добавляет риска.
    Если варианта по умолчанию нет — берём самый дешёвый."""
    default = [v for v in vs if v['addr'] == api_model]
    return default[0] if default else cheapest(vs)


def vision(entry):
    return bool((entry.get('caps') or {}).get('vision'))


def build(cat):
    """профиль PlusVibe: три роли подбираются по каталогу, а не по памяти"""
    report = []
    roles, prices = {}, {}

    # транскрипция — та же модель, что у Polza, самый дешёвый вариант с картинками
    main_entry = find(cat, P.M_MAIN)
    if main_entry is None:
        sys.exit('в каталоге PlusVibe нет модели, которой Polza делает транскрипцию')
    mv = variants(main_entry)
    if not mv:
        sys.exit('у модели транскрипции нет ни одного варианта')
    main = preferred(mv, main_entry.get('apiModel'))
    roles['main'] = main['addr']
    report.append(('транскрипция', main, len(mv)))

    # детекция форм — самая дешёвая модель с поддержкой изображений
    vis = [m for m in cat if vision(m) and variants(m)]
    if not vis:
        sys.exit('в каталоге нет ни одной модели с поддержкой изображений')
    pick = min(vis, key=lambda m: cheapest(variants(m))['in'] or 1e9)
    det = preferred(variants(pick), pick.get('apiModel'))
    roles['detect'] = det['addr']
    report.append(('детекция', det, len(variants(pick))))

    # эскалация — та же модель, что у Polza
    esc_entry = find(cat, P.M_ESC)
    if esc_entry is None:
        sys.exit('в каталоге PlusVibe нет модели, которой Polza делает эскалацию')
    ev = variants(esc_entry)
    if not ev:
        sys.exit('у модели эскалации нет ни одного варианта')
    esc = preferred(ev, esc_entry.get('apiModel'))
    roles['esc'] = esc['addr']
    report.append(('эскалация', esc, len(ev)))

    for r in roles.values():
        e = find(cat, r.split(':')[0])
        for v in variants(e):
            if v['addr'] == r:
                prices[r] = [v['in'], v['out']]
    return roles, prices, report


def show(roles, prices):
    print('%-12s %-8s %-12s %-10s %-10s' % ('роль', 'длина', 'sha1', 'вход', 'выход'))
    for role, addr in sorted(roles.items()):
        pin, pout = prices.get(addr, (None, None))
        print('%-12s %-8d %-12s %-10s %-10s'
              % (role, len(addr), sha(addr), pin, pout))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='только проверить файл')
    args = ap.parse_args()

    cat = load_catalog()
    roles, prices, report = build(cat)
    print('=== подобранные роли (сверка по длине и sha1) ===')
    show(roles, prices)
    for name, v, n in report:
        print('  %-12s выбран вариант %r (всего вариантов %d, цена %s/%s)'
              % (name, v['label'], n, v['in'], v['out']))

    prof = {'providers': {'plusvibe': {
        'chat_url': BASE,
        'key_name': 'PLUSVIBE_API_KEY',
        'roles': roles,
        'prices': prices,
        'cache_tag': 'pv',
        'cost_header': 'x-pv-cost-rub',
        'note': ('адреса моделей подобраны из живого каталога PlusVibe '
                 '(verify_profiles.py) и сверены по длине и sha1; '
                 'метка pv входит в имена файлов кэша, ключи Polza не тронуты')}}}

    if args.check:
        if not os.path.exists(OUT):
            sys.exit(f'нет файла {OUT}')
        cur = json.load(io.open(OUT, encoding='utf-8'))['providers']['plusvibe']
        same = all(cur['roles'][r] == roles[r] for r in roles) and \
            cur.get('prices') == prices
        print('\nфайл совпадает с каталогом: %s' % ('да' if same else 'НЕТ'))
        for r in roles:
            print('  %-8s файл len=%d sha1=%s | каталог len=%d sha1=%s'
                  % (r, len(cur['roles'][r]), sha(cur['roles'][r]),
                     len(roles[r]), sha(roles[r])))
        sys.exit(0 if same else 1)

    io.open(OUT, 'w', encoding='utf-8').write(
        json.dumps(prof, ensure_ascii=False, indent=1) + '\n')
    print('\nзаписано: %s (%d байт)' % (OUT, os.path.getsize(OUT)))

    # проверка чтения: профиль должен подниматься движком
    os.environ['PILOT_PROVIDER'] = 'plusvibe'
    import providers as PR
    PR.reset()
    p = PR.active()
    print('активный профиль:', p)
    print('ключ найден, длина:', len(PR.load_key(p)))
    print('роли: ' + ', '.join('%s len=%d' % (r, len(p.roles[r])) for r in sorted(p.roles)))
    print('суффикс кэша: %r' % p.cache_suffix())
    url, headers, body = PR.build_request(p, p.roles['main'], [], 'K')
    print('запрос собирается: адрес len=%d, тело %d байт' % (len(url), len(body)))


if __name__ == '__main__':
    main()
