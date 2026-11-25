# -*- coding: utf-8 -*-
r"""Публикация скачанных отчётов в S3 (Cloud.ru Evolution) и таблица ссылок.

Зачем именно так.

1. Ссылка должна быть ПОСТОЯННОЙ. Публичный доступ через Bucket Policy даёт адрес вида
   https://global.s3.cloud.ru/<бакет>/<ключ> без срока жизни; ограничение по времени есть
   только у предподписанных URL (X-Amz-Expires), и для таблицы, которая живёт месяцами,
   они не годятся.

2. Ключ должен быть читаемым и устойчивым. Имя эмитента меняется («Артген» / «Артген (ИСКЧ)»),
   поэтому ключ строится из транслита, а ИНН добавляется, когда он есть в артефакте.
   Кириллица в ключе формально допустима, но при копировании ссылки из Excel превращается
   в процентную кашу — поэтому транслит.

3. Замена файла не должна ломать ссылку. У «Спектра» отчёт уже перезаливали: сначала пришёл
   только с пояснениями. Поэтому канонический ключ ПЕРЕЗАПИСЫВАЕТСЯ, а прежняя версия
   уходит в _versions/ с датой. Ссылка в таблице при этом не меняется никогда.

4. Повторный запуск не платит и не грузит дважды: сравнивается SHA256 с метаданными объекта.

Запуск:
  python publish_reports.py --dry-run          # только посчитать ключи и ссылки
  python publish_reports.py                    # загрузить (нужны ключи доступа)
  python publish_reports.py --period 9мес --year 2026

Переменные окружения:
  S3_ENDPOINT      по умолчанию https://s3.cloud.ru
  S3_BUCKET        имя бакета
  S3_PUBLIC_BASE   база публичных ссылок: https://global.s3.cloud.ru/<бакет>
                   или https://<доменное_имя>.s3.cloud.ru
  S3_ACCESS_KEY / S3_SECRET_KEY
"""
import argparse, csv, hashlib, json, os, re, sys
from datetime import date

# Скрипт запускают и из WorkBuddy, и руками из консоли — там может быть другой
# интерпретатор без boto3. Ставим по факту отсутствия, один раз, без интерактива.
try:
    import boto3
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--quiet',
                           'boto3>=1.34'])
    import boto3

HERE = os.path.dirname(os.path.abspath(__file__))
DL = r'D:\data-scraping\downloads'
EXTRACTED = os.path.join(HERE, 'extracted')
OUT_CSV = os.path.join(HERE, '_links.csv')   # к имени добавляются период и год
PREFIX = 'vdo'
SALT_FILE = os.path.join(HERE, '.s3_salt')


def key_salt():
    """Случайный сегмент пути — «соль» ключа.

    Публичный доступ означает, что ссылку может открыть любой, кто её знает. Ключ из ИНН и
    транслита при этом предсказуем: перебрать 10-значные ИНН по слагу несложно. Один общий
    случайный сегмент убирает эту возможность и при этом НЕ мешает выводить ключ из имени
    файла — соль известна скрипту, а не тому, кто подбирает. Сегмент один на все отчёты,
    поэтому 300 файлов не превращаются в 300 несвязанных путей.
    """
    env = os.environ.get('S3_KEY_SALT', '').strip()
    if env:
        return env
    if os.path.exists(SALT_FILE):
        return open(SALT_FILE, encoding='utf-8').read().strip()
    import secrets
    salt = secrets.token_hex(6)
    open(SALT_FILE, 'w', encoding='utf-8').write(salt)
    return salt

# ГОСТ-подобная транслитерация: только для ключей, читаемость важнее обратимости
TRANS = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh',
    'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
    'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu',
    'я': 'ya',
}


PERIOD_SLUG = {'9мес': '9m', '6мес': '6m', '3мес': '3m', '12мес': '12m', 'год': 'y'}
# Обратное соответствие: в консоли удобнее писать латиницей (9m), а файлы называются
# «_9мес_2026.pdf». Принимаем оба написания.
PERIOD_FILE = {'9m': '9мес', '6m': '6мес', '3m': '3мес', '12m': '12мес', 'y': 'год'}


def period_slug(period):
    """Период латиницей: кириллица в ключе превращается в процентную кашу в ссылке."""
    return PERIOD_SLUG.get(period, slugify(period))


def slugify(name):
    s = name.lower().replace('(', ' ').replace(')', ' ')
    s = ''.join(TRANS.get(ch, ch) for ch in s)
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s or 'emitter'


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def inn_of(stem):
    """ИНН из артефакта, если он там есть."""
    p = os.path.join(EXTRACTED, stem + '.json')
    if not os.path.exists(p):
        return None
    try:
        d = json.load(open(p, encoding='utf-8'))
    except Exception:
        return None
    inn = ((d.get('company') or {}).get('inn') or '').strip()
    return inn if re.fullmatch(r'\d{10}|\d{12}', inn or '') else None


def plan(period, year):
    """Список записей: что грузить и какая будет ссылка."""
    period = PERIOD_FILE.get(period, period)
    rx = re.compile(rf'^(.*)_{period}_{year}\.pdf$', re.I)
    rows = []
    for name in sorted(os.listdir(DL)):
        m = rx.match(name)
        if not m:
            continue
        stem = name[:-4]
        path = os.path.join(DL, name)
        slug = slugify(m.group(1))
        inn = inn_of(stem)
        base = f'{inn}_{slug}' if inn else slug
        per = period_slug(period)
        key = f'{PREFIX}/{key_salt()}/{per}/{year}/{base}_{per}_{year}.pdf'
        rows.append(dict(file=name, stem=stem, inn=inn or '', slug=slug, key=key,
                         size=os.path.getsize(path), sha256=sha256(path),
                         local=path))
    # коллизии ключей (одинаковый транслит у разных названий) — развести хешем имени
    seen = {}
    for r in rows:
        if r['key'] in seen:
            h = hashlib.sha1(r['stem'].encode('utf-8')).hexdigest()[:6]
            r['key'] = r['key'].replace('.pdf', f'_{h}.pdf')
        seen[r['key']] = True
    return rows


CREDS_FILES = (os.path.join(HERE, '.s3_creds.txt'), os.path.join(HERE, '.s3_creds'))


def load_creds():
    """Ключи и параметры подключения: окружение или локальный файл KEY=VALUE.

    Особенность Cloud.ru Evolution: aws_access_key_id — СОСТАВНОЙ, вида
    `{tenant_id}:{access_key}`. Если передать только access_key, подпись не сойдётся и
    хранилище ответит SignatureDoesNotMatch — ошибка выглядит как «неверный секрет», хотя
    секрет верный. Поэтому tenant_id из файла склеивается с ключом здесь, один раз.

    Возвращает dict: access_key_id, secret, endpoint, region.
    """
    vals = {}
    for path in CREDS_FILES:
        if os.path.exists(path):
            for line in open(path, encoding='utf-8'):
                if '=' in line and not line.strip().startswith('#'):
                    k, v = line.split('=', 1)
                    vals[k.strip()] = v.strip().strip('"').strip("'")
            break
    for k in ('S3_ACCESS_KEY', 'S3_SECRET_KEY', 'S3_ENDPOINT', 'S3_REGION', 'tenant_id'):
        if os.environ.get(k):
            vals[k] = os.environ[k]
    key = vals.get('S3_ACCESS_KEY') or ''
    tenant = vals.get('tenant_id') or vals.get('TENANT_ID') or ''
    if key and tenant and ':' not in key:
        key = f'{tenant}:{key}'
    return dict(access_key_id=key or None,
                secret=vals.get('S3_SECRET_KEY') or None,
                endpoint=vals.get('S3_ENDPOINT') or 'https://s3.cloud.ru',
                region=vals.get('S3_REGION') or 'ru-central-1')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--period', default='9мес')
    ap.add_argument('--year', default='2026')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    # Класс хранения задан жёстко и не выносится в флаг. Причина: S3 не меняет класс
    # у существующего объекта, а publish_reports.py при совпадении sha256 вообще
    # пропускает загрузку — то есть флаг молча действовал бы только на новые файлы.
    # Настройка, которая иногда не делает ничего, опаснее её отсутствия.
    # SINGLE пробовали 21.11.2026: первая загрузка шла очень медленно, панель
    # рекомендовала одну зону. Причина оказалась в VPN на рабочей машине, а не в
    # платформе; STANDARD бесплатен до 15 ГБ и не берёт плату за извлечение, поэтому
    # для PDF, на которые ссылается опубликованный свод, он единственный осмысленный.
    # Перевести уже выгруженные объекты — fix_storage_class.py.
    STORAGE_CLASS = 'STANDARD'

    creds = load_creds()
    endpoint = creds['endpoint']
    bucket = os.environ.get('S3_BUCKET', 'rsbu')
    public_base = os.environ.get('S3_PUBLIC_BASE', 'https://rsbu.s3.cloud.ru')
    rows = plan(args.period, args.year)
    print(f'файлов к публикации: {len(rows)}, объём '
          f'{sum(r["size"] for r in rows) / 2**30:.2f} ГБ')

    if not args.dry_run:
        if not (bucket and public_base):
            sys.exit('нужны S3_BUCKET и S3_PUBLIC_BASE (или запустите с --dry-run)')
        try:
            import boto3
        except ImportError:
            sys.exit('нет boto3: pip install boto3')

    s3 = None
    if not args.dry_run:
        if not (creds['access_key_id'] and creds['secret']):
            sys.exit('нет ключей: задайте S3_ACCESS_KEY/S3_SECRET_KEY или создайте .s3_creds.txt')
        # Таймаут чтения по умолчанию (60 с) рвёт загрузку крупных сканов: один файл
        # уронил весь прогон на 4-м из 91. Поднимаем таймауты и включаем адаптивные
        # повторы — сеть до хранилища нестабильна на длинных телах запросов.
        from botocore.config import Config
        cfg = Config(read_timeout=300, connect_timeout=30,
                     retries={'max_attempts': 5, 'mode': 'adaptive'},
                     max_pool_connections=8)
        s3 = boto3.client('s3', endpoint_url=endpoint,
                          region_name=creds['region'], config=cfg,
                          aws_access_key_id=creds['access_key_id'],
                          aws_secret_access_key=creds['secret'])

    out, uploaded, skipped, versioned = [], 0, 0, 0
    for r in rows:
        url = f'{public_base.rstrip("/")}/{r["key"]}'
        status = 'planned'
        if s3:
            # Ошибка одного файла не должна обрывать прогон: сеть до хранилища рвёт
            # длинные тела. Сбой фиксируется в статусе и в итоговой сводке, файл
            # остаётся непокрытым — его видно и можно повторить.
            try:
                head = None
                try:
                    head = s3.head_object(Bucket=bucket, Key=r['key'])
                except Exception:
                    head = None
                if head and (head.get('Metadata') or {}).get('sha256') == r['sha256']:
                    status = 'unchanged'
                    skipped += 1
                else:
                    if head:
                        # файл уже был и отличается — прежнюю версию сохраняем
                        vkey = r['key'].replace('.pdf', f'_{date.today().isoformat()}.pdf')
                        vkey = vkey.replace(f'/{period_slug(args.period)}/{args.year}/',
                                            f'/{period_slug(args.period)}/{args.year}/_versions/')
                        s3.copy_object(Bucket=bucket, Key=vkey,
                                       CopySource={'Bucket': bucket, 'Key': r['key']})
                        versioned += 1
                        status = 'replaced'
                    else:
                        status = 'uploaded'
                    s3.upload_file(r['local'], bucket, r['key'],
                                   ExtraArgs={'ContentType': 'application/pdf',
                                              'StorageClass': STORAGE_CLASS,
                                              'Metadata': {'sha256': r['sha256'],
                                                           'source': 'e-disclosure'}})
                    uploaded += 1
            except Exception as e:
                status = 'error: ' + type(e).__name__
                print(f'  ОШИБКА {r["file"]}: {type(e).__name__} {str(e)[:120]}', flush=True)
        out.append(dict(файл=r['file'], инн=r['inn'], ключ=r['key'], ссылка=url,
                        байт=r['size'], sha256=r['sha256'], статус=status))

    # Имя с периодом и годом: свод читает оба года сразу, и файлы не должны затирать друг друга
    out_csv = OUT_CSV.replace('.csv', f'_{period_slug(args.period)}_{args.year}.csv')
    with open(out_csv, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()), delimiter=';')
        w.writeheader()
        w.writerows(out)
    print(f'загружено {uploaded}, без изменений {skipped}, заменено {versioned}')
    print(f'-> {out_csv}')
    print('пример ссылки:', out[0]['ссылка'] if out else '—')


if __name__ == '__main__':
    main()