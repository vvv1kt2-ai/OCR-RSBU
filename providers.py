# -*- coding: utf-8 -*-
r"""Поставщик ИИ как профиль, а не как свойство кода.

Раньше адрес точки чата, имя ключа, три роли моделей и таблица цен были вписаны в
`pipeline.py`. Теперь это профиль: у Polza он встроенный (его адреса моделей уже
лежат в коде и менять их нельзя), у остальных поставщиков — во внешнем JSON-файле
`providers.json`.

Зачем JSON для новых поставщиков: идентификаторы моделей PlusVibe в этой среде при
выводе команд и чтении файлов подменяются пустой строкой. Python читает настоящие
значения, слепнет только вывод, поэтому вписать их в исходный код нельзя — их
невозможно ни проверить глазами, ни отредактировать. В JSON-файл их кладёт скрипт,
а сверяются они численно (длина и sha1), см. `verify_profiles.py`.

Активный профиль выбирается переменной окружения PILOT_PROVIDER. По умолчанию —
PlusVibe: это выбранный поставщик целевых прогонов, и его цены в таблице polza выше
в двенадцать раз, поэтому молчаливый уход на Polza — это не «безопасный откат», а
двенадцатикратный перерасход. Вернуться на Polza стоит одной переменной.
"""
import io, os, re, json, hashlib, warnings

CRED = r'C:\Users\1\.dsh\.credentials.yaml'
PROFILES_JSON = os.environ.get('PILOT_PROFILES', r'D:\models\providers.json')
ENV_VAR = 'PILOT_PROVIDER'
REASONING_VAR = 'PILOT_REASONING'
DEFAULT_PROVIDER = 'plusvibe'

# Режим рассуждений: параметр `reasoning_effort`, который поставщик принимает, а
# модель может и проигнорировать. Измерено на PlusVibe: у основной модели он снимает
# 74% выходных токенов, которые конвейер всё равно выбрасывает (они оплачиваются как
# выходные), а у эскалации и детекции не действует вовсе. Поэтому задаётся по ролям
# и по умолчанию не задан ни для кого.
REASONING_ROLES = ('detect', 'main', 'esc')

# Поставщик, чьи ключи кэша уже лежат на диске в прежнем виде. Для него метка
# поставщика в имя файла НЕ добавляется, иначе переключение профиля вызвало бы
# повторную транскрипцию всех страниц и повторную оплату около 986 ₽.
LEGACY_PROVIDER = 'polza'


class UnknownModel(Warning):
    """Модель, которой нет в таблице цен профиля."""


class Profile(object):
    """Поставщик целиком: куда обращаться, чем платить, какие модели за что отвечают."""

    def __init__(self, name, chat_url, key_name, roles, prices,
                 cache_tag='', cost_header=None, note='', reasoning=None):
        self.name = name
        self.chat_url = chat_url
        self.key_name = key_name
        self.roles = dict(roles)
        self.prices = dict(prices)
        self.cache_tag = cache_tag
        self.cost_header = cost_header
        self.note = note
        self.reasoning = dict(reasoning or {})

    # ---- роли -------------------------------------------------------------
    def address(self, role):
        """адрес модели для роли: 'main' | 'detect' | 'esc'"""
        try:
            addr = self.roles[role]
        except KeyError:
            raise KeyError(f'в профиле {self.name!r} нет роли {role!r}; '
                           f'есть роли: {sorted(self.roles)}')
        if not addr:
            raise ValueError(f'в профиле {self.name!r} роль {role!r} не заполнена — '
                             f'впишите адрес модели в {PROFILES_JSON}')
        return addr

    # ---- цена -------------------------------------------------------------
    def price_of(self, model):
        """(вход, выход) RUB/1M. Неизвестная модель — громкое предупреждение.

        Молчаливый нуль здесь опаснее ошибки: он незаметно занижает отчёт о
        стоимости, и прогон выглядит дешевле, чем был.
        """
        if model in self.prices:
            return self.prices[model]
        warnings.warn(f'цена модели неизвестна профилю {self.name!r}: '
                      f'len={len(str(model))} sha1={hashlib.sha1(str(model).encode()).hexdigest()[:10]}. '
                      f'Стоимость этого вызова в отчёт не попадёт — добавьте модель в таблицу цен '
                      f'профиля.', UnknownModel, stacklevel=2)
        return None

    # ---- режим рассуждений ------------------------------------------------
    def effort_for(self, model):
        """`reasoning_effort` для этой модели, или '' — если режим не задан.

        Ищется по роли, которой принадлежит модель: настройка задаётся ролью, потому
        что отклик на параметр у ролей разный. Роль, которой модель не принадлежит,
        настройки не получает — иначе эскалация молча унаследовала бы чужой режим.

        Переменная окружения PILOT_REASONING перекрывает файл профилей: включить и
        выключить режим нужно уметь одной строкой, не правя файл.
        """
        env = os.environ.get(REASONING_VAR)
        if env is not None:
            return _parse_reasoning(env).get(self._role_of(model), '')
        return self.reasoning.get(self._role_of(model), '')

    def _role_of(self, model):
        """какая роль принадлежит этому адресу; '' — если ничья"""
        for role in REASONING_ROLES:
            if self.roles.get(role) and self.roles[role] == model:
                return role
        return ''

    # ---- ключ кэша --------------------------------------------------------
    def cache_suffix(self):
        """что добавляется в имя файла кэша; у прежнего поставщика — ничего"""
        if self.name == LEGACY_PROVIDER:
            return ''
        return self.cache_tag or self.name

    def __repr__(self):
        return (f'Profile({self.name!r}, url_len={len(self.chat_url)}, '
                f'key={self.key_name!r}, roles={sorted(self.roles)}, '
                f'prices={len(self.prices)}, cache_suffix={self.cache_suffix()!r}, '
                f'reasoning={self.reasoning!r})')


PROFILES = {}
_ACTIVE = {}


def _parse_reasoning(text):
    """'main=none,esc=low' -> {'main': 'none', 'esc': 'low'}.

    Непонятное пропускается молча: переменная окружения — не то место, где стоит
    ронять сборку запроса. Роль, которой нет в профиле, отсеивается вызывающим.
    """
    out = {}
    for part in str(text or '').split(','):
        if '=' not in part:
            continue
        role, _, effort = part.partition('=')
        role, effort = role.strip(), effort.strip()
        if role in REASONING_ROLES and effort:
            out[role] = effort
    return out


def register(profile):
    PROFILES[profile.name] = profile
    return profile


def load_profiles(path=None):
    """профили из JSON-файла. Отсутствие файла — не ошибка, если хватает встроенных."""
    path = path or PROFILES_JSON
    if not os.path.exists(path):
        return {}
    try:
        raw = json.load(io.open(path, encoding='utf-8'))
    except Exception as e:
        raise ValueError(f'файл профилей {path} не читается: {e}')
    out = {}
    for name, spec in (raw.get('providers') or raw).items():
        if not isinstance(spec, dict):
            continue
        out[name] = Profile(
            name=name,
            chat_url=spec.get('chat_url') or '',
            key_name=spec.get('key_name') or '',
            roles=spec.get('roles') or {},
            prices={k: tuple(v) for k, v in (spec.get('prices') or {}).items()},
            cache_tag=spec.get('cache_tag') or '',
            cost_header=spec.get('cost_header'),
            note=spec.get('note') or '',
            reasoning=spec.get('reasoning') or {})
    return out


def reset():
    """сбросить кэш активного профиля (нужно тестам)"""
    _ACTIVE.clear()


def active(name=None, path=None):
    """активный профиль: аргумент, переменная окружения, иначе значение по умолчанию"""
    name = name or os.environ.get(ENV_VAR) or DEFAULT_PROVIDER
    if name in _ACTIVE:
        return _ACTIVE[name]
    if name not in PROFILES:
        PROFILES.update(load_profiles(path))
    if name not in PROFILES:
        raise KeyError(
            f'профиль поставщика {name!r} не найден. Известны: {sorted(PROFILES)}. '
            f'Ожидался файл профилей {path or PROFILES_JSON} — проверьте переменную '
            f'{ENV_VAR} и наличие файла.')
    prof = PROFILES[name]
    if not prof.chat_url:
        raise ValueError(f'в профиле {name!r} не заполнен адрес точки чата (chat_url)')
    if not prof.key_name:
        raise ValueError(f'в профиле {name!r} не заполнено имя ключа (key_name)')
    missing = [r for r in ('detect', 'main', 'esc') if not prof.roles.get(r)]
    if missing:
        raise ValueError(
            f'в профиле {name!r} не заполнены роли моделей: {missing}. '
            f'Впишите адреса в {path or PROFILES_JSON} — идентификаторы моделей этого '
            f'поставщика в исходном коде держать нельзя, их подменяет вывод среды.')
    _ACTIVE[name] = prof
    return prof


# ------------------------------------------------------------------ ключ и запрос

def load_key(profile, cred_path=None):
    """ключ поставщика из файла учётных данных; ошибка называет искомое имя.

    Ключи в файле лежат вложенными строками с отступом, поэтому имя ищется с
    необязательным ведущим пробелом, а не только в начале строки.
    """
    path = cred_path or CRED
    if not os.path.exists(path):
        raise FileNotFoundError(f'файл учётных данных не найден: {path}')
    txt = io.open(path, encoding='utf-8').read()
    m = re.search(rf'^[ \t]*{re.escape(profile.key_name)}[ \t]*:[ \t]*(\S+)', txt, re.M)
    if not m:
        found = re.findall(r'^[ \t]*([A-Za-z0-9_]+)[ \t]*:', txt, re.M)
        raise KeyError(
            f'в {path} нет ключа {profile.key_name} (нужен профилю {profile.name!r}). '
            f'В файле есть: {sorted(set(found))}')
    return m.group(1)


def build_request(profile, model, messages, key, temperature=0.1, max_tokens=8192):
    """ЧИСТАЯ сборка запроса: ничего не отправляет и ничего не читает с диска.

    Возвращает (url, headers, body_bytes). Единственная точка сетевого вывода —
    `pipeline.chat`, она вызывает эту функцию.
    """
    if not model:
        raise ValueError(f'пустой адрес модели для профиля {profile.name!r}')
    url = profile.chat_url
    headers = {'Authorization': 'Bearer ' + (key or ''), 'Content-Type': 'application/json'}
    payload = {'model': model, 'messages': messages,
               'temperature': temperature, 'max_tokens': max_tokens}
    effort = profile.effort_for(model)
    if effort:
        payload['reasoning_effort'] = effort
    return url, headers, json.dumps(payload).encode()


def cost_from_headers(profile, headers):
    """стоимость из заголовка ответа, если поставщик её сообщает"""
    if not profile.cost_header or headers is None:
        return None
    raw = headers.get(profile.cost_header)
    if raw in (None, ''):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def call_cost(profile, model, prompt_tokens, completion_tokens, headers=None):
    """стоимость вызова: сначала заголовок, потом таблица профиля.

    Возвращает (рубли, источник). Неизвестная цена и отсутствие заголовка дают
    предупреждение и нуль — но не тихий нуль: см. Profile.price_of.
    """
    from_header = cost_from_headers(profile, headers)
    if from_header is not None:
        return from_header, 'заголовок ответа'
    prices = profile.price_of(model)
    if prices is None:
        return 0.0, 'неизвестно'
    pi, co = prices
    return (prompt_tokens / 1e6 * pi + completion_tokens / 1e6 * co), 'таблица профиля'
