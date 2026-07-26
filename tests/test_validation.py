import pytest

import edgebridge


@pytest.mark.parametrize('addr, expected', [
    ('192.168.1.150', ('192.168.1.150', None)),
    ('192.168.1.150:2345', ('192.168.1.150', 2345)),
    ('0.0.0.0', ('0.0.0.0', None)),
    ('255.255.255.255:65535', ('255.255.255.255', 65535)),
])
def test_verify_addr_accepts_valid(addr, expected):
    assert edgebridge.verify_addr(addr) == expected


@pytest.mark.parametrize('addr', [
    '',
    None,
    '192.168.1',           # too few octets
    '192.168.1.1.1',       # too many octets
    '192.168.1.256',       # octet out of range
    '192.168.1.150:0',     # port below range
    '192.168.1.150:65536',  # port above range
    'not.an.ip.addr',
])
def test_verify_addr_rejects_invalid(addr):
    assert edgebridge.verify_addr(addr) is False


def test_verify_id_lowercases():
    assert edgebridge.verify_ID('3894BE52-09E8-4CFD-AD5C-580DE59B6873') == \
        '3894be52-09e8-4cfd-ad5c-580de59b6873'


@pytest.mark.parametrize('bad_id', [
    '',
    '3894be52-09e8-4cfd-ad5c',              # too few groups
    '3894be5-09e8-4cfd-ad5c-580de59b6873',  # wrong group length
    '3894be5z-09e8-4cfd-ad5c-580de59b6873',  # non-hex character
])
def test_verify_id_rejects_invalid(bad_id):
    assert edgebridge.verify_ID(bad_id) is False
