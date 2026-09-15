# -*- coding: utf-8 -*-
r"""Кто именно прочитал страницу ТГК-14_6мес_2025 стр.3 — модель или разрешение?

На стр.3 четыре транскрипта: два при 200 dpi (оба с ошибочным 11081647) и два при
300 dpi (один с верным 11061647, другой с ошибочным). Значит различие может быть
не в разрешении, а в МОДЕЛИ. Имя файла кэша содержит метку модели и поставщика:
{stem}_p{стр}_{dpi}_{метка модели}{инфикс поставщика}_{отпечаток}.md
"""
import io, os, re, sys, hashlib

sys.path.insert(0, r'D:\models')
import providers as PR

PAGES = r'D:\models\extracted\pages'
STEM = 'ТГК-14_6мес_2025'
OLD, NEW = '11081647', '11061647'


def norm(t):
    return re.sub(r'(?<=\d)[\s\u00a0](?=\d)', '', t or '')


pv = PR.active('plusvibe')
role_of = {}
for role in ('detect', 'main', 'esc'):
    m = pv.roles.get(role)
    if m:
        role_of[hashlib.sha1(m.encode()).hexdigest()[:10]] = (role, m)

print('=== роли в текущем профиле ===')
for role in ('detect', 'main', 'esc'):
    m = pv.roles.get(role) or ''
    print('  %-7s len=%-3d sha1=%s ords=%s'
          % (role, len(m), hashlib.sha1(m.encode()).hexdigest()[:10],
             ','.join(str(ord(c)) for c in m[:4])))
print()
print('=== транскрипты стр.3 ===')
pat = re.compile(r'^%s_p3_(\d+)_(.+)\.md$' % re.escape(STEM))
rows = []
for f in sorted(os.listdir(PAGES)):
    m = pat.match(f)
    if not m:
        continue
    dpi = int(m.group(1))
    rest = m.group(2)
    t = norm(io.open(os.path.join(PAGES, f), encoding='utf-8').read())
    rows.append((dpi, rest, OLD in t, NEW in t, len(t), f))
for dpi, rest, has_old, has_new, n, f in sorted(rows):
    tag = rest.split('_')[0] if rest else '?'
    print('  %3d dpi  метка=%-22s %5d знаков  ошибочное:%-4s верное:%-4s'
          % (dpi, tag[:22], n, 'ЕСТЬ' if has_old else '-', 'ЕСТЬ' if has_new else '-'))
    print('      файл: %s' % f)
print()
print('ВЫВОД: если верное значение есть только у одного из ДВУХ транскриптов 300 dpi,')
print('а оба транскрипта 200 dpi ошибочны, то причина — РАЗНЫЕ МОДЕЛИ, не разрешение.')
