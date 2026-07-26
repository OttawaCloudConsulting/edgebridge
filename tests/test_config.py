"""Config parsing, including the settings that used to be silently ignored."""

import edgebridge

from conftest import TEST_TOKEN, write_cfg


def test_forwarding_timeout_reaches_the_module_global(tmp_path):
    """Regression: FWTIMEOUT was assigned without a `global` declaration, so
    the configured value went to a local and the timeout stayed at 5s."""
    edgebridge.process_config(write_cfg(tmp_path, timeout=17))

    assert edgebridge.FWTIMEOUT == 17


def test_port_and_token_are_applied(tmp_path):
    edgebridge.process_config(write_cfg(tmp_path, port=9001))

    assert edgebridge.SERVER_PORT == 9001
    assert edgebridge.SMARTTHINGS_TOKEN == f'Bearer {TEST_TOKEN}'


def test_wrong_length_token_is_discarded(tmp_path):
    edgebridge.process_config(write_cfg(tmp_path, token='too-short'))

    assert edgebridge.SMARTTHINGS_TOKEN == edgebridge.DEFAULT_ST_TOKEN


def test_invalid_port_falls_back_to_default(tmp_path):
    edgebridge.process_config(write_cfg(tmp_path, port=99999))

    assert edgebridge.SERVER_PORT == edgebridge.DEFAULT_SERVERPORT


def test_missing_config_file_leaves_defaults(tmp_path):
    edgebridge.process_config(str(tmp_path / 'does-not-exist.cfg'))

    assert edgebridge.SERVER_PORT == edgebridge.DEFAULT_SERVERPORT
    assert edgebridge.SMARTTHINGS_TOKEN == edgebridge.DEFAULT_ST_TOKEN
    assert edgebridge.log is not None


def test_valid_server_ip_is_accepted(tmp_path):
    edgebridge.process_config(write_cfg(tmp_path, extra='Server_IP = 127.0.0.1\n'))

    assert str(edgebridge.SERVER_IP) == '127.0.0.1'


def test_invalid_server_ip_falls_back_to_all_interfaces(tmp_path):
    edgebridge.process_config(write_cfg(tmp_path, extra='Server_IP = 192.168.1.xxx\n'))

    assert edgebridge.SERVER_IP == ''


def test_arg_defaults():
    args = edgebridge.parse_args([])

    assert args.config == edgebridge.CONFIGFILENAME
    assert args.state_dir == '.'
    assert args.debug is False


def test_args_parse_config_and_state_dir():
    args = edgebridge.parse_args(
        ['-d', '--config', '/etc/edgebridge/edgebridge.cfg', '--state-dir', '/var/lib/edgebridge'])

    assert args.debug is True
    assert args.config == '/etc/edgebridge/edgebridge.cfg'
    assert args.state_dir == '/var/lib/edgebridge'
