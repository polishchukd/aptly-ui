# copy_package.py

import requests
from flask import Flask, request, jsonify
from flask_login import login_required, current_user
from urllib.parse import quote
from app_utils import safe_text, update_publish
from app_logging import command_logging
from typing import Callable
from i18n import inject_i18n


def init_copy_package_routes(app: Flask, get_api_url: Callable[[], str]) -> None:

# =============================
# Endpoint copy_package
# Назначение: скопировать один бинарный/исходный пакет из исходного локального репозитория
# в целевой локальный репозиторий Aptly, затем попытаться обновить публикацию целевого
# (PUT /publish/<prefix>/<distribution>) для включения нового пакета. Локализует пакет по
# имени/версии (+архитектуре если указана) читая подробный список packages?format=details.
# Параметры принимаются в JSON. При успехе возвращает JSON {status:'ok', copy: <raw>, publish_update: {...}}.
# publish_update содержит диагностическую информацию (url, status, override, body) или ошибку.
# Ограничения: не создаёт публикацию, а только обновляет существующую; отсутствие публикации
# не считается фатальной ошибкой копирования.
# =============================
    def find_package_key(api_url: str, source_repo: str, package_name: str, version: str, arch: str | None = None, username: str | None = None) -> str | None:
        """
        Находит ключ пакета используя REST API packages endpoint.
        Использует точный поиск по имени и версии.
        """
        try:
            resp = requests.get(
                f'{api_url}/repos/{source_repo}/packages',
                params={'format': 'details'}
            )

            if resp.status_code == 200:
                packages = resp.json()
                for pkg in packages:
                    if (pkg.get('Package') == package_name and
                        pkg.get('Version') == version and
                        (not arch or pkg.get('Architecture') == arch)):
                        command_logging(
                            level='INFO',
                            name='COPY_PACKAGE_FOUND',
                            extra={'name': package_name, 'version': version, 'repo': source_repo},
                            username=username
                        )
                        return pkg.get('Key')

                command_logging(
                    level='WARNING',
                    name='COPY_PACKAGE_NOT_FOUND',
                    extra={'name': package_name, 'version': version, 'arch': arch, 'from': source_repo},
                    username=username
                )
            else:
                command_logging(
                    level='ERROR',
                    name='COPY_PACKAGE_API_ERROR',
                    extra={'url': f'{api_url}/repos/{source_repo}/packages', 'status': resp.status_code},
                    body=safe_text(resp)[:400],
                    username=username
                )

            return None
        except Exception as e:
            command_logging(
                level='ERROR',
                name='COPY_PACKAGE_SEARCH_EXCEPTION',
                body=str(e),
                extra={'name': package_name, 'version': version, 'repo': source_repo},
                username=username
            )
            return None


#######
    def copy_package_to_repo(api_url: str, source_repo: str, target_repo: str, package_key: str) -> requests.Response:
        """
        Копирует пакет между репозиториями используя REST API.
        Поддерживает атомарное копирование пакета с проверкой конфликтов.
        """
        url = f"{api_url}/repos/{target_repo}/packages"

        # Используем новый формат API для копирования с указанием WithDeps=0 для копирования
        # только конкретного пакета без зависимостей
        payload = {
            "PackageRefs": [package_key],
            "WithDeps": 0,
            "SourceRepo": source_repo
        }

        return requests.post(url, json=payload)


#######
    @app.route('/copy_package', methods=['POST'])
    @login_required
    def copy_package():
        _t = inject_i18n()['_t']
        data = request.get_json() or {}

        source_repo = data.get('source_repo')
        target_repo = data.get('target_repo')
        package_name = data.get('package_name')
        version = data.get('version')
        arch = data.get('arch')
        target_distribution = data.get('target_distribution')
        target_prefix = data.get('target_prefix')

        # Проверка обязательных параметров
        if not all([source_repo, target_repo, package_name, version]):
            return jsonify({'error': _t('flash.missing_parameters')}), 400

        api_url = get_api_url()

        # Получаем имя текущего пользователя
        username = getattr(current_user, 'username', None)

        try:
            # Поиск пакета в исходном репозитории используя REST API
            pkg_key = find_package_key(api_url, source_repo, package_name, version, arch, username)

            if not pkg_key:
                command_logging(
                    level='WARNING',
                    name='COPY_PACKAGE_NOT_FOUND',
                    extra={
                        'name': package_name,
                        'version': version,
                        'arch': arch or 'any',
                        'from': source_repo
                    },
                    username=username
                )
                return jsonify({'error': _t('flash.package_not_found')}), 404

            # Копирование пакета с использованием REST API
            copy_resp = copy_package_to_repo(api_url, source_repo, target_repo, pkg_key)
            if copy_resp.status_code not in (200, 201, 202, 204):
                command_logging(
                    level='ERROR',
                    name='COPY_PACKAGE_FAIL',
                    code=copy_resp.status_code,
                    body=safe_text(copy_resp)[:400],
                    extra={'key': pkg_key},
                    username=username
                )
                return jsonify({
                    'error': _t('flash.copy_package_failed') + f': {safe_text(copy_resp)}'
                }), copy_resp.status_code

            # Обновление публикации целевого репозитория
            publish_update = None
            try:
                publish_update = update_publish(
                    api_url,
                    repo=target_repo,
                    prefix=(target_prefix or None),
                    distribution=(target_distribution or None)
                    # override=bool(target_distribution or target_prefix)
                )
                if publish_update.get('status') in (200, 201, 202, 204):
                    command_logging(
                        level='INFO',
                        name='COPY_PACKAGE',
                        extra={'src': source_repo, 'dst': target_repo, 'key': pkg_key},
                        username=username
                    )
                else:
                    # If no_publish_found -> informational, otherwise log error
                    if publish_update.get('error') == 'no_publish_found':
                        command_logging(
                            level='INFO',
                            name='COPY_PACKAGE_NO_PUBLISH_UPDATE',
                            extra={'src': source_repo, 'dst': target_repo, 'key': pkg_key},
                            username=username
                        )
                    else:
                        command_logging(
                            level='ERROR',
                            name='COPY_PACKAGE_PUBLISH_UPDATE_FAIL',
                            code=publish_update.get('status'),
                            body=(publish_update.get('body') or '')[:400],
                            extra={'repo': target_repo},
                            username=username
                        )
            except Exception as e:
                command_logging(
                    level='ERROR',
                    name='COPY_PACKAGE_PUBLISH_UPDATE_EXCEPTION',
                    body=str(e),
                    extra={'repo': target_repo},
                    username=username
                )
                publish_update = {'error': str(e)}

            return jsonify({
                'status': 'ok',
                'copy': safe_text(copy_resp),
                'publish_update': publish_update
            })

        except Exception as e:
            command_logging(
                level='ERROR',
                name='COPY_PACKAGE_EXCEPTION',
                body=str(e),
                username=username
            )
            return jsonify({'error': _t('flash.copy_package_exception') + f': {e}'}), 500
