import json

import httpx
import pytest

from vn_market_data.sources import fireant
from vn_market_data.sources.base import SourceUnavailable


def test_turnover_paginates_and_sorts(monkeypatch):
    monkeypatch.setattr(fireant, '_PAGE_SIZE', 2)
    monkeypatch.setattr(fireant, 'post_capped', lambda *a, **k: (200, b'{"accessToken":"secret"}'))
    calls = []
    def get(url, **kwargs):
        calls.append(kwargs)
        offset = kwargs['params']['offset']
        rows = ([{'symbol': 'VNINDEX', 'date': f'2026-10-{day}T00:00:00',
                  'totalValue': 100, 'putthroughValue': 30, 'totalVolume': 10}
                 for day in ('30', '29')] if offset == 0 else [])
        return 200, json.dumps(rows).encode()
    monkeypatch.setattr(fireant, 'get_capped', get)
    rows = fireant.FireAntSource().get_market_turnover('vnindex', '2026-10-01', '2026-10-31')
    assert [r['date'] for r in rows] == ['2026-10-29', '2026-10-30']
    assert rows[0] == {'date': '2026-10-29', 'value': 100, 'matched': 70,
                       'put_through': 30, 'volume': 10}
    assert [c['params']['offset'] for c in calls] == [0, 2]
    assert calls[0]['headers']['Authorization'] == 'Bearer secret'


@pytest.mark.parametrize('status,body', [(401, b''), (200, b'{}'), (200, b'bad'),
                                         (200, b'[{"date":"2026-10-30"}]')])
def test_bad_response_falls_through(monkeypatch, status, body):
    monkeypatch.setattr(fireant, 'post_capped', lambda *a, **k: (200, b'{"accessToken":"secret"}'))
    monkeypatch.setattr(fireant, 'get_capped', lambda *a, **k: (status, body))
    with pytest.raises(SourceUnavailable):
        fireant.FireAntSource().get_market_turnover('VNINDEX', '2026-10-01', '2026-10-31')


def test_login_and_network_failure_fall_through(monkeypatch):
    monkeypatch.setattr(fireant, 'post_capped', lambda *a, **k: (200, b'{}'))
    with pytest.raises(SourceUnavailable):
        fireant.FireAntSource().get_market_turnover('VNINDEX', '2026-10-01', '2026-10-31')
    def fail(*args, **kwargs):
        raise httpx.ConnectError('offline')
    monkeypatch.setattr(fireant, 'post_capped', fail)
    with pytest.raises(SourceUnavailable):
        fireant.FireAntSource().get_market_turnover('VNINDEX', '2026-10-01', '2026-10-31')


def test_invalid_symbol_never_reaches_api():
    with pytest.raises(ValueError):
        fireant.FireAntSource().get_market_turnover('../x', '2026-10-01', '2026-10-31')


@pytest.mark.parametrize('method,kind', [('get_news', 1), ('get_discussions', 0)])
def test_symbol_posts_fetch_one_page(monkeypatch, method, kind):
    monkeypatch.setattr(fireant, 'post_capped', lambda *a, **k: (200, b'{"accessToken":"secret"}'))
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return 200, b'[{"postID":42,"title":"Example"}]'
    monkeypatch.setattr(fireant, 'get_capped', get)
    result = getattr(fireant.FireAntSource(), method)('fpt', offset=20, limit=10)
    assert result == [{'postID': 42, 'title': 'Example'}]
    assert calls[0][0].endswith('/symbols/FPT/posts')
    assert calls[0][1]['params'] == {'offset': 20, 'limit': 10, 'type': kind}


def test_replies_and_empty_page(monkeypatch):
    monkeypatch.setattr(fireant, 'post_capped', lambda *a, **k: (200, b'{"accessToken":"secret"}'))
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        return 200, b'[]'
    monkeypatch.setattr(fireant, 'get_capped', get)
    assert fireant.FireAntSource().get_replies(42) == []
    assert calls[0].endswith('/posts/42/replies')


@pytest.mark.parametrize('status,body', [(401, b''), (200, b'{}'), (200, b'bad'),
                                         (200, b'[{"title":"missing id"}]')])
def test_posts_failure_is_not_empty(monkeypatch, status, body):
    monkeypatch.setattr(fireant, 'post_capped', lambda *a, **k: (200, b'{"accessToken":"secret"}'))
    monkeypatch.setattr(fireant, 'get_capped', lambda *a, **k: (status, body))
    with pytest.raises(SourceUnavailable):
        fireant.FireAntSource().get_news('FPT')


@pytest.mark.parametrize('call', [lambda s: s.get_news('../bad'),
                                  lambda s: s.get_news('FPT', offset=-1),
                                  lambda s: s.get_discussions('FPT', limit=21),
                                  lambda s: s.get_replies(0)])
def test_posts_invalid_input(call):
    with pytest.raises(ValueError):
        call(fireant.FireAntSource())
