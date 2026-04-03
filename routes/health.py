import requests
from flask import jsonify
from flask import Flask
from typing import Callable


def init_health_routes(app: Flask, get_api_url: Callable[[], str]) -> None:
    """
    Регистрирует роут /health
    get_api_url — функция, возвращающая URL API для проверки
    """

#######
    @app.route('/health')
    def health():
        try:
            api_url = get_api_url()
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500

        # Try known health endpoints first, then fall back to base URL.
        base = str(api_url).rstrip('/')
        candidates = [f"{base}/api/healthy", f"{base}/healthy", base]
        last_exc = None
        last_resp = None
        for url in candidates:
            try:
                resp = requests.get(url, timeout=3)
                last_resp = resp
                if resp.status_code == 200:
                    return jsonify({'status': 'ok', 'code': resp.status_code}), 200
                # continue trying other candidates on unexpected status
            except Exception as e:
                last_exc = e
                continue

        # If we reached here, no candidate returned 200
        if last_resp is not None:
            return jsonify({'status': 'error', 'code': getattr(last_resp, 'status_code', None)}), 500
        else:
            return jsonify({'status': 'error', 'error': str(last_exc)}), 500
