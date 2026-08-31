"""Tests for CAI AMP session entry helpers."""

import pytest

from cai.lib.amp_runtime import run_amp_entry, should_run_amp_entry


def test_should_run_amp_entry_for_main():
    assert should_run_amp_entry("__main__") is True


def test_should_run_amp_entry_for_imported_module():
    assert should_run_amp_entry("cai.amp.some_module") is False


def test_run_amp_entry_cli_success_exits_zero():
    with pytest.raises(SystemExit) as exc:
        run_amp_entry(lambda: 0, "__main__")
    assert exc.value.code == 0


def test_run_amp_entry_cli_failure_exits_nonzero():
    with pytest.raises(SystemExit) as exc:
        run_amp_entry(lambda: 1, "__main__")
    assert exc.value.code == 1


def test_run_amp_entry_ipython_success_does_not_raise(monkeypatch):
    monkeypatch.setitem(
        __import__("builtins").__dict__,
        "get_ipython",
        lambda: object(),
    )
    run_amp_entry(lambda: 0, "__main__")


def test_run_amp_entry_ipython_failure_raises_system_exit(monkeypatch):
    monkeypatch.setitem(
        __import__("builtins").__dict__,
        "get_ipython",
        lambda: object(),
    )
    with pytest.raises(SystemExit) as exc:
        run_amp_entry(lambda: 2, "__main__")
    assert exc.value.code == 2
