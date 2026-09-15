# -*- coding: utf-8 -*-
r"""Tests for the provider profile and the pure request builder (ticket 02).

The provider stops being a property of the code and becomes a profile. Nothing here
touches the network or spends money: the request builder is pure, and the cache key is
built from a real open PDF without calling anything.

Run:  python D:\models\tests\test_providers.py
"""
import os, sys, json, warnings, tempfile

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


def raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def _msg(fn):
    """текст исключения — чтобы проверять, что ошибка объясняет себя"""
    try:
        fn()
    except Exception as e:
        return str(e)
    return ''


print('--- реестр профилей ---')
check('Polza зарегистрирован', 'polza' in PR.PROFILES)
check('активный профиль по умолчанию — PlusVibe', PR.active().name == 'plusvibe')
check('активный профиль берётся из переменной окружения',
      PR.active('polza').name == 'polza')
check('неизвестный профиль даёт понятную ошибку',
      raises(lambda: PR.active('нетакого'), KeyError))
check('в ошибке перечислены известные профили',
      'polza' in _msg(lambda: PR.active('нетакого')))

print('--- профиль описывает поставщика целиком ---')
p = PR.active()
p_polza = PR.active('polza')
check('есть адрес точки чата', bool(p.chat_url))
check('есть имя ключа в файле учётных данных', p_polza.key_name == 'POLZA_API_KEY')
check('есть все три роли', sorted(p.roles) == ['detect', 'esc', 'main'])
check('есть таблица цен', len(p.prices) >= 3)
check('роли заполнены', all(p.roles[r] for r in ('detect', 'main', 'esc')))
check('адрес роли main непустой', bool(p.address('main')))
check('обращение к несуществующей роли даёт понятную ошибку',
      raises(lambda: p.address('нетакой'), KeyError))
check('метка кэша у Polza пуста (ключи прежние)', p_polza.cache_suffix() == '')
check('метка кэша у PlusVibe не пуста', p.cache_suffix() == 'pv')

print('--- сборка запроса чистая ---')
url, headers, body = PR.build_request(p, p.roles['main'], [{'role': 'user', 'content': 'x'}],
                                      'СЕКРЕТ')
check('возвращает адрес профиля', url == p.chat_url)
check('ключ попадает в заголовок', headers['Authorization'] == 'Bearer СЕКРЕТ')
check('заголовок типа содержимого на месте', headers['Content-Type'] == 'application/json')
obj = json.loads(body.decode())
check('тело содержит модель', obj['model'] == p.roles['main'])
check('тело содержит сообщения', obj['messages'] == [{'role': 'user', 'content': 'x'}])
check('дефолтная температура 0.1', obj['temperature'] == 0.1)
url2, h2, b2 = PR.build_request(p, p.roles['main'], [], 'К', temperature=0.5, max_tokens=7)
check('параметры доходят до тела', json.loads(b2.decode())['max_tokens'] == 7)
check('пустой адрес модели отвергается',
      raises(lambda: PR.build_request(p, '', [], 'К'), ValueError))
check('сборка не читает диск и не ходит в сеть',
      'urllib' not in json.dumps(str(PR.build_request.__code__.co_names)))

print('--- ключ ---')
check('ключ Polza читается', len(PR.load_key(p_polza)) > 10)
missing = PR.Profile('нетакого', 'https://x/y', 'НЕТ_ТАКОГО_КЛЮЧА',
                     {'detect': 'a', 'main': 'b', 'esc': 'c'}, {})
check('отсутствие ключа даёт понятную ошибку',
      raises(lambda: PR.load_key(missing), KeyError))
check('в ошибке назван искомый ключ',
      'НЕТ_ТАКОГО_КЛЮЧА' in _msg(lambda: PR.load_key(missing)))
check('в ошибке назван файл учётных данных',
      'credentials' in _msg(lambda: PR.load_key(missing)))

print('--- цена: молчаливого нуля быть не должно ---')
check('известная модель даёт цену', p.price_of(p.roles['main']) is not None)
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter('always')
    got = p.price_of('нетакой/модели-нет')
    check('неизвестная модель даёт None', got is None, got)
    check('и громкое предупреждение', len(w) == 1, [str(x.message) for x in w])
    check('предупреждение называет модель численно', 'sha1=' in str(w[0].message))
cost, src = PR.call_cost(p, p.roles['main'], 1_000_000, 1_000_000)
check('цена по таблице считается', cost > 0 and src == 'таблица профиля', (cost, src))
class H(dict):
    def get(self, k, d=None):
        return dict.get(self, k, d)
prof_hdr = PR.Profile('h', 'https://x', 'K', {'detect': 'a', 'main': 'b', 'esc': 'c'},
                      {p.roles['main']: (1.0, 2.0)}, cost_header='x-cost')
c2, s2 = PR.call_cost(prof_hdr, p.roles['main'], 1_000_000, 1_000_000, H({'x-cost': '3.5'}))
check('заголовок ответа важнее таблицы', c2 == 3.5 and s2 == 'заголовок ответа', (c2, s2))
c3, s3 = PR.call_cost(prof_hdr, p.roles['main'], 1_000_000, 1_000_000, H({}))
check('без заголовка считается по таблице', c3 == 3.0, (c3, s3))
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter('always')
    c4, s4 = PR.call_cost(prof_hdr, 'нетакой', 1_000_000, 1_000_000, H({}))
    check('неизвестная модель и без заголовка — предупреждение, а не тихий нуль',
          len(w) == 1 and c4 == 0.0 and s4 == 'неизвестно', (c4, s4, len(w)))

print('--- профили из JSON ---')
tmp = os.path.join(tempfile.gettempdir(), '_test_providers.json')
json.dump({'providers': {'тест': {
    'chat_url': 'https://example.test/v1/chat',
    'key_name': 'PLUSVIBE_API_KEY',
    'roles': {'detect': 'd-model', 'main': 'm-model', 'esc': 'e-model'},
    'prices': {'m-model': [1.5, 2.5]},
    'cache_tag': 'tv',
    'cost_header': 'x-cost'}}},
    open(tmp, 'w', encoding='utf-8'), ensure_ascii=False)
loaded = PR.load_profiles(tmp)
check('профиль читается из файла', 'тест' in loaded, sorted(loaded))
check('роли читаются', loaded['тест'].roles['main'] == 'm-model')
check('цены читаются кортежем', loaded['тест'].prices['m-model'] == (1.5, 2.5))
check('метка кэша читается', loaded['тест'].cache_suffix() == 'tv')
check('заголовок цены читается', loaded['тест'].cost_header == 'x-cost')
check('отсутствие файла профилей не ломает встроенные', PR.load_profiles(tmp + '.нет') == {})
bad = os.path.join(tempfile.gettempdir(), '_test_providers_bad.json')
open(bad, 'w', encoding='utf-8').write('{ это не json')
check('битый файл профилей даёт понятную ошибку',
      raises(lambda: PR.load_profiles(bad), ValueError))
empty = PR.Profile('пустой', 'https://x', 'K', {'detect': 'a', 'main': '', 'esc': 'c'}, {})
check('незаполненный адрес роли даёт понятную ошибку',
      raises(lambda: empty.address('main'), ValueError))
check('в ошибке сказано, что адрес надо вписать в файл профилей',
      'providers.json' in _msg(lambda: empty.address('main')))
nourl = PR.Profile('без-адреса', '', 'K', {'detect': 'a', 'main': 'b', 'esc': 'c'}, {})
PR.register(nourl)
check('профиль без адреса чата отвергается',
      raises(lambda: PR.active('без-адреса'), ValueError))
check('и ошибка называет незаполненное поле',
      'chat_url' in _msg(lambda: PR.active('без-адреса')))
norole = PR.Profile('без-ролей', 'https://x', 'K', {'main': 'b'}, {})
PR.register(norole)
check('профиль с неполными ролями отвергается',
      raises(lambda: PR.active('без-ролей'), ValueError))
check('и ошибка называет недостающие роли',
      'detect' in _msg(lambda: PR.active('без-ролей')))

print('--- имена ролей сохранены ---')
check('M_MAIN совпадает с ролью main профиля', P.M_MAIN == P.ACTIVE_PROFILE.roles['main'])
check('M_ESC совпадает с ролью esc профиля', P.M_ESC == P.ACTIVE_PROFILE.roles['esc'])
check('M_DETECT совпадает с ролью detect профиля',
      P.M_DETECT == P.ACTIVE_PROFILE.roles['detect'])
check('BASE совпадает с адресом профиля', P.BASE == P.ACTIVE_PROFILE.chat_url)

print('--- режим рассуждений ---')
# Измерено: 74% выходных токенов основной модели — рассуждения, которые конвейер
# выбрасывает, а платит за них по цене выхода. Параметр reasoning_effort снимает их
# целиком, не меняя текст ответа. Но у эскалации и детекции он не работает, поэтому
# настройка задаётся по ролям, а по умолчанию выключена: молчаливое включение
# изменило бы то, за что мы платим, без ведома того, кто запускает прогон.
def _body(prof, role):
    url, headers, body = PR.build_request(prof, prof.address(role), [{'role': 'user'}], 'k')
    return json.loads(body.decode('utf-8'))


plain = PR.Profile('обычный', 'https://x', 'K',
                   {'detect': 'd', 'main': 'm', 'esc': 'e'}, {'m': (1.0, 2.0)})
check('без настройки рассуждений параметр не отправляется',
      'reasoning_effort' not in _body(plain, 'main'),
      'молчаливое включение меняет счёт за прогон')
check('и тело запроса прежнее: модель, сообщения, температура, предел',
      sorted(_body(plain, 'main')) == ['max_tokens', 'messages', 'model', 'temperature'],
      sorted(_body(plain, 'main')))

tuned = PR.Profile('настроенный', 'https://x', 'K',
                   {'detect': 'd', 'main': 'm', 'esc': 'e'}, {'m': (1.0, 2.0)},
                   reasoning={'main': 'none'})
check('настройка рассуждений попадает в запрос основной модели',
      _body(tuned, 'main').get('reasoning_effort') == 'none')
check('эскалация не получает чужую настройку',
      'reasoning_effort' not in _body(tuned, 'esc'),
      'у эскалации параметр не работает — посылать его значит врать в настройках')
check('детекция тоже не получает', 'reasoning_effort' not in _body(tuned, 'detect'))
check('настройка не подменяет модель и сообщения',
      _body(tuned, 'main')['model'] == 'm' and _body(tuned, 'main')['messages'])

allroles = PR.Profile('все-роли', 'https://x', 'K',
                      {'detect': 'd', 'main': 'm', 'esc': 'e'}, {},
                      reasoning={'main': 'low', 'esc': 'low'})
check('настройка задаётся по каждой роли отдельно',
      _body(allroles, 'main')['reasoning_effort'] == 'low'
      and _body(allroles, 'esc')['reasoning_effort'] == 'low'
      and 'reasoning_effort' not in _body(allroles, 'detect'))

# файл профилей должен уметь то же самое, иначе настройка недоступна без правки кода
rj = os.path.join(tempfile.gettempdir(), '_test_providers_reason.json')
open(rj, 'w', encoding='utf-8').write(json.dumps({'providers': {'р': {
    'chat_url': 'https://x', 'key_name': 'K',
    'roles': {'detect': 'd', 'main': 'm', 'esc': 'e'},
    'prices': {'m': [1.0, 2.0]}, 'reasoning': {'main': 'none'}}}}, ensure_ascii=False))
rl = PR.load_profiles(rj)['р']
check('файл профилей задаёт режим рассуждений',
      _body(rl, 'main').get('reasoning_effort') == 'none')
check('и не выдумывает его там, где не задан', 'reasoning_effort' not in _body(rl, 'esc'))
open(rj, 'w', encoding='utf-8').write(json.dumps({'providers': {'р': {
    'chat_url': 'https://x', 'key_name': 'K',
    'roles': {'detect': 'd', 'main': 'm', 'esc': 'e'},
    'prices': {'m': [1.0, 2.0]}}}}, ensure_ascii=False))
check('отсутствие поля в файле читается как «выключено»',
      'reasoning_effort' not in _body(PR.load_profiles(rj)['р'], 'main'))

print('--- включение переменной окружения ---')
os.environ['PILOT_REASONING'] = 'main=none'
envprof = PR.Profile('с-переменной', 'https://x', 'K',
                     {'detect': 'd', 'main': 'm', 'esc': 'e'}, {})
check('переменная окружения включает режим без правки файла',
      _body(envprof, 'main').get('reasoning_effort') == 'none')
check('переменная не задевает роли, которых в ней нет',
      'reasoning_effort' not in _body(envprof, 'esc'))
os.environ['PILOT_REASONING'] = 'main=none,esc=low'
check('в переменной можно перечислить несколько ролей',
      _body(envprof, 'esc').get('reasoning_effort') == 'low')
os.environ['PILOT_REASONING'] = 'мусор без знака равенства'
check('мусор в переменной не роняет сборку запроса',
      'reasoning_effort' not in _body(envprof, 'main'))
del os.environ['PILOT_REASONING']
check('без переменной снова ничего не отправляется',
      'reasoning_effort' not in _body(envprof, 'main'))
# Режим рассуждений не меняет то, что мы читаем со страницы, поэтому в ключ кэша он
# попадать не должен: иначе включение режима оплатило бы повторную транскрипцию всего.
_quiet = PR.Profile('т', 'https://x', 'K', {}, {}, cache_tag='pv')
_loud = PR.Profile('т', 'https://x', 'K', {}, {}, cache_tag='pv',
                   reasoning={'main': 'none'})
check('настройка не попадает в метку кэша: режим не меняет, что мы читаем со страницы',
      _quiet.cache_suffix() == _loud.cache_suffix() == 'pv',
      (_quiet.cache_suffix(), _loud.cache_suffix()))

print()
print('пройдено %d, провалено %d' % (len(PASS), len(FAIL)))
if FAIL:
    print('провалы: ' + ', '.join(FAIL))
sys.exit(1 if FAIL else 0)
