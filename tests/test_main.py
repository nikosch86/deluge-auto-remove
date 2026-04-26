"""End-to-end tests for main() driving a fake DelugeRPCClient."""
# pylint: disable=missing-function-docstring,missing-class-docstring
# pylint: disable=redefined-outer-name,unused-argument,too-many-instance-attributes
import logging
import sys
import types

import pytest

import main as main_module


class FakeDelugeRPCClient:
    """Stand-in for deluge_client.DelugeRPCClient."""

    instances = []

    def __init__(self, host, port, user, password, **kwargs):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.kwargs = kwargs
        self.connected = False
        self.connect_exception = None
        self.torrents = {}
        self.removed = []
        self.remove_responses = {}
        FakeDelugeRPCClient.instances.append(self)

    def connect(self):
        if self.connect_exception:
            raise self.connect_exception
        self.connected = True

    def call(self, method, *args):
        if method == "core.get_torrents_status":
            return self.torrents
        if method == "core.remove_torrent":
            torrent_id = args[0]
            self.removed.append(args)
            override = self.remove_responses.get(torrent_id)
            if isinstance(override, Exception):
                raise override
            if override is not None:
                return override
            return True
        raise AssertionError(f"unexpected method {method}")


@pytest.fixture(autouse=True)
def reset_fake():
    FakeDelugeRPCClient.instances = []
    yield


class FakeRemoteException(Exception):
    pass


@pytest.fixture
def fake_deluge_client(monkeypatch):
    """Install a fake `deluge_client` module so main()'s lazy import picks it up."""
    fake_module = types.ModuleType("deluge_client")
    fake_client_submodule = types.ModuleType("deluge_client.client")
    fake_module.DelugeRPCClient = FakeDelugeRPCClient
    fake_client_submodule.RemoteException = FakeRemoteException
    fake_module.client = fake_client_submodule
    monkeypatch.setitem(sys.modules, "deluge_client", fake_module)
    monkeypatch.setitem(sys.modules, "deluge_client.client", fake_client_submodule)
    monkeypatch.setattr(main_module.coloredlogs, "install", lambda **kwargs: None)
    return fake_module


CONNECT_ARGS = ["--host", "h", "--port", "58846", "--user", "u", "--password", "p"]


def test_main_exits_when_required_arg_missing(monkeypatch, fake_deluge_client):
    for var in ["DELUGE_HOST", "DELUGE_PORT", "DELUGE_USER", "DELUGE_PASSWORD"]:
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(SystemExit) as exc_info:
        main_module.main([])
    assert exc_info.value.code == 2


def test_main_connect_failure_exits(fake_deluge_client, monkeypatch):
    def make_failing_client(*args, **kwargs):
        client = FakeDelugeRPCClient(*args, **kwargs)
        client.connect_exception = RuntimeError("network down")
        return client

    monkeypatch.setattr(fake_deluge_client, "DelugeRPCClient", make_failing_client)
    with pytest.raises(SystemExit) as exc_info:
        main_module.main(CONNECT_ARGS)
    assert exc_info.value.code == 2


def test_main_bad_login_exits(fake_deluge_client, monkeypatch, caplog):
    bad_login_cls = type("BadLoginError", (FakeRemoteException,), {})

    def make_failing_client(*args, **kwargs):
        client = FakeDelugeRPCClient(*args, **kwargs)
        client.connect_exception = bad_login_cls("login rejected")
        return client

    monkeypatch.setattr(fake_deluge_client, "DelugeRPCClient", make_failing_client)
    with caplog.at_level(logging.CRITICAL):
        with pytest.raises(SystemExit):
            main_module.main(CONNECT_ARGS)
    assert "wrong password" in caplog.text


def test_main_other_remote_exception_exits(fake_deluge_client, monkeypatch, caplog):
    other_cls = type("SomeOtherError", (FakeRemoteException,), {})

    def make_failing_client(*args, **kwargs):
        client = FakeDelugeRPCClient(*args, **kwargs)
        client.connect_exception = other_cls("daemon refused")
        return client

    monkeypatch.setattr(fake_deluge_client, "DelugeRPCClient", make_failing_client)
    with caplog.at_level(logging.CRITICAL):
        with pytest.raises(SystemExit):
            main_module.main(CONNECT_ARGS)
    assert "daemon refused" in caplog.text


def _seeded_client_factory(torrents):
    def factory(*args, **kwargs):
        client = FakeDelugeRPCClient(*args, **kwargs)
        client.torrents = torrents
        return client
    return factory


def test_main_removes_when_seeding_exceeded(fake_deluge_client, monkeypatch):
    torrents = {
        b"id-old": {
            "name": "old.torrent",
            "state": "Seeding",
            "label": "",
            "is_finished": True,
            "seeding_time": 30 * 86400,
            "ratio": 1.0,
            "stop_ratio": 2.0,
            "stop_at_ratio": False,
            "time_added": 0,
        },
        b"id-new": {
            "name": "new.torrent",
            "state": "Seeding",
            "label": "",
            "is_finished": True,
            "seeding_time": 1 * 86400,
            "ratio": 0.5,
            "stop_ratio": 2.0,
            "stop_at_ratio": False,
            "time_added": 0,
        },
    }
    monkeypatch.setattr(fake_deluge_client, "DelugeRPCClient",
        _seeded_client_factory(torrents))
    main_module.main(CONNECT_ARGS + ["--days", "10", "-vv"])
    client = FakeDelugeRPCClient.instances[-1]
    assert client.removed == [("id-old", True)]


def test_main_dry_run_does_not_remove(fake_deluge_client, monkeypatch):
    torrents = {
        b"id-old": {
            "name": "old.torrent",
            "state": "Seeding",
            "label": "",
            "is_finished": True,
            "seeding_time": 30 * 86400,
            "ratio": 1.0,
            "stop_ratio": 2.0,
            "stop_at_ratio": False,
            "time_added": 0,
        },
    }
    monkeypatch.setattr(fake_deluge_client, "DelugeRPCClient",
        _seeded_client_factory(torrents))
    main_module.main(CONNECT_ARGS + ["--days", "10", "--dry-run"])
    client = FakeDelugeRPCClient.instances[-1]
    assert client.removed == []


def test_main_keep_data_inverts_flag(fake_deluge_client, monkeypatch):
    torrents = {
        b"id-old": {
            "name": "old.torrent",
            "state": "Seeding",
            "label": "",
            "is_finished": True,
            "seeding_time": 30 * 86400,
            "ratio": 1.0,
            "stop_ratio": 2.0,
            "stop_at_ratio": False,
            "time_added": 0,
        },
    }
    monkeypatch.setattr(fake_deluge_client, "DelugeRPCClient",
        _seeded_client_factory(torrents))
    main_module.main(CONNECT_ARGS + ["--days", "10", "--keep-data"])
    client = FakeDelugeRPCClient.instances[-1]
    assert client.removed == [("id-old", False)]


def test_main_logs_stop_ratio_ignored_branch(fake_deluge_client, monkeypatch, caplog):
    torrents = {
        b"id-x": {
            "name": "x.torrent",
            "state": "Seeding",
            "label": "",
            "is_finished": True,
            "seeding_time": 1 * 86400,
            "ratio": 5.0,
            "stop_ratio": 2.0,
            "stop_at_ratio": False,
            "time_added": 0,
        },
    }
    monkeypatch.setattr(fake_deluge_client, "DelugeRPCClient",
        _seeded_client_factory(torrents))
    with caplog.at_level(logging.DEBUG):
        main_module.main(CONNECT_ARGS + ["-vv"])
    client = FakeDelugeRPCClient.instances[-1]
    assert client.removed == []
    assert "stop_at_ratio" in caplog.text


def test_main_removes_via_numeric_ratio(fake_deluge_client, monkeypatch):
    torrents = {
        b"id-x": {
            "name": "x.torrent",
            "state": "Seeding",
            "label": "",
            "is_finished": True,
            "seeding_time": 1 * 86400,
            "ratio": 3.0,
            "stop_ratio": 99.0,
            "stop_at_ratio": True,
            "time_added": 0,
        },
    }
    monkeypatch.setattr(fake_deluge_client, "DelugeRPCClient",
        _seeded_client_factory(torrents))
    main_module.main(CONNECT_ARGS + ["--ratio", "2.0"])
    client = FakeDelugeRPCClient.instances[-1]
    assert client.removed == [("id-x", True)]


def test_main_removes_via_stop_ratio_when_enabled(fake_deluge_client, monkeypatch):
    torrents = {
        b"id-x": {
            "name": "x.torrent",
            "state": "Seeding",
            "label": "",
            "is_finished": True,
            "seeding_time": 1 * 86400,
            "ratio": 3.0,
            "stop_ratio": 2.0,
            "stop_at_ratio": True,
            "time_added": 0,
        },
    }
    monkeypatch.setattr(fake_deluge_client, "DelugeRPCClient",
        _seeded_client_factory(torrents))
    main_module.main(CONNECT_ARGS + ["-v"])
    client = FakeDelugeRPCClient.instances[-1]
    assert client.removed == [("id-x", True)]


def test_main_continues_after_failed_removal(fake_deluge_client, monkeypatch, caplog):
    torrents = {
        b"id-bad": {
            "name": "bad.torrent",
            "state": "Seeding",
            "label": "",
            "is_finished": True,
            "seeding_time": 30 * 86400,
            "ratio": 0.0,
            "stop_ratio": 99.0,
            "stop_at_ratio": False,
            "time_added": 0,
        },
        b"id-good": {
            "name": "good.torrent",
            "state": "Seeding",
            "label": "",
            "is_finished": True,
            "seeding_time": 30 * 86400,
            "ratio": 0.0,
            "stop_ratio": 99.0,
            "stop_at_ratio": False,
            "time_added": 0,
        },
    }

    def factory(*args, **kwargs):
        client = FakeDelugeRPCClient(*args, **kwargs)
        client.torrents = torrents
        client.remove_responses = {"id-bad": RuntimeError("daemon hated it")}
        return client

    monkeypatch.setattr(fake_deluge_client, "DelugeRPCClient", factory)
    with caplog.at_level(logging.ERROR):
        main_module.main(CONNECT_ARGS + ["--days", "10"])
    client = FakeDelugeRPCClient.instances[-1]
    # Both torrents were attempted; the bad one didn't abort the run.
    assert {call[0] for call in client.removed} == {"id-bad", "id-good"}
    assert "daemon hated it" in caplog.text


def test_main_keeps_when_label_matches(fake_deluge_client, monkeypatch):
    torrents = {
        b"id-keep": {
            "name": "keep.torrent",
            "state": "Seeding",
            "label": "keep",
            "is_finished": True,
            "seeding_time": 99 * 86400,
            "ratio": 99.0,
            "stop_ratio": 1.0,
            "stop_at_ratio": True,
            "time_added": 0,
        },
    }
    monkeypatch.setattr(fake_deluge_client, "DelugeRPCClient",
        _seeded_client_factory(torrents))
    main_module.main(CONNECT_ARGS)
    client = FakeDelugeRPCClient.instances[-1]
    assert client.removed == []


def test_main_disconnected_after_connect_dies(fake_deluge_client, monkeypatch, caplog):
    def factory(*args, **kwargs):
        client = FakeDelugeRPCClient(*args, **kwargs)
        original_connect = client.connect

        def connect_but_stay_disconnected():
            original_connect()
            client.connected = False
        client.connect = connect_but_stay_disconnected
        return client

    monkeypatch.setattr(fake_deluge_client, "DelugeRPCClient", factory)
    with caplog.at_level(logging.CRITICAL):
        with pytest.raises(SystemExit) as exc_info:
            main_module.main(CONNECT_ARGS)
    assert exc_info.value.code == 2
    assert "failed to connect" in caplog.text


def test_main_missing_deluge_client_module_dies(monkeypatch, caplog):
    monkeypatch.setattr(main_module.coloredlogs, "install", lambda **kwargs: None)
    monkeypatch.setitem(sys.modules, "deluge_client", None)
    with caplog.at_level(logging.CRITICAL):
        with pytest.raises(SystemExit) as exc_info:
            main_module.main(CONNECT_ARGS)
    assert exc_info.value.code == 2
