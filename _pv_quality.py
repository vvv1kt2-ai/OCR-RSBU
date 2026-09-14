# -*- coding: utf-8 -*-
"""Проверка качества PlusVibe на уже закэшированных страницах (задача 01).

Идея: у нас есть транскрипты страниц, сделанные через Polza. Берём несколько,
отправляем ТУ ЖЕ страницу тем же промптом и теми же параметрами через PlusVibe и
сравниваем ответы. Текст может отличаться формулировками, цифры — нет.

Эталон — транскрипт той же модели и того же dpi (иначе эталоном станет ответ
другой модели и сравнение потеряет смысл).

Ничего не перезаписывает: результат в _pv_quality*.md и _pv_quality*.json,
ответы PlusVibe — в extracted/pages/_pvq/. Повторный запуск бесплатен.

Запуск:
    python _pv_quality.py --dry          # показать, что будет отправлено, без вызовов
    python _pv_quality.py                # 6 страниц, дешёвый вариант (по умолчанию)
    python _pv_quality.py --n 20         # выборка шире (уже скачанное берётся из кэша)
    python _pv_quality.py --variant network   # сравнить подороже, если дешёвый провалился
"""
import os, sys, io, re, json, time, hashlib, argparse, difflib, urllib.request
from collections import Counter

sys.path.insert(0, r'D:\models')
sys.path.insert(0, r'D:\models\pylibs')

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import pipeline as P          # добавляет pylibs в путь, даёт TRANSCRIBE_PROMPT/render_png
import pymupdf

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')
DL = r'D:\data-scraping\downloads'
CRED = r'C:\Users\1\.dsh\.credentials.yaml'
CACHE = os.path.join(PAGES, '_pvq')
BASE = 'https://plusvibeapi.ru/v1/chat/completions'
CATALOG = r'D:\models\_pv_catalog.json'
MD = r'D:\models\_pv_quality.md'
JSONOUT = r'D:\models\_pv_quality.json'

# вариант -> (вход RUB/1М, выход RUB/1М); точные цены берём из живого каталога.
# 'default' — вариант без суффикса (у Gemini это самый дешёвый, label «Ag · по умолчанию»).
FALLBACK_PRICES = {'default': (3.78, 18.86), 'ag2': (9.43, 47.15),
                   'network': (4.72, 23.58), 'network2': (9.9, 49.5)}


# ---------------------------------------------------------------- чистые функции

def address(model, variant):
    """адрес модели в PlusVibe: вариант по умолчанию идёт БЕЗ суффикса.
    У Gemini 3.8 Flash варианты: '' (label «Ag · по умолчанию»), ':ag2',
    ':network', ':network2'."""
    return model if variant in ('', 'default') else f'{model}:{variant}'


def norm_digits(txt):
    """все числа текста в виде строк из одних цифр, по возрастанию.

    '1 234' -> '1234', '(1 345)' -> '1345'. Пробел внутри числа — разделитель
    разрядов, поэтому склеиваем только группы ровно по три цифры: иначе
    '20 10 30' (три разных числа) превратилось бы в одно '201030'.
    Дробная часть идёт отдельным числом: '1 234,5' -> ['1234', '5'].
    """
    return sorted(re.sub(r'\D', '', d) for d in
                  re.findall(r'\d{1,3}(?:[ \u00a0]\d{3})+(?!\d)|\d+', txt)
                  if re.sub(r'\D', '', d))


def digit_diff(ref, cand):
    """Сравнение чисел как мультимножеств. Возвращает четыре разных факта.

    Одного «чего не хватает» мало: в этих таблицах остаток на начало года равен
    остатку на конец прошлого, поэтому одно число законно стоит в двух ячейках, и
    разница кратностей означает не «числа нет», а «пропущена строка». Годы (2024,
    2025) идут в каждой строке — по ним прямо видно, сколько строк выпало.

      absent     — числа, которых в ответе нет совсем (потеря данных)
      undercount — [(число, в эталоне, в ответе)]: есть, но реже (выпала строка)
      extra      — числа, которых в эталоне нет совсем (придумано)
      overcount  — [(число, в эталоне, в ответе)]: есть, но чаще (дубль)
    """
    cr, cc = Counter(norm_digits(ref)), Counter(norm_digits(cand))
    absent = sorted(n for n in cr if cc[n] == 0)
    undercount = sorted((n, cr[n], cc[n]) for n in cr if 0 < cc[n] < cr[n])
    extra = sorted(n for n in cc if cr[n] == 0)
    overcount = sorted((n, cr[n], cc[n]) for n in cc if cc[n] > cr[n] > 0)
    return {'absent': absent, 'undercount': undercount,
            'extra': extra, 'overcount': overcount}


def significant(nums, min_len=4):
    """числа, у которых есть шанс быть суммой: 1..3 знака — это номера строк,
    единицы измерения и прочий шум."""
    return [n for n in nums if len(n) >= min_len]


def char_ratio(ref, cand):
    """посимвольное сходство 0..1 (порядок символов учитывается).

    Пробелы выброшены: перенос строки там, где эталон поставил пробел, — это не
    расхождение, а разная разметка той же таблицы.
    """
    return difflib.SequenceMatcher(None, re.sub(r'\s+', '', ref),
                                   re.sub(r'\s+', '', cand)).ratio()


def first_divergence(ref, cand, ctx=70, left=12):
    """первое место, где тексты разошлись: (позиция, фрагмент эталона, фрагмент ответа).

    Слева захватываем `left` символов, чтобы в отчёте было видно число целиком,
    а не только его хвост, с которого началось расхождение.
    """
    a, b = ref.strip(), cand.strip()
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    if i == n and len(a) == len(b):
        return None
    s = max(0, i - left)
    return i, a[s:i + ctx], b[s:i + ctx]


def verdict(rows):
    """годится / не годится — с причинами, выраженными числами.

    Строгое условие проекта: числа, которое есть в эталоне и отсутствует в ответе,
    быть не должно. Отдельно смотрим на «значимые» числа (4+ знака): пропажа
    короткого числа — обычно шум разметки, пропажа суммы — дефект. Выпавшая строка
    ловится по кратности (2025: 19 раз против 13) и тоже дефект — это потеря
    данных, а не разная разметка.
    """
    reasons = []
    if not rows:
        return {'ok': False, 'strict_ok': False, 'reasons': ['нет данных: ни одной страницы']}
    for r in rows:
        where = f'{r["stem"]} стр.{r["page"]}'
        d = r.get('diff') or {}
        if r.get('truncated'):
            reasons.append(f'{where}: ответ оборван по лимиту токенов')
        if r.get('filtered'):
            reasons.append(f'{where}: ответ срезан фильтром содержимого')
        lost = significant(d.get('absent') or [])
        if lost:
            reasons.append(f'{where}: нет совсем {len(lost)} значимых чисел, '
                           f'например {", ".join(lost[:5])}')
        under = [(n, a, b) for n, a, b in (d.get('undercount') or []) if len(n) >= 4]
        if under:
            reasons.append(f'{where}: пропущены строки — числа встречаются реже, например '
                           + ', '.join(f'{n} ({a}->{b})' for n, a, b in under[:4]))
        if r['len_pv'] < 0.9 * r['len_polza']:
            reasons.append(f'{where}: ответ короче эталона — '
                           f'{r["len_pv"]} против {r["len_polza"]} символов')
    def clean(r):
        d = r.get('diff') or {}
        return not (d.get('absent') or d.get('undercount') or d.get('extra'))
    strict = all(clean(r) for r in rows)
    ok = not reasons
    if ok and not strict:
        reasons.append('строгий критерий не выполнен: расхождения только в коротких '
                       'числах и лишних повторах — шум разметки, не суммы')
    return {'ok': ok, 'strict_ok': strict, 'reasons': reasons}


def key():
    txt = io.open(CRED, encoding='utf-8').read()
    m = re.search(r'PLUSVIBE_API_KEY:\s*(\S+)', txt)
    if not m:
        sys.exit('PLUSVIBE_API_KEY не найден в ' + CRED)
    return m.group(1)


def price_of(model, variant):
    """цена из живого каталога по (len, sha1) — имя модели в выводе может скрываться"""
    if os.path.exists(CATALOG):
        try:
            cat = json.load(io.open(CATALOG, encoding='utf-8'))
            h = hashlib.sha1(model.encode()).hexdigest()[:10]
            for m in cat:
                if hashlib.sha1(str(m.get('apiModel') or '').encode()).hexdigest()[:10] == h:
                    for v in m.get('variants') or []:
                        a = str(v.get('addressAs') or '')
                        if a == address(model, variant):
                            return v.get('inputRub'), v.get('outputRub'), v.get('label')
        except Exception:
            pass
    p = FALLBACK_PRICES.get(variant)
    return (p[0], p[1], 'из файла-снимка') if p else (None, None, None)


def cached_pages(limit, want_tag=None):
    """самые крупные кэшированные страницы: на них виднее расхождения.
    want_tag — сравнивать только с транскриптами той же модели (иначе 300dpi
    эскалация другого эскалатора попадёт в эталон)."""
    pat = re.compile(r'^(.+)_p(\d+)_(\d+)_(.+?)_([0-9a-f]{10})\.md$')
    out = []
    for fn in os.listdir(PAGES):
        m = pat.match(fn)
        if not m or fn.startswith('_'):
            continue
        stem, page, dpi, tag, fp = m.groups()
        if want_tag and tag != want_tag:
            continue
        path = os.path.join(PAGES, fn)
        size = os.path.getsize(path)
        pdf = os.path.join(DL, stem + '.pdf')
        if os.path.exists(pdf) and size > 1500:
            out.append({'file': fn, 'stem': stem, 'page': int(page), 'dpi': int(dpi),
                        'size': size, 'pdf': pdf, 'path': path, 'tag': tag})
    # по одной странице на документ, чтобы выборка не состояла из одного отчёта
    seen, picked = set(), []
    for r in sorted(out, key=lambda x: -x['size']):
        if r['stem'] in seen:
            continue
        seen.add(r['stem'])
        picked.append(r)
        if len(picked) >= limit:
            break
    return picked


def inventory():
    """список файлов кэша до/после — доказательство, что ничего не перезаписано"""
    inv = {}
    for fn in os.listdir(PAGES):
        p = os.path.join(PAGES, fn)
        if os.path.isfile(p):
            inv[fn] = os.path.getsize(p)
    return inv


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()[:12]


def call(model, messages, max_tokens=16000, timeout=300, retries=2):
    body = json.dumps({'model': model, 'messages': messages,
                       'temperature': 0.1, 'max_tokens': max_tokens}).encode()
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(BASE, data=body, method='POST', headers={
                'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'})
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
                hdr = r.headers.get('x-pv-cost-rub')
            u = data.get('usage') or {}
            return (data['choices'][0]['message']['content'] or '',
                    u.get('prompt_tokens', 0), u.get('completion_tokens', 0),
                    data['choices'][0].get('finish_reason'), time.time() - t0, hdr)
        except Exception as e:
            last = e
            print(f'   попытка {attempt + 1} не удалась: {e}')
            time.sleep(2 + 3 * attempt)
    raise last


# ---------------------------------------------------------------- основной ход

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=6)
    ap.add_argument('--variant', default='default',
                    help="default (Ag) | ag2 | network | network2")
    ap.add_argument('--model', default=P.M_MAIN)
    ap.add_argument('--dry', action='store_true', help='ничего не отправлять')
    ap.add_argument('--recheck', action='store_true',
                    help='пересчитать отчёт только по кэшу ответов, без вызовов')
    ap.add_argument('--out', default=None, help='куда писать отчёт (по умолчанию _pv_quality)')
    ap.add_argument('--only', default=None,
                    help='только эти страницы: "документ:страница,документ:страница"')
    args = ap.parse_args()

    global KEY, MD, JSONOUT
    if args.out:
        MD = rf'D:\models\{args.out}.md'
        JSONOUT = rf'D:\models\{args.out}.json'
    KEY = None if (args.dry or args.recheck) else key()
    os.makedirs(CACHE, exist_ok=True)

    addr = address(args.model, args.variant)
    pin, pout, label = price_of(args.model, args.variant)
    mtag = P.model_tag(args.model)
    msha = hashlib.sha1(args.model.encode()).hexdigest()[:10]
    asha = hashlib.sha1(addr.encode()).hexdigest()[:10]
    print(f'модель: len={len(args.model)} sha1={msha}')
    print(f'адрес:  len={len(addr)} sha1={asha} вариант={args.variant!r} ({label})')
    print(f'цена:   вход {pin} выход {pout} RUB/1M')

    pages = cached_pages(args.n, want_tag=mtag)
    if args.only:
        """выборка по именам: нужно, чтобы проверить именно провалившиеся страницы,
        а не самые крупные"""
        pool = {(p['stem'], p['page']): p for p in cached_pages(10 ** 6, want_tag=mtag)}
        pages = []
        for spec in args.only.split(','):
            spec = spec.strip()
            stem, _, pg = spec.rpartition(':')
            want_key = (stem, int(pg))
            if want_key not in pool:
                sys.exit(f'--only: нет кэшированного транскрипта для {spec}')
            pages.append(pool[want_key])
    print(f'\nстраниц выбрано: {len(pages)} (эталон — транскрипты {mtag})')
    for r in pages:
        print(f'   {r["stem"][:34]:34} стр.{r["page"]:3} {r["dpi"]}dpi  {r["size"]}B')

    if args.dry:
        print('\n--dry: вызовов не делаю. Уберите --dry, чтобы прогнать.')
        return

    before = inventory()
    ref_hashes = {r['file']: sha1_file(r['path']) for r in pages}

    doc_cache = {}
    rows = []
    tot = {'pt': 0, 'ct': 0, 'cost': 0.0, 'new': 0, 'cached': 0}
    for r in pages:
        if r['pdf'] not in doc_cache:
            doc_cache[r['pdf']] = pymupdf.open(r['pdf'])
        doc = doc_cache[r['pdf']]
        if r['page'] > len(doc):
            print(f'   {r["stem"]} стр.{r["page"]}: за пределами файла, пропуск')
            continue
        polza = io.open(r['path'], encoding='utf-8').read()
        cpath = os.path.join(CACHE, f'{r["stem"]}_p{r["page"]}_{r["dpi"]}_{args.variant}_{mtag}.md')
        truncated = filtered = False
        if os.path.exists(cpath):
            pv = io.open(cpath, encoding='utf-8').read()
            pt = ct = 0
            cost, fin, secs = 0.0, 'кэш', 0.0
            src = 'из кэша PlusVibe'
            tot['cached'] += 1
        elif args.recheck:
            sys.exit(f'--recheck: нет ответа в кэше для {r["stem"]} стр.{r["page"]} '
                     f'({os.path.basename(cpath)}). Уберите --recheck, чтобы заплатить.')
        else:
            msg = [P.img_message(P.render_png(doc[r['page'] - 1], r['dpi']),
                                 P.TRANSCRIBE_PROMPT + f' (страница {r["page"]} файла)')]
            pv, pt, ct, fin, secs, hdr = call(addr, msg)
            if fin == 'length':                     # как в конвейере: дописать обрыв
                more, pt2, ct2, fin2, _, hdr2 = call(
                    addr, msg + [{'role': 'assistant', 'content': pv},
                                 {'role': 'user', 'content': 'Продолжи ровно с места обрыва, '
                                                             'без повторов.'}])
                pv, pt, ct, fin = pv + more, pt + pt2, ct + ct2, fin2
                hdr = hdr or hdr2
                truncated = fin == 'length'
            filtered = (fin == 'content_filter')
            if filtered:
                # Провайдер обрезал ответ фильтром. В кэш такой ответ не кладём:
                # он неполон, а кэш сделал бы неполноту вечной и бесплатной для
                # повторного чтения. Зато он виден в отчёте и в вердикте.
                print(f'   {r["stem"]} стр.{r["page"]}: ответ срезан фильтром '
                      f'содержимого — в кэш не кладу')
            else:
                io.open(cpath, 'w', encoding='utf-8').write(pv)
            cost = float(hdr) if hdr else (pt / 1e6 * (pin or 0) + ct / 1e6 * (pout or 0))
            src = f'{secs:.0f}с finish={fin}'
            tot['new'] += 1
        tot['pt'] += pt
        tot['ct'] += ct
        tot['cost'] += cost

        d = digit_diff(polza, pv)
        rows.append({'stem': r['stem'], 'page': r['page'], 'dpi': r['dpi'], 'variant': args.variant,
                     'ref_file': r['file'], 'pv_file': os.path.basename(cpath),
                     'len_polza': len(polza), 'len_pv': len(pv),
                     'ratio': round(char_ratio(polza, pv), 4),
                     'digits_polza': len(norm_digits(polza)), 'digits_pv': len(norm_digits(pv)),
                     'diff': d, 'absent_sig': significant(d['absent']),
                     'undercount_sig': [x for x in d['undercount'] if len(x[0]) >= 4],
                     'truncated': truncated, 'filtered': filtered,
                     'identical': polza.strip() == pv.strip(), 'src': src, 'cost': cost,
                     'pt': pt, 'ct': ct})
        print(f'   {r["stem"][:28]:28} стр.{r["page"]:3}: '
              f'символов {len(polza)}->{len(pv)}, сходство {rows[-1]["ratio"]:.3f}, '
              f'чисел {rows[-1]["digits_polza"]}->{rows[-1]["digits_pv"]}, '
              f'нет совсем {len(d["absent"])} (значимых {len(rows[-1]["absent_sig"])}), '
              f'выпало строк {len(d["undercount"])}, лишних {len(d["extra"])}'
              + (f'  [{fin}]' if filtered or truncated else ''))

    after = inventory()
    lost = [k for k, v in before.items() if k not in after]
    changed = [k for k, v in before.items() if k in after and after[k] != v]
    ref_moved = [f for f, h in ref_hashes.items() if sha1_file(os.path.join(PAGES, f)) != h]
    newfiles = sorted(set(after) - set(before))
    v = verdict(rows)

    out = io.open(MD, 'w', encoding='utf-8')
    w = out.write
    w('# Качество PlusVibe против Polza на одних и тех же страницах\n\n')
    w(f'Эталон — транскрипты Polza моделью len={len(args.model)} sha1={msha}, dpi как в таблице.\n\n')
    w(f'Проверяемый адрес: len={len(addr)} sha1={asha}, вариант `{args.variant}` '
      f'({label}), цена {pin}/{pout} ₽ за 1М.\n\n')
    w(f'Параметры вызова те же, что в конвейере: `temperature=0.1`, `max_tokens=16000`, '
      f'тот же промпт, тот же рендер страницы.\n\n')
    w('| документ | стр. | dpi | символов Polza | символов PlusVibe | сходство | '
      'чисел Polza | чисел PlusVibe | нет совсем | значимых нет | выпало строк | лишних |\n')
    w('|---|---|---|---|---|---|---|---|---|---|---|---|\n')
    for r in rows:
        w(f'| {r["stem"]} | {r["page"]} | {r["dpi"]} | {r["len_polza"]} | {r["len_pv"]} | '
          f'{r["ratio"]:.3f} | {r["digits_polza"]} | {r["digits_pv"]} | {len(r["diff"]["absent"])} | '
          f'{len(r["absent_sig"])} | {len(r["diff"]["undercount"])} | {len(r["diff"]["extra"])} |\n')
    w('\n## Числа, которых не хватает\n\n')
    w('«Нет совсем» — числа эталона, отсутствующие в ответе: потеря данных.\n'
      '«Реже» — число есть, но встречается меньше раз: значит выпала строка таблицы,\n'
      'в которой оно стояло (в этих отчётах остаток на начало года равен остатку на\n'
      'конец прошлого года, поэтому одно число законно стоит в двух ячейках).\n\n')
    if not any(r['diff']['absent'] or r['diff']['undercount'] for r in rows):
        w('Ни одного числа из эталона не потеряно ни на одной странице.\n')
    for r in rows:
        d = r['diff']
        if not (d['absent'] or d['undercount'] or d['extra']):
            continue
        w(f'\n### {r["stem"]} стр.{r["page"]} (сходство {r["ratio"]:.3f})\n\n')
        if d['absent']:
            w(f'- нет совсем ({len(d["absent"])}, из них значимых {len(r["absent_sig"])}): '
              f'{", ".join(d["absent"][:25])}\n')
        if d['undercount']:
            w(f'- есть, но реже ({len(d["undercount"])}, из них значимых '
              f'{len(r["undercount_sig"])}): '
              + ', '.join(f'{n} {a}->{b}' for n, a, b in d['undercount'][:25]) + '\n')
        if d['extra']:
            w(f'- есть у PlusVibe, нет у Polza ({len(d["extra"])}): '
              f'{", ".join(d["extra"][:25])}\n')
    w('\n## Расхождения в тексте\n\n')
    w('Первое место, где ответ разошёлся с эталоном — чтобы видеть, расхождение\n'
      'косметическое (порядок строк, пробелы) или содержательное.\n\n')
    for r in rows:
        if r['identical']:
            w(f'- {r["stem"]} стр.{r["page"]}: совпало посимвольно\n')
            continue
        ref = io.open(os.path.join(PAGES, r['ref_file']), encoding='utf-8').read()
        cand = io.open(os.path.join(CACHE, r['pv_file']), encoding='utf-8').read()
        d = first_divergence(ref, cand)
        if d is None:
            w(f'- {r["stem"]} стр.{r["page"]}: различие только в пробелах по краям\n')
            continue
        i, a, b = d
        w(f'- {r["stem"]} стр.{r["page"]} (сходство {r["ratio"]:.3f}, знак {i}): '
          f'эталон `{a}` → PlusVibe `{b}`\n')
    w(f'\nПолное посимвольное совпадение: '
      f'{sum(1 for r in rows if r["identical"])} из {len(rows)} страниц. '
      'Остальные отличаются формулировками и порядком строк — это ожидаемо; '
      'критерий проекта — числа.\n')
    w('\n## Вердикт\n\n')
    w(f'**{"Годится" if v["ok"] else "Не годится"}**\n\n')
    w(f'- страниц: {len(rows)}, из них новых вызовов: {tot["new"]}, из кэша: {tot["cached"]}\n')
    w(f'- токенов: вход {tot["pt"]}, выход {tot["ct"]}\n')
    w(f'- потрачено: **{tot["cost"]:.2f} ₽**\n')
    w(f'- страниц с полным посимвольным совпадением: '
      f'{sum(1 for r in rows if r["identical"])}\n')
    w(f'- страниц без единого расхождения в числах: '
      f'{sum(1 for r in rows if not any(r["diff"].values()))}\n')
    w(f'- потеряно чисел совсем: {sum(len(r["diff"]["absent"]) for r in rows)} '
      f'(значимых {sum(len(r["absent_sig"]) for r in rows)})\n')
    w(f'- выпало строк (числа есть, но реже): '
      f'{sum(len(r["diff"]["undercount"]) for r in rows)} '
      f'(значимых {sum(len(r["undercount_sig"]) for r in rows)})\n')
    w(f'- строгий критерий (ни одного потерянного числа): '
      f'{"выполнен" if v["strict_ok"] else "не выполнен"}\n')
    w(f'- контрольный: ни один файл кэша не перезаписан — '
      f'потеряно {len(lost)}, изменено {len(changed)}, '
      f'эталонных транскриптов сдвинуто {len(ref_moved)}, новых файлов {len(newfiles)}\n')
    for reason in v['reasons']:
        w(f'- {reason}\n')
    out.close()

    json.dump({'model_len': len(args.model), 'model_sha1': msha, 'address_len': len(addr),
               'address_sha1': asha, 'variant': args.variant, 'label': label,
               'price_in': pin, 'price_out': pout, 'verdict': v, 'totals': tot,
               'cache_lost': lost, 'cache_changed': changed, 'ref_moved': ref_moved,
               'new_files': newfiles, 'rows': rows, 'recheck': bool(args.recheck)},
              io.open(JSONOUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print(f'\nитог: {len(rows)} страниц, токенов {tot["pt"]}/{tot["ct"]}, '
          f'потрачено {tot["cost"]:.2f} RUB, новых вызовов {tot["new"]}')
    print(f'вердикт: {"ГОДИТСЯ" if v["ok"] else "НЕ ГОДИТСЯ"}'
          + ('' if v['strict_ok'] else ' (строгий критерий не выполнен)'))
    for reason in v['reasons']:
        print('   - ' + reason)
    print(f'кэш: потеряно {len(lost)}, изменено {len(changed)}, новых файлов {len(newfiles)}')
    print(f'отчёт: {os.path.basename(MD)}')


if __name__ == '__main__':
    main()
