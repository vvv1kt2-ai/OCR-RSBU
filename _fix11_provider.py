# -*- coding: utf-8 -*-
r"""Проверка plusvibe: доступен ли ключ, какая модель на каждой роли, что с ценой.

Вызовов LLM нет: только чтение профилей и проверка наличия ключа.
"""
import os, sys

sys.path.insert(0, r'D:\models')
import providers as PR

print('переменная выбора поставщика: %s' % PR.ENV_VAR)
print('в окружении: %r' % os.environ.get(PR.ENV_VAR))
print('значение по умолчанию в коде: %r' % PR.DEFAULT_PROVIDER)
print('устаревшее имя: %r' % PR.LEGACY_PROVIDER)
print()

for name in ('plusvibe',):
    try:
        p = PR.active(name)
    except Exception as e:
        print('%s: НЕДОСТУПЕН — %s' % (name, str(e)[:200])); continue
    print('профиль %r:' % p.name)
    print('   адрес: %s' % p.chat_url)
    print('   ключ: имя переменной %r' % p.key_name)
    try:
        k = PR.load_key(p)
        print('   ключ найден: длина %d, sha1 %s'
              % (len(k), __import__('hashlib').sha1(k.encode()).hexdigest()[:8]))
    except Exception as e:
        print('   ключ НЕ найден: %s' % str(e)[:160])
    print('   суффикс кэша: %r' % p.cache_suffix)
    print('   роли:')
    for role, model in sorted((p.roles or {}).items()):
        print('      %-8s %r  (длина имени %d)' % (role, model, len(model)))
    print('   цены (₽ за 1M вход/выход):')
    for m, pr in sorted((p.prices or {}).items()):
        print('      %-34s %s / %s' % (m, pr[0], pr[1]))
    print()

# что было в кэшах plusvibe и polza
PAGES = r'D:\models\extracted\pages'
import os as _os
pv = [f for f in _os.listdir(PAGES) if f.endswith('_pv.json')]
nopv = [f for f in _os.listdir(PAGES) if f.endswith('.json') and not f.endswith('_pv.json')]
print('файлов кэша с суффиксом _pv (plusvibe): %d' % len(pv))
print('файлов кэша без суффикса (polza):        %d' % len(nopv))
