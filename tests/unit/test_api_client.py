import httpx
import pytest
from desktop.api_client import ApiClient, ApiError


def test_network_disconnect(monkeypatch):
    def failed(*args, **kwargs):
        raise httpx.ConnectError('offline')
    monkeypatch.setattr(httpx, 'request', failed)
    with pytest.raises(ApiError, match='تعذر الاتصال'):
        ApiClient().request('GET', '/health')


def test_api_error_is_readable(monkeypatch):
    monkeypatch.setattr(httpx, 'request', lambda *a, **k: httpx.Response(403, json={'detail': 'غير مسموح'}))
    with pytest.raises(ApiError, match='غير مسموح'):
        ApiClient().request('GET', '/api/patients')


def test_api_validation_error(monkeypatch):
    monkeypatch.setattr(httpx, 'request', lambda *a, **k: httpx.Response(422, json={
        'detail': [{'loc': ['body', 'full_name'], 'msg': 'required'}]}))
    with pytest.raises(ApiError, match='full_name: required'):
        ApiClient().request('POST', '/api/patients', {})
