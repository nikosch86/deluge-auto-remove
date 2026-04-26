"""Tests for the should_remove() per-torrent decision function."""
# pylint: disable=missing-function-docstring
import pytest

from main import should_remove


def make_torrent(**overrides):
    base = {
        "name": "test.torrent",
        "state": "Seeding",
        "label": "",
        "is_finished": True,
        "seeding_time": 0,
        "ratio": 0.0,
        "stop_ratio": 2.0,
        "stop_at_ratio": False,
        "time_added": 0,
    }
    base.update(overrides)
    return base


DEFAULTS = {"seeding_days": 25, "ratio": "auto", "keep_label": "keep", "remove_error": False}


def call(torrent, **overrides):
    kwargs = {**DEFAULTS, **overrides}
    return should_remove(torrent, **kwargs)


# --- state filtering -------------------------------------------------------

@pytest.mark.parametrize("state", ["Seeding", "Paused"])
def test_eligible_states_pass_initial_gate(state):
    decision, _ = call(make_torrent(state=state, seeding_time=99 * 86400))
    assert decision is True


@pytest.mark.parametrize("state", ["Downloading", "Queued", "Checking", "Allocating"])
def test_non_eligible_states_are_kept(state):
    decision, reason = call(make_torrent(state=state, seeding_time=99 * 86400))
    assert decision is False
    assert reason is None


def test_error_state_kept_by_default():
    decision, _ = call(make_torrent(state="Error", seeding_time=99 * 86400))
    assert decision is False


def test_error_state_removed_when_remove_error_enabled():
    decision, reason = call(
        make_torrent(state="Error", seeding_time=99 * 86400),
        remove_error=True,
    )
    assert decision is True
    assert reason == "seeding_days"


# --- keep label ------------------------------------------------------------

def test_keep_label_skips_torrent():
    decision, reason = call(make_torrent(label="keep", seeding_time=99 * 86400))
    assert decision is False
    assert reason is None


def test_non_keep_label_does_not_skip():
    decision, _ = call(make_torrent(label="other", seeding_time=99 * 86400))
    assert decision is True


def test_custom_keep_label_respected():
    decision, _ = call(
        make_torrent(label="archive", seeding_time=99 * 86400),
        keep_label="archive",
    )
    assert decision is False


# --- is_finished -----------------------------------------------------------

def test_unfinished_torrent_is_kept():
    decision, _ = call(make_torrent(is_finished=False, seeding_time=99 * 86400))
    assert decision is False


# --- seeding days ----------------------------------------------------------

def test_seeding_under_threshold_is_kept():
    decision, _ = call(make_torrent(seeding_time=10 * 86400), seeding_days=25)
    assert decision is False


def test_seeding_over_threshold_is_removed():
    decision, reason = call(make_torrent(seeding_time=26 * 86400), seeding_days=25)
    assert decision is True
    assert reason == "seeding_days"


def test_seeding_exactly_at_threshold_is_kept():
    # original used `>` not `>=`
    decision, _ = call(make_torrent(seeding_time=25 * 86400), seeding_days=25)
    assert decision is False


# --- numeric ratio ---------------------------------------------------------

def test_numeric_ratio_above_threshold_removes():
    decision, reason = call(make_torrent(ratio=2.5), ratio="2.0")
    assert decision is True
    assert reason == "ratio"


def test_numeric_ratio_below_threshold_kept():
    decision, _ = call(make_torrent(ratio=1.0), ratio="2.0")
    assert decision is False


def test_negative_ratio_is_dead_switch():
    # original guarded with `> -1`, so any negative ratio disables the check
    decision, _ = call(make_torrent(ratio=99.0), ratio="-1")
    assert decision is False


# --- auto ratio ------------------------------------------------------------

def test_auto_ratio_removes_when_stop_at_ratio_true():
    torrent = make_torrent(ratio=3.0, stop_ratio=2.0, stop_at_ratio=True)
    decision, reason = call(torrent)
    assert decision is True
    assert reason == "stop_ratio"


def test_auto_ratio_keeps_when_stop_at_ratio_false():
    torrent = make_torrent(ratio=3.0, stop_ratio=2.0, stop_at_ratio=False)
    decision, reason = call(torrent)
    assert decision is False
    assert reason == "stop_ratio_ignored"


def test_auto_ratio_keeps_when_under_stop_ratio():
    torrent = make_torrent(ratio=1.0, stop_ratio=2.0, stop_at_ratio=True)
    decision, reason = call(torrent)
    assert decision is False
    assert reason is None


# --- precedence ------------------------------------------------------------

def test_seeding_days_takes_precedence_over_ratio():
    torrent = make_torrent(seeding_time=99 * 86400, ratio=3.0, stop_ratio=2.0,
        stop_at_ratio=True)
    decision, reason = call(torrent)
    assert decision is True
    assert reason == "seeding_days"
