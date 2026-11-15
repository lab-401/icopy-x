"""Tests for the UDC handover between PC mode and the always-on RNDIS gadget.

The device controller hosts a single gadget driver, so the app must detach the
configfs RNDIS gadget (tools/rndis) before loading g_acm_ms/g_serial and put it
back afterwards. These tests cover both sides of that handover and the two
ways it can silently fail: touching nothing on an image without the gadget, and
an unbind that writes an empty string (configfs ignores a zero-length store).
"""

import pytest

from middleware import gadget_linux


@pytest.fixture
def gadget(tmp_path, monkeypatch):
    """Relocate the configfs gadget root to a temporary directory."""
    root = tmp_path / 'usb_gadget' / 'icopy'
    monkeypatch.setattr(gadget_linux, '_RNDIS_GADGET', str(root))
    return root


@pytest.fixture
def calls(monkeypatch):
    """Record shell commands instead of running them."""
    recorded = []

    def fake_system(cmd):
        recorded.append(cmd)
        return 0

    monkeypatch.setattr(gadget_linux.os, 'system', fake_system)
    return recorded


def test_release_is_a_noop_without_the_gadget(gadget, calls):
    """Stock images have no RNDIS gadget: the package must stay portable."""
    assert not gadget.exists()
    assert gadget_linux.release_rndis_udc() is False
    assert calls == []


def test_release_unbinds_with_a_newline(gadget, calls):
    """A zero-length write is ignored by configfs, so the unbind writes '\\n'."""
    gadget.mkdir(parents=True)
    udc = gadget / 'UDC'
    udc.write_text('musb-hdrc.4.auto\n')

    assert gadget_linux.release_rndis_udc() is True
    assert udc.read_text() == '\n'


def test_release_survives_an_unwritable_udc(gadget, calls):
    """A read-only configfs file must not abort PC mode."""
    gadget.mkdir(parents=True)
    (gadget / 'UDC').mkdir()          # open() for writing fails with IsADirectoryError

    assert gadget_linux.release_rndis_udc() is False


def test_restore_restarts_the_network_service(gadget, calls):
    gadget.mkdir(parents=True)
    assert gadget_linux.restore_rndis() is True
    assert len(calls) == 1
    assert 'systemctl restart rndis.service' in calls[0]


def test_restore_is_a_noop_without_the_gadget(gadget, calls):
    assert gadget_linux.restore_rndis() is False
    assert calls == []


def test_pc_mode_releases_the_udc_before_loading_its_gadget(gadget, monkeypatch):
    """Order matters: g_acm_ms is parked as a pending driver if RNDIS still holds the UDC."""
    gadget.mkdir(parents=True)
    (gadget / 'UDC').write_text('musb-hdrc.4.auto\n')

    order = []
    monkeypatch.setattr(gadget_linux, 'release_rndis_udc',
                        lambda: order.append('release') or True)
    monkeypatch.setattr(gadget_linux.os, 'system',
                        lambda cmd: order.append(cmd))

    gadget_linux.upan_and_serial()
    assert order[0] == 'release'
    assert any('g_acm_ms' in cmd for cmd in order if isinstance(cmd, str))


def test_leaving_pc_mode_restores_the_network(gadget, monkeypatch):
    gadget.mkdir(parents=True)
    restored = []
    monkeypatch.setattr(gadget_linux, 'restore_rndis',
                        lambda: restored.append(True) or True)
    monkeypatch.setattr(gadget_linux.os, 'system', lambda cmd: 0)
    monkeypatch.setattr(gadget_linux, 'auto_ms_remount', lambda: None)

    gadget_linux.kill_all_module()
    assert restored == [True]
