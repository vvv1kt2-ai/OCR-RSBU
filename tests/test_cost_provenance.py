# -*- coding: utf-8 -*-
r"""Tests for cost accounting and provenance (ticket 05).

The cost report must not depend on a stale price list, and a document result must say
which provider produced it. No network, no LLM calls: the header path and the
table path are exercised through the pure functions.

Run:  python D:\models\tests\test_cost_provenance.py
"""
import os, sys, json, warnings

sys.path.insert(0, r'D:\models')
import pipeline as P          # importing it puts D:\models\pylibs on sys.path
import providers as PR

PASS, FAIL, LOG = [], [], []
_console = print


def print(*a, **k):
    LOG.append(' '.join(str(x) for x in a))
    _console(*a, **k)


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('  %-4s %s%s' % ('ok' if cond else 'FAIL', name,
                           ('  <- ' + str(detail)) if detail and not cond else ''))


class H(dict):
    """a stand-in for the response headers object"""
    def get(self, k, d=None):
        return dict.get(self, k, d)


prof = PR.Profile('тест', 'https://x/v1/chat', 'K',
                  {'detect': 'd', 'main': 'm', 'esc': 'e'},
                  {'m': (10.0, 20.0)}, cost_header='x-cost')

print('--- цена: заголовок ответа ---')
rub, src = PR.call_cost(prof, 'm', 1_000_000, 0, H({'x-cost': '1.25'}))
check('заголовок прочитан', rub == 1.25 and src == 'заголовок ответа', (rub, src))
rub, src = PR.call_cost(prof, 'm', 0, 1_000_000, H({'x-cost': '7'}))
check('заголовок важнее таблицы и при нулевом входе', rub == 7.0, rub)

print('--- цена: таблица профиля ---')
rub, src = PR.call_cost(prof, 'm', 1_000_000, 1_000_000, H({}))
check('без заголовка считается по таблице', rub == 30.0 and src == 'таблица профиля',
      (rub, src))
rub, src = PR.call_cost(prof, 'm', 500_000, 250_000, None)
check('без объекта заголовков тоже считается', rub == 5.0 + 5.0, rub)

print('--- цена: заголовок есть, но пустой или битый ---')
rub, src = PR.call_cost(prof, 'm', 1_000_000, 0, H({'x-cost': ''}))
check('пустой заголовок откатывается на таблицу', rub == 10.0 and 'таблица' in src,
      (rub, src))
rub, src = PR.call_cost(prof, 'm', 1_000_000, 0, H({'x-cost': 'не число'}))
check('нечисловой заголовок откатывается на таблицу', rub == 10.0 and 'таблица' in src,
      (rub, src))

print('--- цена: неизвестная модель не даёт тихий нуль ---')
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter('always')
    rub, src = PR.call_cost(prof, 'нетакой', 1_000_000, 1_000_000, H({}))
    check('стоимость нулевая, но помечена как неизвестная',
          rub == 0.0 and src == 'неизвестно', (rub, src))
    check('и выдано предупреждение', len(w) == 1, len(w))
    check('предупреждение объясняет последствие',
          'отчёт' in str(w[0].message) or 'стоимость' in str(w[0].message),
          str(w[0].message))
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter('always')
    rub, src = PR.call_cost(prof, 'нетакой', 1_000_000, 0, H({'x-cost': '2'}))
    check('но заголовок спасает даже неизвестную модель', rub == 2.0 and len(w) == 0,
          (rub, src, len(w)))

print('--- профиль без заголовка стоимости ---')
plain = PR.Profile('без-заголовка', 'https://x', 'K',
                   {'detect': 'd', 'main': 'm', 'esc': 'e'}, {'m': (1.0, 2.0)})
check('профиль без заголовка не падает', PR.cost_from_headers(plain, H({'x-cost': '5'})) is None)
rub, src = PR.call_cost(plain, 'm', 1_000_000, 1_000_000, H({'x-cost': '5'}))
check('и считает по таблице, игнорируя чужой заголовок', rub == 3.0 and 'таблица' in src,
      (rub, src))

print('--- происхождение в результате ---')
src = json.load(open(os.path.join(P.OUTDIR, 'ТГК-14_6мес_2025.json'), encoding='utf-8'))
check('в результате записан поставщик', 'provider' in src['source'], sorted(src['source']))
check('поставщик непустой', bool(src['source']['provider']))
check('поле модели сохранено рядом', 'ocr_model' in src['source'], sorted(src['source']))
# The artifact must say who made it, and that name must resolve — but it must NOT be
# compared with the currently active profile: the artifacts on disk were made by Polza
# while PlusVibe is now the default, and an artifact cannot retroactively change author
# when the default moves. Coupling the two only passed while they happened to coincide.
check('записанный поставщик — известный профиль',
      src['source']['provider'] in PR.PROFILES,
      (src['source']['provider'], sorted(PR.PROFILES)))
check('файл и число страниц по-прежнему на месте',
      src['source']['file'] and src['source']['pages_total'] > 0)

print('--- манифест ---')
man_path = os.path.join(P.OUTDIR, '_manifest.json')
if os.path.exists(man_path):
    man = json.load(open(man_path, encoding='utf-8'))
    check('в манифесте есть поставщик', 'provider' in man)
    check('в манифесте есть стоимость прогона', 'cost_rub' in man.get('usage', {}))
    check('в манифесте есть число вызовов', 'calls' in man.get('usage', {}))
    check('пояснение к стоимости записано', 'usage_note' in man)
else:
    check('манифест существует', False, man_path)

print()
print('пройдено %d, провалено %d' % (len(PASS), len(FAIL)))
if FAIL:
    print('провалы: ' + ', '.join(FAIL))
sys.exit(1 if FAIL else 0)
