"""Logger robustness. Misconfiguration must degrade, not kill the process."""

import edgebridge
from conftest import write_cfg


def test_logfile_output_without_a_path_does_not_crash(tmp_path, capsys):
    """Regression: logoutp was set before the path was read, so a missing
    'logfile' key left filename='' and the first message raised
    FileNotFoundError during startup - a crash loop in a container."""
    edgebridge.process_config(
        write_cfg(tmp_path, console_output='no', logfile_output='yes'))

    edgebridge.log.warn('this must not raise')

    assert edgebridge.log.savetofile is False
    assert 'no logfile was specified' in capsys.readouterr().out


def test_logfile_output_without_a_path_falls_back_to_console(tmp_path, capsys):
    """Console output is forced back on, otherwise the misconfiguration would
    leave the process running with no output at all."""
    edgebridge.process_config(
        write_cfg(tmp_path, console_output='no', logfile_output='yes'))

    edgebridge.log.info('visible message')

    assert 'visible message' in capsys.readouterr().out


def test_unwritable_logfile_degrades_to_console(tmp_path, capsys):
    """An unwritable path (read-only mount, missing directory) must not raise."""
    edgebridge.process_config(write_cfg(
        tmp_path, logfile_output='yes', logfile=tmp_path / 'nope' / 'deep' / 'x.log'))

    edgebridge.log.error('still delivered')

    out = capsys.readouterr().out
    assert edgebridge.log.savetofile is False
    assert 'is not writable' in out
    assert 'still delivered' in out


def test_valid_logfile_is_written(tmp_path):
    logfile = tmp_path / 'edgebridge.log'
    edgebridge.process_config(
        write_cfg(tmp_path, logfile_output='yes', logfile=logfile))

    edgebridge.log.info('recorded')

    assert 'recorded' in logfile.read_text()
