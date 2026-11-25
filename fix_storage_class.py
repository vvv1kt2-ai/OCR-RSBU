# -*- coding: utf-8 -*-
r"""Приведение класса хранения объектов бакета к нужному (по умолчанию STANDARD).

Зачем отдельная утилита. В S3 класс хранения нельзя «переключить» у существующего объекта —
он задаётся при записи. Меняют копированием объекта на себя с другим классом. При этом:

  * ключ (и значит публичная ссылка) НЕ меняется — копия кладётся на то же место;
  * без `MetadataDirective=REPLACE` хранилище откажет: «copy request is illegal because it is
    trying to copy an object to itself without changing the object's metadata»;
  * с `REPLACE` метаданные НЕ копируются автоматически — их надо передать заново, иначе
    пропадёт `sha256`, по которому publish_reports.py понимает, что файл уже загружен, и
    следующий прогон перезальёт всё заново. ContentType тоже передаётся заново, иначе PDF
    начнёт отдаваться как application/octet-stream.

Запуск:
  python fix_storage_class.py --dry-run
  python fix_storage_class.py
  python fix_storage_class.py --only avtoban avtoassistans avtomoe-opt

Цель задана жёстко — STANDARD. Архивные классы (COLD, ICE) для этих файлов не годятся:
на них ссылается опубликованный свод, а извлечение из архива платное и с задержкой до
нескольких часов — ссылка формально работает, а человек ждёт. SINGLE пробовали 21.11.2026
как временную меру из-за медленной загрузки; причина была в VPN на рабочей машине, а не
в платформе. Поэтому утилита только возвращает объекты в STANDARD.
"""
import argparse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PREFIX = 'vdo/'
TARGET = 'STANDARD'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='*', default=None,
                    help='подстроки ключей; без них обрабатываются все объекты префикса')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    import importlib.util
    spec = importlib.util.spec_from_file_location('pub', os.path.join(HERE, 'publish_reports.py'))
    pub = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pub)

    import boto3
    from botocore.config import Config
    c = pub.load_creds()
    s3 = boto3.client('s3', endpoint_url=c['endpoint'], region_name=c['region'],
                      config=Config(read_timeout=300, retries={'max_attempts': 5,
                                                              'mode': 'adaptive'}),
                      aws_access_key_id=c['access_key_id'],
                      aws_secret_access_key=c['secret'])
    bucket = os.environ.get('S3_BUCKET', 'rsbu')

    todo = []
    for page in s3.get_paginator('list_objects_v2').paginate(Bucket=bucket, Prefix=PREFIX):
        for o in page.get('Contents', []):
            cls = o.get('StorageClass') or 'STANDARD'
            if cls == TARGET:
                continue
            if args.only and not any(s in o['Key'] for s in args.only):
                continue
            todo.append((o['Key'], cls, o['Size']))

    print(f'к переводу в {TARGET}: {len(todo)} объектов')
    for k, cls, size in todo:
        print(f'  {cls:<8} {size / 2**20:6.2f} МБ  {k}')

    if args.dry_run or not todo:
        return

    done = failed = 0
    for k, cls, _size in todo:
        try:
            head = s3.head_object(Bucket=bucket, Key=k)
            meta = head.get('Metadata') or {}
            ctype = head.get('ContentType') or 'application/pdf'
            s3.copy_object(Bucket=bucket, Key=k,
                           CopySource={'Bucket': bucket, 'Key': k},
                           StorageClass=TARGET,
                           MetadataDirective='REPLACE',
                           ContentType=ctype,
                           Metadata=meta)
            now = (s3.head_object(Bucket=bucket, Key=k).get('StorageClass') or 'STANDARD')
            ok = (now == TARGET)
            print(f'  {"OK  " if ok else "НЕТ "} {cls} -> {now}  {k}', flush=True)
            done += ok
            failed += (not ok)
        except Exception as e:
            failed += 1
            print(f'  ОШИБКА {k}: {type(e).__name__} {str(e)[:120]}', flush=True)

    print(f'\nпереведено: {done}, ошибок: {failed}')


if __name__ == '__main__':
    main()