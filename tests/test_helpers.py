import logging

import pytest

from main import build_argparser, cleanup_and_die, remove


def test_cleanup_and_die_exits_with_code_2(caplog):
    with caplog.at_level(logging.CRITICAL):
        with pytest.raises(SystemExit) as exc_info:
            cleanup_and_die("boom")
    assert exc_info.value.code == 2
    assert "boom" in caplog.text


def test_argparser_defaults_when_env_unset(monkeypatch):
    for var in ["DELUGE_HOST", "DELUGE_PORT", "DELUGE_USER", "DELUGE_PASSWORD"]:
        monkeypatch.delenv(var, raising=False)
    parser = build_argparser()
    args = parser.parse_args([])
    assert args.host is None
    assert args.port is None
    assert args.days == 25
    assert args.ratio == "auto"
    assert args.keep_label == "keep"
    assert args.dry_run is False
    assert args.keep_data is False
    assert args.remove_error is False
    assert args.verbose == 0


def test_argparser_reads_env(monkeypatch):
    monkeypatch.setenv("DELUGE_HOST", "deluge.local")
    monkeypatch.setenv("DELUGE_PORT", "58846")
    monkeypatch.setenv("DELUGE_USER", "u")
    monkeypatch.setenv("DELUGE_PASSWORD", "p")
    parser = build_argparser()
    args = parser.parse_args([])
    assert args.host == "deluge.local"
    assert args.port == "58846"
    assert args.user == "u"
    assert args.password == "p"


def test_argparser_cli_overrides_env(monkeypatch):
    monkeypatch.setenv("DELUGE_HOST", "from-env")
    parser = build_argparser()
    args = parser.parse_args(["--host", "from-cli"])
    assert args.host == "from-cli"


def test_argparser_verbose_counts():
    parser = build_argparser()
    assert parser.parse_args(["-v"]).verbose == 1
    assert parser.parse_args(["-vv"]).verbose == 2
    assert parser.parse_args(["-vvv"]).verbose == 3


class FakeClient:
    def __init__(self, response=True):
        self.response = response
        self.calls = []

    def call(self, method, *args):
        self.calls.append((method, args))
        return self.response


def test_remove_dry_run_does_not_call_client(caplog):
    client = FakeClient()
    with caplog.at_level(logging.INFO):
        remove(client, "abc", keep_data=False, dry_run=True)
    assert client.calls == []
    assert "[dry-run]" in caplog.text
    assert "(with data)" in caplog.text


def test_remove_dry_run_keep_data_message(caplog):
    client = FakeClient()
    with caplog.at_level(logging.INFO):
        remove(client, "abc", keep_data=True, dry_run=True)
    assert "(with data)" not in caplog.text


def test_remove_calls_client(caplog):
    client = FakeClient(response=True)
    with caplog.at_level(logging.INFO):
        remove(client, "abc", keep_data=False, dry_run=False)
    assert client.calls == [("core.remove_torrent", ("abc", True))]


def test_remove_keep_data_passes_false():
    client = FakeClient(response=True)
    remove(client, "abc", keep_data=True, dry_run=False)
    assert client.calls == [("core.remove_torrent", ("abc", False))]


def test_remove_failure_exits():
    client = FakeClient(response=b"some error")
    with pytest.raises(SystemExit) as exc_info:
        remove(client, "abc", keep_data=False, dry_run=False)
    assert exc_info.value.code == 2
