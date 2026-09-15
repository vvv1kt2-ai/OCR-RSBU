# -*- coding: utf-8 -*-
r"""Почему «детекция 0.22 ₽» расходится с замером 0.03 ₽ за вызов.

Проверяю по _pv_usage.json: какая модель обслуживала роль detect в том прогоне.
"""
import io, json, sys

sys.path.insert(0, r'D:\models')
import providers as PR

d = json.load(io.open(r'D:\models\_pv_usage.json', encoding='utf-8'))
if isinstance(d, list):
    print('файл — список из %d записей; поля первой:' % len(d))
    if d:
        print('  %s' % json.dumps(d[0], ensure_ascii=False)[:300])
    # собираю роли
    roles = {}
    for rec in d:
        if not isinstance(rec, dict):
            continue
        r = rec.get('role') or rec.get('stage')
        if r:
            roles.setdefault(r, {'calls': 0, 'pt': 0, 'ct': 0, 'model': rec.get('model')})
            roles[r]['calls'] += 1
            roles[r]['pt'] += rec.get('pt') or rec.get('prompt_tokens') or 0
            roles[r]['ct'] += rec.get('ct') or rec.get('completion_tokens') or 0
    print()
    print('по ролям:')
    for k, v in sorted(roles.items()):
        print('  %-8s модель=%r вызовов=%d pt=%d ct=%d'
              % (k, v['model'], v['calls'], v['pt'], v['ct']))
    d = {'roles': roles}
roles = d.get('roles') or d.get('by_role') or {}
if isinstance(roles, dict):
    for k, v in roles.items():
        if isinstance(v, dict):
            print('  роль %-8s модель=%r pt=%s ct=%s calls=%s'
                  % (k, v.get('model'), v.get('pt'), v.get('ct'), v.get('calls')))
        else:
            print('  роль %-8s %r' % (k, v))
print()
print('роли активного профиля polza (встроенный):')
p = PR.active()
for k, v in (p.roles or {}).items():
    print('  %-8s %r' % (k, v))
print()
print('роли профиля plusvibe (providers.json):')
try:
    pv = PR.active('plusvibe')
    for k, v in (pv.roles or {}).items():
        print('  %-8s %r' % (k, v))
except Exception as e:
    print('  не удалось: %s' % e)
