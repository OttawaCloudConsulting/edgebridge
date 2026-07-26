"""End-to-end tests against a real threaded server on an ephemeral port.

`responses` patches requests globally, which would also intercept the test
client's own call into the live server. Every mocked test therefore registers a
passthru for the server's base URL so only the *outbound* call is faked.
"""

import requests
import responses

import edgebridge

EDGEID = '3894be52-09e8-4cfd-ad5c-580de59b6873'


def test_healthz_returns_200(live_server):
    assert requests.get(f'{live_server}/healthz', timeout=5).status_code == 200


def test_readyz_returns_200(live_server):
    assert requests.get(f'{live_server}/readyz', timeout=5).status_code == 200


def test_healthz_is_not_relayed_for_a_registered_source(live_server, monkeypatch):
    """The probe arrives from the same host the tests register, so this proves
    the health path is matched before registration lookup."""
    forwarded = []
    monkeypatch.setattr(edgebridge, 'registrations', [
        {'devaddr': ('127.0.0.1', None), 'edgeid': EDGEID,
         'hubaddr': ('192.168.1.107', 31732)}])
    monkeypatch.setattr(edgebridge, 'passto_hub', lambda s, r: forwarded.append(r))

    assert requests.get(f'{live_server}/healthz', timeout=5).status_code == 200
    assert forwarded == []


def test_post_ping_returns_200(live_server):
    assert requests.post(f'{live_server}/api/ping', timeout=5).status_code == 200


def test_get_ping_returns_400(live_server):
    """Pinned upstream behaviour: the ping fast path exists only in do_POST, so
    a GET falls through to handle_requests and fails the no-query-string check.
    /healthz exists precisely because this is not usable as a probe."""
    assert requests.get(f'{live_server}/api/ping', timeout=5).status_code == 400


def test_register_and_delete_round_trip(live_server, tmp_path):
    params = f'devaddr=192.168.1.150&hubaddr=192.168.1.107:31732&edgeid={EDGEID}'

    assert requests.post(f'{live_server}/api/register?{params}', timeout=5).status_code == 200
    assert (tmp_path / edgebridge.REGSFILENAME).read_text().strip()
    assert len(edgebridge.registrations) == 1

    assert requests.delete(f'{live_server}/api/register?{params}', timeout=5).status_code == 200
    assert edgebridge.registrations == []


def test_register_rejects_a_bad_address(live_server):
    params = f'devaddr=999.999.999.999&hubaddr=192.168.1.107:31732&edgeid={EDGEID}'

    assert requests.post(f'{live_server}/api/register?{params}', timeout=5).status_code == 400


@responses.activate
def test_forward_returns_upstream_body(live_server):
    responses.add_passthru(live_server)
    responses.add(responses.GET, 'https://example.com/data', body='hello', status=200)

    r = requests.get(f'{live_server}/api/forward?url=https://example.com/data', timeout=5)

    assert r.status_code == 200
    assert r.text == 'hello'


@responses.activate
def test_forward_preserves_multibyte_body(live_server):
    """Content-Length must be measured in bytes, not characters."""
    body = 'héllo 日本語'
    responses.add_passthru(live_server)
    responses.add(responses.GET, 'https://example.com/utf8', body=body, status=200)

    r = requests.get(f'{live_server}/api/forward?url=https://example.com/utf8', timeout=5)

    assert r.content.decode('utf-8') == body


@responses.activate
def test_forward_maps_upstream_error_status(live_server):
    responses.add_passthru(live_server)
    responses.add(responses.GET, 'https://example.com/nope', status=404)

    r = requests.get(f'{live_server}/api/forward?url=https://example.com/nope', timeout=5)

    assert r.status_code == 404


@responses.activate
def test_forward_returns_502_when_target_is_unreachable(live_server):
    """Regression: only requests.Timeout was caught, so a connection failure
    escaped the handler and the driver received no response at all."""
    responses.add_passthru(live_server)
    responses.add(responses.GET, 'https://example.com/down',
                  body=requests.exceptions.ConnectionError('refused'))

    r = requests.get(f'{live_server}/api/forward?url=https://example.com/down', timeout=10)

    assert r.status_code == 502


@responses.activate
def test_forward_returns_502_on_timeout(live_server):
    responses.add_passthru(live_server)
    responses.add(responses.GET, 'https://example.com/slow',
                  body=requests.exceptions.Timeout('too slow'))

    r = requests.get(f'{live_server}/api/forward?url=https://example.com/slow', timeout=10)

    assert r.status_code == 502


def test_forward_without_url_argument_returns_400(live_server):
    r = requests.get(f'{live_server}/api/forward?nourl=1', timeout=5)

    assert r.status_code == 400


def test_unknown_endpoint_returns_404(live_server):
    r = requests.get(f'{live_server}/api/bogus?x=1', timeout=5)

    assert r.status_code == 404
