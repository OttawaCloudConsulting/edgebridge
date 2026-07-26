"""Registration storage, lookup, and the source-IP matching k8s can break."""

import os

import edgebridge
from conftest import FakeServer

EDGEID = '3894be52-09e8-4cfd-ad5c-580de59b6873'
RECORD = {'devaddr': ('192.168.1.150', None), 'edgeid': EDGEID,
          'hubaddr': ('192.168.1.107', 31732)}


def test_regs_round_trip_uses_state_dir(tmp_path):
    edgebridge.write_regs(edgebridge.REGSFILENAME, [RECORD])

    written = tmp_path / edgebridge.REGSFILENAME
    assert written.exists(), 'registrations must land in STATE_DIR'
    assert edgebridge.read_regs(edgebridge.REGSFILENAME) == [
        {'devaddr': ['192.168.1.150', None], 'edgeid': EDGEID,
         'hubaddr': ['192.168.1.107', 31732]}
    ]


def test_state_dir_is_independent_of_cwd(tmp_path, monkeypatch):
    """Config may be mounted read-only, so state must not follow the CWD."""
    state = tmp_path / 'state'
    state.mkdir()
    monkeypatch.setattr(edgebridge, 'STATE_DIR', str(state))

    edgebridge.write_regs(edgebridge.REGSFILENAME, [RECORD])

    assert (state / edgebridge.REGSFILENAME).exists()
    assert not os.path.exists(os.path.join(os.getcwd(), edgebridge.REGSFILENAME))


def test_find_reg_matches_on_addr_and_id():
    reglist = [RECORD]

    assert edgebridge.find_reg(reglist, RECORD['devaddr'], EDGEID) == 0
    assert edgebridge.find_reg(reglist, ('10.0.0.1', None), EDGEID) is None
    assert edgebridge.find_reg(reglist, RECORD['devaddr'], 'other-id') is None


def test_find_reg_misses_after_reload_tuple_becomes_list(tmp_path):
    """Known upstream quirk, pinned so a future fix is a deliberate choice.

    verify_addr() produces tuples; JSON round-trips them into lists, and
    tuple != list, so a re-registration appends a duplicate instead of
    replacing the existing record.
    """
    edgebridge.write_regs(edgebridge.REGSFILENAME, [RECORD])
    reloaded = edgebridge.read_regs(edgebridge.REGSFILENAME)

    assert reloaded[0]['devaddr'] == ['192.168.1.150', None]
    assert edgebridge.find_reg(reloaded, RECORD['devaddr'], EDGEID) is None


def test_registered_source_ip_is_forwarded(monkeypatch):
    forwarded = []
    monkeypatch.setattr(edgebridge, 'registrations', [RECORD])
    monkeypatch.setattr(edgebridge, 'passto_hub', lambda s, r: forwarded.append(r))
    monkeypatch.setattr(edgebridge, 'http_response', lambda *a: None)

    matched = edgebridge.proc_registered_requests(
        FakeServer(client_address=('192.168.1.150', 5555)))

    assert matched is True
    assert forwarded == [RECORD]


def test_registration_matching_breaks_when_source_ip_changes(monkeypatch):
    """Regression guarding the Kubernetes Service requirements.

    Devices are matched purely on client_address[0]. If kube-proxy SNATs the
    source to the node IP, every inbound device message silently stops
    matching - which is why the Service needs externalTrafficPolicy: Local.
    """
    forwarded = []
    monkeypatch.setattr(edgebridge, 'registrations', [RECORD])
    monkeypatch.setattr(edgebridge, 'passto_hub', lambda s, r: forwarded.append(r))
    monkeypatch.setattr(edgebridge, 'http_response', lambda *a: None)

    matched = edgebridge.proc_registered_requests(
        FakeServer(client_address=('10.42.0.1', 5555)))  # SNAT'd to a node IP

    assert matched is False
    assert forwarded == []


def test_passto_hub_sends_with_a_timeout(monkeypatch):
    """Without a timeout one unreachable hub blocks the process indefinitely."""
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        captured['url'] = url

        class Resp:
            status_code = 200
        return Resp()

    monkeypatch.setattr(edgebridge.requests, 'post', fake_post)

    edgebridge.passto_hub(FakeServer(path='/trigger', command='POST'), RECORD)

    assert captured['timeout'] == edgebridge.FWTIMEOUT
    assert captured['url'].startswith('http://192.168.1.107:31732/192.168.1.150/POST')


def test_error_threshold_queues_registration_for_scrubbing(monkeypatch):
    monkeypatch.setattr(edgebridge, 'registrations', [RECORD])

    for _ in range(3):
        edgebridge.error_proc(RECORD['hubaddr'])

    assert RECORD in edgebridge.regdeletelist
