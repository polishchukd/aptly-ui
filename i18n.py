# i18n.py

from pathlib import Path
import json
from flask import session


# =============================
# Минимальный загрузчик переводов (JSON-файлы в каталоге i18n/<lang>.json)
# Предоставляет хелпер `_t(key)` и словарь `I18N` в Jinja-шаблоны через context_processor.
# Язык по умолчанию — 'ru'. Сделано простым намеренно, можно позже мигрировать на Flask-Babel.
# =============================
TRANSLATIONS_CACHE = {}

########
def load_translations(lang: str = 'ru') -> dict:
    """Загрузить переводы из i18n/<lang>.json и кэшировать их.

    Возвращает dict; при ошибке возвращает пустой dict.
    """
    lang = (lang or 'ru')
    if lang in TRANSLATIONS_CACHE:
        return TRANSLATIONS_CACHE[lang]
    p = Path('i18n') / f'{lang}.json'
    try:
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                TRANSLATIONS_CACHE[lang] = data
                return data
    except Exception:
        pass
    TRANSLATIONS_CACHE[lang] = {}
    return {}

#######
def inject_i18n() -> dict:
    # Минимально: предпочитать язык из session, по умолчанию — русский. Можно расширить чтением заголовков.
    lang = session.get('lang', 'ru')
    translations = load_translations(lang)
    def _t(key, default=''):
        try:
            return translations.get(key, default or key)
        except Exception:
            return default or key
    return {'I18N': translations, '_t': _t, 'CURRENT_LANG': lang}
