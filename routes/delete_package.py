# delete_package.py

import requests
from flask import request, jsonify, Flask
from flask_login import login_required, current_user
from app_logging import command_logging
from app_utils import safe_text, update_publish
from typing import Callable
from i18n import inject_i18n


def init_delete_package_routes(app: Flask, get_api_url: Callable[[], str]) -> None:

# =============================
# Endpoint delete_package
# Назначение: удалить указанный пакет (конкретную версию + архитектуру, если задана) из
# локального репозитория. Алгоритм: получить детали пакетов репозитория, собрать ключи
# соответствующих объектов и выполнить DELETE /repos/<repo>/packages c JSON {PackageRefs:[...] }.
# При успешном статусе из набора (200,201) возвращает {status:'ok'}. Не обновляет публикации
# автоматически — это остаётся на усмотрение пользователя.
# =============================
    @app.route('/delete_package', methods=['POST'])
    @login_required
    def delete_package():
        _t = inject_i18n()['_t']
        data = request.get_json() or {}
        repo = data.get('repo')
        package_name = data.get('package_name')
        version = data.get('version')
        arch = data.get('arch')
        if not all([repo, package_name, version]):
            return jsonify({'error': _t('flash.missing_parameters')}), 400

        # Получаем имя текущего пользователя
        username = getattr(current_user, 'username', None)

        api_url = get_api_url()
        try:
            # Получить детали пакетов для репозитория
            resp = requests.get(f'{api_url}/repos/{repo}/packages?format=details')
            if resp.status_code != 200:
                return jsonify({'error': _t('flash.packages_list_fetch_failed') + f': {safe_text(resp)}'}), resp.status_code
            pkgs = resp.json()
            delete_keys = []
            for pkg in pkgs:
                if pkg.get('Package') == package_name and pkg.get('Version') == version:
                    delete_keys.append(pkg.get('Key'))

            if not delete_keys:
                command_logging(
                    level='WARNING',
                    name='DELETE_PACKAGE_NOT_FOUND',
                    extra={'package': package_name, 'version': version, 'arch': arch, 'repo': repo},
                    username=username
                )
                return jsonify({'error': _t('flash.package_not_found')}), 404
            # Удалить
            del_url = f'{api_url}/repos/{repo}/packages'
            payload = {"PackageRefs": delete_keys}
            del_resp = requests.delete(del_url, json=payload)
            if del_resp.status_code in (200, 201, 202, 204):
                command_logging(
                    level='INFO',
                    name='DELETE_PACKAGE',
                    extra={'repo': repo, 'keys': ','.join(delete_keys)},
                    username=username
                )
                # Попытка обновить публикацию (если репозиторий публикуется)
                publish_update = None
                try:
                    publish_update = update_publish(api_url, repo=repo)
                    if publish_update.get('status') in (200, 201, 202, 204):
                        command_logging(
                            level='INFO',
                            name='DELETE_PACKAGE_PUBLISH_UPDATED',
                            extra={'repo': repo},
                            username=username
                        )
                    else:
                        if publish_update.get('error') == 'no_publish_found':
                            command_logging(
                                level='INFO',
                                name='DELETE_PACKAGE_NO_PUBLISH',
                                extra={'repo': repo},
                                username=username
                            )
                        else:
                            command_logging(
                                level='ERROR',
                                name='DELETE_PACKAGE_PUBLISH_UPDATE_FAIL',
                                code=publish_update.get('status'),
                                body=(publish_update.get('body') or '')[:400],
                                extra={'repo': repo},
                                username=username
                            )
                except Exception as e:
                    command_logging(
                        level='ERROR',
                        name='DELETE_PACKAGE_PUBLISH_EXCEPTION',
                        body=str(e),
                        extra={'repo': repo},
                        username=username
                    )

                return jsonify({'status': 'ok', 'publish_update': publish_update})
            else:
                command_logging(
                    level='ERROR',
                    name='DELETE_PACKAGE_FAIL',
                    code=del_resp.status_code,
                    body=safe_text(del_resp)[:400],
                    extra={'repo': repo},
                    username=username
                )
                return jsonify({'error': _t('flash.delete_package_failed') + f': {safe_text(del_resp)}'}), del_resp.status_code
        except Exception as e:
            command_logging(
                level='ERROR',
                name='DELETE_PACKAGE_EXCEPTION',
                body=str(e),
                extra={'repo': repo},
                username=username
            )
            return jsonify({'error': _t('flash.delete_package_exception') + f': {e}'}), 500
