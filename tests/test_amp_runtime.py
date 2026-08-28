"""Tests for CAI AMP session entry helpers."""

from cai.lib.amp_runtime import should_run_amp_entry


def test_should_run_amp_entry_for_main():
    assert should_run_amp_entry("__main__") is True


def test_should_run_amp_entry_for_imported_module():
    assert should_run_amp_entry("cai.amp.some_module") is False
