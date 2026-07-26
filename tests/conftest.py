"""Shared fixtures.

The single most important thing here is `bootstrap`. `edgebridge.log` does not
exist at import time - it is created as a side effect of `process_config()`
(edgebridge.py, end of that function). Nearly every function in the module calls
`log.*`, so without this autouse fixture almost any test fails with NameError.
"""

import http.server
import io
import threading

import pytest

import edgebridge

# 36 characters, which is what process_config validates the token length against.
TEST_TOKEN = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'

CFG_TEMPLATE = """[config]
Server_Port = {port}
SmartThings_Bearer_Token = {token}
forwarding_timeout = {timeout}
console_output = no
logfile_output = no
"""


def write_cfg(tmp_path, port=8088, token=TEST_TOKEN, timeout=5, extra=''):
    """Write a config file and return its path as a string."""
    cfg = tmp_path / 'edgebridge.cfg'
    cfg.write_text(CFG_TEMPLATE.format(port=port, token=token, timeout=timeout) + extra)
    return str(cfg)


@pytest.fixture(autouse=True)
def bootstrap(tmp_path, monkeypatch):
    """Initialise `log` and isolate module-level state for every test."""
    edgebridge.process_config(write_cfg(tmp_path))

    monkeypatch.setattr(edgebridge, 'STATE_DIR', str(tmp_path))
    monkeypatch.setattr(edgebridge, 'DEBUG', False)
    monkeypatch.setattr(edgebridge, 'registrations', [])
    monkeypatch.setattr(edgebridge, 'hubsenderrors', {})
    monkeypatch.setattr(edgebridge, 'regdeletelist', [])

    yield


class FakeServer:
    """Stands in for the BaseHTTPRequestHandler passed around the module."""

    def __init__(self, client_address=('192.168.1.150', 4444), path='/',
                 command='POST', data_bytes=b'', headers=None):
        self.client_address = client_address
        self.path = path
        self.command = command
        self.data_bytes = data_bytes
        self.headers = headers if headers is not None else {}
        self.responses = []
        self.wfile = io.BytesIO()

    # http_response() is monkeypatched out in most tests, but when it is not,
    # these let a FakeServer absorb a real response without a socket.
    def send_response(self, code):
        self.responses.append(code)

    def send_header(self, *_args):
        pass

    def end_headers(self):
        pass


@pytest.fixture
def live_server():
    """A real threaded server on an ephemeral port; yields its base URL."""
    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), edgebridge.myHTTPRequestHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    yield f'http://127.0.0.1:{httpd.server_address[1]}'

    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)
