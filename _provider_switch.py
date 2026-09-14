# -*- coding: utf-8 -*-
r"""Прогон одного документа через выбранного поставщика (приёмка задач 02–04).

Проверяет три вещи, которые нельзя проверить одними тестами:
  1. выбор поставщика переменной окружения действительно меняет адрес и ключ;
  2. ключи кэша Polza не тронуты и не создано ни одного нового файла;
  3. у другого поставщика появляются СВОИ файлы кэша, а прежние не изменяются.

    python _provider_switch.py --doc "Афанасий_6мес_2026" --provider polza
    python _provider_switch.py --doc "Афанасий_6мес_2026" --provider plusvibe
"""
import io, os, sys, json, glob, hashlib, argparse, subprocess

sys.path.insert(0, r'D:\models')
import pipeline as P

EX = r'D:\models\extracted'
PAGES = os.path.join(EX, 'pages')


def inventory():
    """Содержимое каждого файла кэша, а не время правки.

    Сравнивать время нельзя: текстовые разборы форм переписываются каждый прогон
    тем же содержимым, и по времени они выглядели бы «изменёнными».
    """
    inv = {}
    for fn in os.listdir(PAGES):
        p = os.path.join(PAGES, fn)
        if os.path.isfile(p):
            inv[fn] = sha(p)
    return inv


def sha(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha1()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()[:12]


def is_page_transcript(fn):
    """транскрипт страницы — то, за что платят: <документ>_p<стр>_<dpi>_<модель>...md"""
    return bool(__import__('re').match(r'^.+_p\d+_(200|300)_.+\.md$', fn))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--doc', required=True)
    ap.add_argument('--provider', default='plusvibe')
    ap.add_argument('--timeout', type=int, default=1800)
    args = ap.parse_args()

    pdf = os.path.join(r'D:\data-scraping\downloads', args.doc + '.pdf')
    result = os.path.join(EX, args.doc + '.json')
    if not os.path.exists(pdf):
        sys.exit('нет файла ' + pdf)

    before = inventory()
    result_before = sha(result)
    env = dict(os.environ)
    env['PILOT_PROVIDER'] = args.provider
    env['PYTHONIOENCODING'] = 'utf-8'

    t0 = __import__('time').time()
    pr = subprocess.run([sys.executable, os.path.join(r'D:\models', 'pipeline.py'), pdf],
                        env=env, cwd=r'D:\models', capture_output=True, timeout=args.timeout)
    out = (pr.stdout or b'').decode('utf-8', 'replace') + \
          (pr.stderr or b'').decode('utf-8', 'replace')
    io.open(rf'D:\models\_switch_{args.provider}.log', 'w', encoding='utf-8').write(out)
    secs = __import__('time').time() - t0

    after = inventory()
    new = sorted(set(after) - set(before))
    changed = sorted(k for k in before if k in after and after[k] != before[k])
    # Файлы страниц (_p<номер>_<dpi>_...) — это то, за что платят. Разборы форм из
    # текстового слоя (правилом, без модели) переписываются каждый прогон и в
    # приёмку не входят: они бесплатны и от поставщика не зависят.
    new_pages = [n for n in new if is_page_transcript(n)]
    new_other = [n for n in new if not is_page_transcript(n)]
    changed_pages = [n for n in changed if is_page_transcript(n)]
    changed_other = [n for n in changed if not is_page_transcript(n)]
    result_after = sha(result)

    lines = [f'# Прогон «{args.doc}» через поставщика {args.provider}', '',
             f'- код возврата: {pr.returncode}, время {secs:.0f} с',
             f'- новых транскриптов страниц: {len(new_pages)}',
             f'- изменённых транскриптов страниц: {len(changed_pages)}',
             f'- прочих новых файлов кэша: {len(new_other)}',
             f'- прочих изменённых файлов кэша: {len(changed_other)}',
             f'- результат: {result_before} -> {result_after}',
             '']
    cost = None
    for line in out.splitlines():
        if 'ИТОГО' in line or 'cost' in line.lower() and 'RUB' in line:
            lines.append('- ' + line.strip())
    m = __import__('re').findall(r'итого[^\n]*', out, __import__('re').I)
    if m:
        lines.append('- ' + m[-1].strip())

    if args.provider == 'polza':
        lines.append('')
        lines.append('Ожидание: ноль новых транскриптов страниц и неизменённые прежние — '
                     'иначе переключение профиля стоило бы повторной оплаты.')
    else:
        lines.append('')
        lines.append('Ожидание: появились СВОИ транскрипты (метка pv), '
                     'ползовские не изменены.')
    io.open(rf'D:\models\_switch_{args.provider}.md', 'w', encoding='utf-8').write(
        '\n'.join(lines) + '\n')

    print('\n'.join(lines))
    print('новые транскрипты (первые 5): ' + ', '.join(new_pages[:5]))
    print('изменённые транскрипты (первые 5): ' + ', '.join(changed_pages[:5]))
    print('прочие изменённые (первые 3): ' + ', '.join(changed_other[:3]))
    print('лог: _switch_%s.log' % args.provider)
    sys.exit(0 if pr.returncode == 0 else 1)


if __name__ == '__main__':
    main()
