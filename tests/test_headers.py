"""build_headers() and the redaction that keeps the bearer token out of logs."""

import responses

import edgebridge
from conftest import FakeServer

ST_PATH = '/api/forward?url=https://api.smartthings.com/v1/devices'
OTHER_PATH = '/api/forward?url=https://example.com/thing'


def test_ignored_headers_are_dropped():
    server = FakeServer(headers={
        'User-Agent': 'curl/8.0', 'Host': 'bridge.local',
        'TE': 'trailers', 'Connection': 'keep-alive',
        'X-Custom': 'kept',
    })

    headers = edgebridge.build_headers(server, OTHER_PATH)

    assert headers['X-Custom'] == 'kept'
    assert headers['Host'] == 'example.com'          # rewritten to the target
    assert headers['User-Agent'] == 'SmartThings Edge Hub'
    assert 'TE' not in headers and 'Connection' not in headers


def test_token_injected_for_smartthings_api():
    headers = edgebridge.build_headers(FakeServer(), ST_PATH)

    assert headers['Authorization'] == edgebridge.SMARTTHINGS_TOKEN
    assert headers['Authorization'].startswith('Bearer ')


def test_token_not_injected_for_other_hosts():
    assert 'Authorization' not in edgebridge.build_headers(FakeServer(), OTHER_PATH)


def test_client_authorization_is_not_overridden():
    """A driver supplying its own credential must win over the configured token."""
    server = FakeServer(headers={'Authorization': 'Bearer client-supplied'})

    headers = edgebridge.build_headers(server, ST_PATH)

    assert headers['Authorization'] == 'Bearer client-supplied'


def test_redact_headers_masks_credentials():
    redacted = edgebridge.redact_headers({
        'Authorization': 'Bearer super-secret',
        'Proxy-Authorization': 'Basic other-secret',
        'Accept': '*/*',
    })

    assert redacted['Authorization'] == edgebridge.REDACTED
    assert redacted['Proxy-Authorization'] == edgebridge.REDACTED
    assert redacted['Accept'] == '*/*'


@responses.activate
def test_token_never_reaches_the_debug_log(monkeypatch, capsys):
    """Regression: proc_forward used to log the built headers verbatim, which
    wrote the bearer token straight into the log under -d."""
    responses.add(responses.GET, 'https://api.smartthings.com/v1/devices',
                  body='[]', status=200)
    monkeypatch.setattr(edgebridge, 'DEBUG', True)
    monkeypatch.setattr(edgebridge.log, 'toconsole', True)

    edgebridge.proc_forward(FakeServer(command='GET', path=ST_PATH), 'GET', ST_PATH,
                            'url=https://api.smartthings.com/v1/devices')

    out = capsys.readouterr().out
    assert 'Headers:' in out, 'debug output was not captured'
    assert edgebridge.REDACTED in out
    assert edgebridge.SMARTTHINGS_TOKEN not in out
