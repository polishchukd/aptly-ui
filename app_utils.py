# app_utils.py

import requests
from load_config import _load_config
from urllib.parse import quote
from requests import Response
from app_logging import command_logging


# ==================================================================================================
# Функция get_api_url
# Назначение: централизованно получить URL Aptly API, требуемый для всех внешних запросов.
# Приоритет источников: значение ключа API_URL в aptly-ui.conf (секция DEFAULT) имеет первенство,
# если оно пустое – используется одноимённая переменная окружения. В случае отсутствия
# валидного значения выбрасывается RuntimeError с инструкцией по исправлению – это позволяет
# быстро обнаружить неправильную конфигурацию сразу при первом обращении (например, в health).
# Особенности: вызывается на каждый запрос вместо кеширования, чтобы изменения aptly-ui.conf
# применялись динамически. Нагрузка минимальна, так как файл небольшой; при необходимости
# возможна оптимизация простым статическим кешем.
# Возвращает: строку (базовый URL без завершающего /, если пользователь так указал).
# ==================================================================================================
def get_api_url() -> str:
    api_url = _load_config().get('API_URL')
    if not api_url:
        raise RuntimeError(
            'API_URL is not configured.')
    return api_url


# ==================================================================================================
# Функция safe_text
# Назначение: безопасно извлечь текст из HTTP-ответа requests. В некоторых случаях .text
# или .content могут генерировать исключения (нестандартные объекты / проблемы декодирования).
# Алгоритм: попытаться resp.text -> затем декодировать resp.content в UTF-8 с заменой ошибок ->
# вернуть строку-заглушку если всё не удалось. Применяется при формировании диагностических ответов
# JSON для фронтенда, чтобы избежать падения из-за плохой кодировки.
# ==================================================================================================

def safe_text(resp: Response) -> str:
    try:
        return resp.text
    except Exception:
        try:
            return resp.content.decode('utf-8', 'replace')
        except Exception as e:
            command_logging(
                level='WARNING',
                name='SAFE_TEXT_DECODE_ERROR',
                body=str(e),
                extra={'resp_type': str(type(resp))}
            )
            return '<unreadable response>'


# =====================================
# Общие функции для работы с Aptly API
# =====================================

#########
def fetch_publishes(api_url: str) -> list[dict]:
    """Получает список публикаций Aptly."""
    try:
        resp = requests.get(f"{api_url}/publish")
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []

#########
def encode_publish_path(prefix: str, distribution: str) -> str:
    """Кодирует путь публикации по правилам Aptly."""
    encoded_prefix = prefix.replace('_', '__').replace('/', '_')
    encoded_dist = quote(distribution or '', safe='')
    return f"{encoded_prefix}/{encoded_dist}"


#########
def find_repo_publish(publishes: list[dict], repo: str) -> dict | None:
    """Находит публикацию, где используется указанный репозиторий."""
    for pub in publishes:
        sources = pub.get('Sources') or []
        if any(s.get('Name') == repo for s in sources):
            return {
                'Prefix': pub.get('Prefix') or pub.get('prefix') or '',
                'Distribution': pub.get('Distribution') or pub.get('distribution') or ''
            }
    return None


#########
def find_publish_by_repo(publishes: list[dict], repo: str) -> dict | None:
    """Найти публикацию, где используется указанный репозиторий."""
    for pub in publishes:
        sources = pub.get('Sources') or []
        if any(s.get('Name') == repo for s in sources):
            return pub
    return None


#########
def update_publish(api_url: str,
                   repo: str | None = None,
                   prefix: str | None = None,
                   distribution: str | None = None) -> dict:
    """
    Обновляет существующую публикацию Aptly.
    """

    try:
        # 1. Базовые значения
        used_prefix = prefix or ''
        used_dist = distribution or ''

        # 2. Если prefix+distribution не заданы — пытаемся найти по repo
        if not (used_prefix and used_dist) and repo:
            publishes = fetch_publishes(api_url)
            pub = find_repo_publish(publishes, repo)
            if pub:
                used_prefix = used_prefix or pub.get('Prefix', '')
                used_dist = used_dist or pub.get('Distribution', '')

        # 3. Если до сих пор нет данных — публикацию найти невозможно
        if not (used_prefix and used_dist):
            return {'error': 'no_publish_found'}

        # 4. Формирование запроса
        put_url = f"{api_url}/publish/{encode_publish_path(used_prefix, used_dist)}"
        payload = {"ForceOverwrite": True}

        cfg = _load_config()
        origin = cfg.get('PUBLISH_ORIGIN')
        label = cfg.get('PUBLISH_LABEL')
        if origin:
            payload['Origin'] = origin
        if label:
            payload['Label'] = label

        # 5. Выполняем PUT
        resp = requests.put(put_url, json=payload)
        return {
            'url': put_url,
            'status': getattr(resp, 'status_code', None),
            'body': safe_text(resp)
        }

    except Exception as e:
        return {'error': str(e)}
