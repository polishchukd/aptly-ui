# upload_package.py

import requests
import io
import re
import time
from typing import Callable
from i18n import inject_i18n
from flask import request, jsonify, Flask
from flask_login import login_required, current_user
from app_utils import safe_text, update_publish
from app_logging import command_logging

def init_upload_package_routes(app: Flask, get_api_url: Callable[[], str]) -> None:

# =============================
# Endpoint upload_package
# Назначение: загрузить .deb файл через форму, сохранить во временный storage Aptly (/files), затем импортировать в выбранный репозиторий.
# Принимает multipart/form-data: file (.deb), repo (имя репозитория).
# Возвращает JSON с результатом загрузки и импорта.
# =============================
    @app.route('/upload_package', methods=['POST'])
    @login_required
    def upload_package():
        _t = inject_i18n()['_t']
        if 'file' not in request.files or 'repo' not in request.form:
            return jsonify({'error': _t('flash.upload_file_repo_required')}), 400
        file = request.files['file']
        repo = request.form['repo'].strip()
        if not file or not repo:
            return jsonify({'error': _t('flash.upload_file_repo_required')}), 400
        if not (file.filename.endswith('.deb') or file.filename.endswith('.ddeb')):
                return jsonify({'error': _t('flash.upload_deb_only')}), 400

        # Получаем имя текущего пользователя
        username = getattr(current_user, 'username', None)

        api_url = get_api_url()
        # Шаг 1: загрузить файл в Aptly storage (/files/:dir)
        try:
            try:
                file.stream.seek(0)
            except Exception:
                pass
            file_bytes = file.read()

            # Очистить имя директории для загрузки: разрешены только буквы, цифры, точка, дефис, нижнее подчёркивание
            raw_dir = repo or 'uploads'
            safe_dir = re.sub(r'[^A-Za-z0-9._-]+', '_', raw_dir)
            # добавить метку времени, чтобы избежать коллизий
            safe_dir = f"{safe_dir}-{int(time.time())}"

            # Подготовить кандидатный POST URL в зависимости от того, содержит ли базовый адрес API уже /api
            base_raw = str(api_url).rstrip('/')
            if base_raw.endswith('/api'):
                post_url = f"{base_raw}/files/{safe_dir}"
                repo_import_base = base_raw
            else:
                post_url = f"{base_raw}/api/files/{safe_dir}"
                repo_import_base = base_raw.rstrip('/') + '/api'

            tried = []
            upload_resp = None
            upload_url_used = None
            uploaded_path = None

            # Отправить multipart форму методом POST на /api/files/:dir
            try:
                files_payload = {'file': (file.filename, io.BytesIO(file_bytes), file.mimetype or 'application/octet-stream')}
                resp = requests.post(post_url, files=files_payload)
                tried.append({'method': 'POST', 'url': post_url, 'status': getattr(resp, 'status_code', 'err'), 'body': safe_text(resp)[:800]})
                if resp is not None and resp.status_code in (200, 201, 202, 204):
                    upload_resp = resp
                    upload_url_used = post_url
            except Exception as e:
                tried.append({'method': 'POST', 'url': post_url, 'error': str(e)})

            if not upload_resp:
                command_logging(
                    level='ERROR',
                    name='UPLOAD_PACKAGE_ALL_FAIL',
                    body=str(tried),
                    extra={'file': file.filename, 'repo': repo},
                    username=username
                )
                return jsonify({'error': _t('flash.upload_failed_no_endpoint'), 'tried': tried}), 502

            # Разбор ответа на загрузку: ожидается список строк вида "dir/filename"
            try:
                j = upload_resp.json()
                if isinstance(j, list) and j:
                    uploaded_path = j[0]
                elif isinstance(j, dict):
                    # резервный вариант - попытаться найти первое значение
                    if 'Files' in j and isinstance(j['Files'], list) and j['Files']:
                        uploaded_path = j['Files'][0]
            except Exception:
                pass
            # резервный вариант: использовать только имя файла
            if not uploaded_path:
                uploaded_path = f"{safe_dir}/{file.filename}"

            # Шаг 2: импортируем файл (POST /api/repos/:name/file/:dir or /:dir/:file)
            import_resp = None
            import_url_used = None
            tried_import = []

            # Определить директорию и, при необходимости, имя файла
            if '/' in uploaded_path:
                dir_part, file_part = uploaded_path.split('/', 1)
            else:
                dir_part, file_part = uploaded_path, None

            # Сначала пробуем импортировать всю директорию
            try:
                import_url = f"{repo_import_base}/repos/{repo}/file/{dir_part}"
                resp = requests.post(import_url)
                tried_import.append({'url': import_url, 'status': getattr(resp, 'status_code', 'err'), 'body': safe_text(resp)[:800]})
                if resp is not None and resp.status_code in (200, 201, 202, 204):
                    import_resp = resp
                    import_url_used = import_url
            except Exception as e:
                tried_import.append({'url': import_url if 'import_url' in locals() else f'{repo_import_base}/repos/{repo}/file/{dir_part}', 'error': str(e)})

            # Если импорт директории не удался и есть имя файла, пробуем импортировать отдельный файл
            if not import_resp and file_part:
                try:
                    import_url = f"{repo_import_base}/repos/{repo}/file/{dir_part}/{file_part}"
                    resp = requests.post(import_url)
                    tried_import.append({'url': import_url, 'status': getattr(resp, 'status_code', 'err'), 'body': safe_text(resp)[:800]})
                    if resp is not None and resp.status_code in (200, 201, 202, 204):
                        import_resp = resp
                        import_url_used = import_url
                except Exception as e:
                    tried_import.append({'url': import_url if 'import_url' in locals() else f'{repo_import_base}/repos/{repo}/file/{dir_part}/{file_part}', 'error': str(e)})

            if not import_resp:
                command_logging(
                    level='ERROR',
                    name='IMPORT_DEB_ALL_FAIL',
                    body=str(tried_import),
                    extra={'file': uploaded_path, 'repo': repo},
                    username=username
                )
                return jsonify({'error': _t('flash.import_failed'), 'tried': tried_import}), 502

            # Попробовать разобрать JSON-ответ для получения деталей
            import_details = None
            try:
                import_details = import_resp.json()
            except Exception:
                import_details = safe_text(import_resp)

            # Попытаться обновить публикацию через общий helper
            publish_update = None
            try:
                publish_update = update_publish(api_url, repo=repo)
                if publish_update.get('status') in (200, 201, 202, 204):
                    command_logging(
                        level='INFO',
                        name='UPLOAD_PACKAGE_PUBLISH_UPDATED',
                        extra={'file': file.filename, 'repo': repo},
                        username=username
                    )
                else:
                    if publish_update.get('error') == 'no_publish_found':
                        command_logging(
                            level='INFO',
                            name='UPLOAD_PACKAGE_NO_PUBLISH',
                            extra={'file': file.filename, 'repo': repo},
                            username=username
                        )
                    else:
                        command_logging(
                            level='ERROR',
                            name='UPLOAD_PACKAGE_PUBLISH_UPDATE_FAIL',
                            code=publish_update.get('status'),
                            body=(publish_update.get('body') or '')[:400],
                            extra={'file': file.filename, 'repo': repo},
                            username=username
                        )
            except Exception as e:
                command_logging(
                    level='ERROR',
                    name='UPLOAD_PACKAGE_PUBLISH_EXCEPTION',
                    body=str(e),
                    extra={'file': file.filename, 'repo': repo},
                    username=username
                )

            command_logging(
                level='INFO',
                name='UPLOAD_PACKAGE',
                extra={'file': file.filename, 'repo': repo},
                username=username
            )
            return jsonify({'status': 'ok', 'filename': uploaded_path, 'repo': repo, 'details': import_details, 'publish_update': publish_update}), 200
        except Exception as e:
            command_logging(
                level='ERROR',
                name='UPLOAD_PACKAGE_EXCEPTION',
                body=str(e),
                extra={'file': file.filename if file else '', 'repo': repo},
                username=username
            )
            return jsonify({'error': _t('flash.upload_exception') + f': {e}'}), 500
