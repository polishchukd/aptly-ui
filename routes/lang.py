# lang.py

from flask import request, session, jsonify, Flask
from flask_login import login_required
from i18n import load_translations, TRANSLATIONS_CACHE


def init_lang_routes(app: Flask, users: dict) -> None:


#######
    @app.route('/set_lang', methods=['POST'])
    def set_lang():
        """Установить язык пользователя в сессии (просто). Принимает JSON {lang: 'ru'|'en'} или form data.

        Возвращает JSON {status:'ok', lang: <lang>} при успехе.
        """
        data = {}
        try:
            data = request.get_json(force=False) or {}
        except Exception:
            data = {}
        lang = data.get('lang') or request.form.get('lang')
        if not lang:
            return jsonify({'status': 'error', 'error': 'missing lang'}), 400
        if lang not in ('ru', 'en'):
            return jsonify({'status': 'error', 'error': 'unsupported lang'}), 400
        session['lang'] = lang
        # Предзагрузить переводы для удобства
        load_translations(lang)
        return jsonify({'status': 'ok', 'lang': lang}), 200


#######
    @app.route('/reload_i18n', methods=['POST'])
    @login_required
    def reload_i18n():
        """Простой аутентифицированный эндпоинт для очистки кеша переводов и повторной загрузки с диска.

        Используйте, когда вы изменили файлы в `i18n/` и хотите, чтобы изменения были применены без
        перезапуска процесса приложения. Возвращает JSON с базовой информацией о статусе.
        """
        global TRANSLATIONS_CACHE
        TRANSLATIONS_CACHE = {}
        # Принудительно перезагрузить переводы для языка по умолчанию
        lang = 'ru'
        translations = load_translations(lang)
        return jsonify({'status': 'ok', 'lang': lang, 'loaded_keys': len(translations)}), 200
