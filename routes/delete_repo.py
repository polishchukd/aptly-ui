# delete_repo.py

import requests
from flask import request, jsonify, Flask
from flask_login import login_required, current_user
from urllib.parse import quote
from app_utils import safe_text, fetch_publishes, encode_publish_path, find_publish_by_repo
from typing import Callable
from i18n import inject_i18n
from app_logging import command_logging


def init_delete_repo_routes(app: Flask, get_api_url: Callable) -> None:

#######
    def delete_publish(api_url: str, prefix: str, distribution: str, force: bool) -> dict:
        """Удалить публикацию и вернуть результат."""
        try:
            url = f"{api_url}/publish/{encode_publish_path(prefix, distribution)}"
            resp = requests.delete(url, params={'force': '1'} if force else None)
            return {'status': resp.status_code, 'body': safe_text(resp)}
        except Exception as e:
            return {'status': 'error', 'body': str(e)}


#######
    def repo_still_published(api_url: str, repo: str) -> bool:
        """Проверить, остался ли репозиторий в публикациях."""
        publishes = fetch_publishes(api_url)
        return find_publish_by_repo(publishes, repo) is not None


#######
    def delete_repo_only(api_url: str, repo: str, force: bool = False) -> dict:
        """Удалить сам репозиторий.

        Если force=True, передаём параметр ?force=1 согласно документации Aptly.
        """
        try:
            params = {'force': '1'} if force else None
            resp = requests.delete(f"{api_url}/repos/{repo}", params=params)
            return {'status': resp.status_code, 'body': safe_text(resp)}
        except Exception as e:
            return {'status': 'error', 'body': str(e)}


#######
    @app.route('/delete_repo', methods=['POST'])
    @login_required
    def delete_repo():
        # Входные данные: {repo: <name>, force: true|false}
        _t = inject_i18n()['_t']
        data = request.get_json(silent=True) or {}
        repo = data.get('repo') or request.form.get('repo')
        force = data.get('force') if 'force' in data else (request.form.get('force') == '1')

        if not repo:
            return jsonify({'error': _t('flash.repo_required')}), 400

        # Получаем имя текущего пользователя
        username = getattr(current_user, 'username', None)

        api_url = get_api_url()
        result = {'publish': None, 'repo': None}

        try:
            # Проверка публикаций
            pub_entry = find_publish_by_repo(fetch_publishes(api_url), repo)

            if pub_entry:
                prefix = pub_entry.get('Prefix') or pub_entry.get('prefix') or ''
                distribution = pub_entry.get('Distribution') or pub_entry.get('distribution') or ''

                if prefix and distribution:
                    result['publish'] = delete_publish(api_url, prefix, distribution, bool(force))

                    # Записать результат удаления публикации в журнал
                    pub_res = result['publish']
                    try:
                        status = pub_res.get('status')
                    except Exception:
                        status = None
                    if status in (200, 201, 202, 204):
                        command_logging(
                            level='INFO',
                            name='DELETE_PUBLISH',
                            extra={'prefix': prefix, 'distribution': distribution, 'repo': repo},
                            username=username
                        )
                    else:
                        # pub_res is a dict {'status':..., 'body':...} or error-string
                        pub_body = pub_res.get('body') if isinstance(pub_res, dict) else str(pub_res)
                        command_logging(
                            level='ERROR',
                            name='DELETE_PUBLISH_FAIL',
                            code=status if isinstance(status, int) else None,
                            body=(pub_body or '')[:400],
                            extra={'prefix': prefix, 'distribution': distribution, 'repo': repo},
                            username=username
                        )
                    if repo_still_published(api_url, repo):
                        result['repo'] = {
                            'status': 'skipped',
                            'body': _t('flash.repo_still_published')
                        }
                        return jsonify(result)

            # Удаление самого репозитория (передаём force если указан)
            result['repo'] = delete_repo_only(api_url, repo, bool(force))
            # Записать результат удаления репозитория в журнал
            try:
                repo_status = result['repo'].get('status')
            except Exception:
                repo_status = None
            if repo_status in (200, 201, 202, 204):
                command_logging(
                    level='INFO',
                    name='DELETE_REPO',
                    extra={'repo': repo},
                    username=username
                )
            else:
                repo_body = result['repo'].get('body') if isinstance(result['repo'], dict) else str(result['repo'])
                command_logging(
                    level='ERROR',
                    name='DELETE_REPO_FAIL',
                    code=repo_status if isinstance(repo_status, int) else None,
                    body=(repo_body or '')[:400],
                    extra={'repo': repo},
                    username=username
                )
            return jsonify(result)

        except Exception as e:
            # записать исключение в журнал команд для аудита
            command_logging(
                level='ERROR',
                name='DELETE_REPO_EXCEPTION',
                body=str(e),
                extra={'repo': repo},
                username=username
            )
            return jsonify({'error': str(e)}), 500
