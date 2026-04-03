# api_requests.py

import requests
from flask import Flask, request, jsonify
from flask_login import login_required, current_user
from typing import Callable
from app_logging import command_logging
from i18n import inject_i18n


def init_api_requests_routes(app: Flask, get_api_url: Callable[[], str]) -> None:

# =============================
# Endpoint api_repos
# Назначение: прокси к Aptly /repos. Возвращает JSON-список репозиториев (или пустой список
# при ошибке). Используется фронтендом для автодополнения полей и списков.
# =============================
    @app.route('/api/repos', methods=['GET'])
    @login_required
    def api_repos():
        # Получаем имя текущего пользователя
        username = getattr(current_user, 'username', None)

        api_url = get_api_url()
        try:
            resp = requests.get(f'{api_url}/repos')
            if resp.status_code == 200:
                return resp.json()
            else:
                return []
        except Exception as e:
            command_logging(
                level='ERROR',
                name='API_REPOS_EXCEPTION',
                body=str(e),
                username=username
            )
            return []


# =============================
# Endpoint api_distributions
# Назначение: собрать уникальный список distribution из всех репозиториев.
# =============================
    @app.route('/api/distributions', methods=['GET'])
    @login_required
    def api_distributions():
        api_url = get_api_url()
        dists = set()
        try:
            resp = requests.get(f'{api_url}/repos')
            if resp.status_code == 200:
                repos = resp.json() or []
                for r in repos:
                    dist = r.get('DefaultDistribution') or ''
                    if dist:
                        dists.add(dist)
                    # Попытаться извлечь из имени по паттерну base-component-version-distribution
                    name = r.get('Name') or ''
                    parts = name.split('-')
                    if len(parts) >= 4 and any(ch.isdigit() for ch in parts[2]):
                        dists.add(parts[-1])
        except Exception:
            pass
        return jsonify(sorted(dists))


# =============================
# Функция ensure_list() приводит входное значение к списку
# =============================
    def ensure_list(data):
        if not data:
            return []
        if isinstance(data, list):
            return data
        return [data]


# =============================
# Endpoint api_packages
# Назначение: вернуть уникальный отсортированный список имён пакетов в заданном репозитории.
# Использует запрос packages?format=details, затем извлекает поле Package. При ошибках или
# отсутствии параметра repo возвращает пустой список. Применяется для автодополнения имени
# пакета в форме копирования.
# =============================
    @app.route('/api/packages', methods=['GET'])
    @login_required
    def api_packages():
        repo = request.args.get('repo')
        api_url = get_api_url()
        if not repo:
            return []
        try:
            resp = requests.get(f'{api_url}/repos/{repo}/packages?format=details')
            if resp.status_code == 200:
                data = resp.json()
                pkgs = ensure_list(data) # Aptly может вернуть один объект или массив -> приводим к списоку
                names = sorted(set(pkg.get('Package') for pkg in pkgs if pkg.get('Package')))
                return names
            else:
                return []
        except Exception:
            return []

# =============================
# Endpoint api_versions
# Назначение: получить список версий для конкретного пакета внутри указанного репозитория.
# Фильтрует по имени пакета и собирает уникальные значения поля Version. Возвращает отсортированный
# список строк. При отсутствии repo или package — пустой список. Используется для автодополнения
# версии перед копированием или удалением.
# =============================
    @app.route('/api/versions', methods=['GET'])
    @login_required
    def api_versions():
        repo = request.args.get('repo')
        package = request.args.get('package')
        api_url = get_api_url()
        if not repo or not package:
            return []
        try:
            resp = requests.get(f'{api_url}/repos/{repo}/packages?format=details')
            if resp.status_code == 200:
                data = resp.json()
                pkgs = ensure_list(data) # Aptly может вернуть один объект или массив -> приводим к списоку
                versions = sorted(set(pkg.get('Version') for pkg in pkgs if pkg.get('Package') == package and pkg.get('Version')))
                return versions
            else:
                return []
        except Exception:
            return []

# =============================
# Endpoint api_package_key
# Назначение: найти уникальный ключ пакета (Key) по комбинации repo + package + version
# для дальнейших операций (копирование / удаление). Выполняет один запрос details и
# перебирает результаты. Возвращает JSON {key: "..."} или ошибку.
# =============================
    @app.route('/api/package_key', methods=['GET'])
    @login_required
    def api_package_key():
        _t = inject_i18n()['_t']
        repo = request.args.get('repo')
        package = request.args.get('package')
        version = request.args.get('version')
        if not (repo and package and version):
            return jsonify({'error': _t('flash.insufficient_parameters')}), 400
        api_url = get_api_url()
        try:
            resp = requests.get(f'{api_url}/repos/{repo}/packages?format=details')
            if resp.status_code != 200:
                return jsonify({'error': _t('flash.packages_list_fetch_failed') + f': {resp.text}'}), resp.status_code
            data = resp.json()
            pkgs = ensure_list(data) # Aptly может вернуть один объект или массив -> приводим к списоку
            for pkg in pkgs:
                if pkg.get('Package') == package and pkg.get('Version') == version:
                    return jsonify({'key': pkg.get('Key')})
            return jsonify({'error': _t('flash.package_not_found')}), 404
        except Exception as e:
            return jsonify({'error': _t('flash.internal_error') + f': {e}'}), 500

# =============================
# Endpoint api_repo_distributions
# Назначение: вернуть список distribution, в которых участвует конкретный репозиторий как
# источник (по имени в массиве Sources публикаций). Сканирует /publish, фильтрует записи по
# Sources[].Name == repo и возвращает отсортированный список уникальных Distribution.
# Используется фронтендом для ограничения выпадающего списка дистрибуций при выборе репозитория.
# =============================
    @app.route('/api/repo_distributions', methods=['GET'])
    @login_required
    def api_repo_distributions():
        repo = request.args.get('repo')
        if not repo:
            return jsonify([])
        api_url = get_api_url()
        try:
            resp = requests.get(f'{api_url}/publish')
            if resp.status_code != 200:
                return jsonify([]), resp.status_code
            pubs = resp.json() or []
            dists = []
            for pub in pubs:
                sources = pub.get('Sources') or []
                if any(s.get('Name') == repo for s in sources):
                    dist = pub.get('Distribution') or pub.get('distribution') or ''
                    if dist and dist not in dists:
                        dists.append(dist)
            return jsonify(sorted(dists))
        except Exception:
            return jsonify([])

# =============================
# Endpoint api_repo_publish_info
# Назначение: вернуть список объектов публикации (Prefix + Distribution) для заданного
# репозитория. Служит для автоподстановки префикса и дистрибуции при выборе целевого
# репозитория копирования. Если репозиторий опубликован в нескольких местах, фронтенд может
# предложить выбор. Возвращает массив JSON объектов или пустой список при ошибке.
# =============================
    @app.route('/api/repo_publish_info', methods=['GET'])
    @login_required
    def api_repo_publish_info():
        repo = request.args.get('repo')
        if not repo:
            return jsonify([])
        api_url = get_api_url()
        try:
            resp = requests.get(f'{api_url}/publish')
            if resp.status_code != 200:
                return jsonify([]), resp.status_code
            pubs = resp.json() or []
            out = []
            for pub in pubs:
                sources = pub.get('Sources') or []
                if any(s.get('Name') == repo for s in sources):
                    out.append({
                        'Prefix': pub.get('Prefix') or pub.get('prefix') or '',
                        'Distribution': pub.get('Distribution') or pub.get('distribution') or ''
                    })
            return jsonify(out)
        except Exception:
            return jsonify([])
